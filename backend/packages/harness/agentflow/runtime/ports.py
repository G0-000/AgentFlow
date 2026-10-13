# ============================================================================
# AgentFlow · runtime/ports.py —— 端口注册表（R1 反向桥的唯一 sanctioned 入口）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【结构图】
# ┌──────────────────────────────────────────────────────────────────────┐
# │ 核心层域代码（agents/collab/...）                                     │
# │      │  from agentflow.runtime import ports                         │
# │      ▼                                                              │
# │  ports.py（本文件）                                                  │
# │      _impls: dict[str, Any]   ← threading.Lock 保护的适配器注册表     │
# │      register / register_many / unregister / get / is_registered    │
# │      域访问器：无适配器 → no-op / None / False 降级                   │
# │      ▲                                                              │
# │      │ 应用层启动时一次性 register（app/gateway/runtime_adapters.py） │
# └──────────────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【设计思想】
# 规则 R1（架构文档 §1.3）：agentflow/ 下任何文件都不得 import app.*。
# 当核心代码需要应用层能力（SSE 广播、通道服务、语音、诊断…）时，改为消费本文件
# 的端口访问器；应用层在 create_app() 启动时把真实实现 register 进来。
# 语义：
#   - Gateway 进程：启动期装配，每个端口都解析到真实实现。
#   - 外部进程 / 纯核心单测：没有适配器，每个访问器按 no-op / 安全默认 / None
#     降级——等价于它取代的旧版 try: from app... except ImportError 写法。
# 端口 key 是稳定 API：改名必须同步改基线文档；新增端口允许，按域分组写在本文件。
# ----------------------------------------------------------------------------
# 🎯 【实用场景】
# 1. 核心域想往 SSE 订阅者推事件 → ports.broadcast_event(...)，离线自动静默。
# 2. 核心域想读自动化模式的外层提示规则 → ports.automation_langgraph_outer_rules()。
# ----------------------------------------------------------------------------
# 📊 【顺序执行链流程图】
# 核心域调用 broadcast_event(tid, type, data)
#   → impl = get("events.broadcaster")          ← 查注册表（无锁读 dict）
#   → impl is None ? → return False（离线降级，调用方走 HTTP relay 兜底）
#   → await impl.broadcast(...)
#        成功 → return True
#        异常被吞 → return False（广播失败不拖垮主流程）
# ----------------------------------------------------------------------------
# 🧩 【代码解析】
# - 注册表核心：模块级 _impls dict + threading.Lock；写操作持锁，读操作用 dict.get。
# - 域访问器：统一模式 impl = get("<域>.<能力>"); if impl is None: 降级; else 调用。
# - _BroadcasterProxy：模块级单例代理，让旧调用点 `await broadcaster.broadcast()`
#   零改动可用；离进程时自身就是 no-op。
# ----------------------------------------------------------------------------
# ❓ Q&A
# Q: 为什么注册表用模块级全局而不是传参？
# A: 核心域几十个调用点遍布中间件/工具，传参会污染所有签名；全局注册表 + 降级
#    语义是对旧版"随处 try import app"的收敛——只收敛到本文件一处。
# Q: 注册时机？
# A: 应用层 create_app() 内调用 register_runtime_adapters()（幂等），先于挂路由。
# ----------------------------------------------------------------------------
# ⚠️ 【风险点】
# 1. 本文件严禁 import app.*——这是 R1 的物理保证。
# 2. 访问器绝不能让异常冒泡到核心域：会影响主 Agent 循环，全部 try/降级包裹。
# 3. 端口 key 字符串改名 = 跨进程契约变更，需同步 runtime_adapters 与基线文档。
#
# 页脚：2026-10-13（移植自 evoflow/runtime/ports.py 最小骨架）
# ============================================================================

"""Runtime ports —— 核心层到应用层唯一的 sanctioned 反向桥（规则 R1）。

核心层域代码只通过本文件消费应用层能力；应用层在进程启动时经
``app.gateway.runtime_adapters.register_runtime_adapters()``
把适配器装进注册表。没有适配器时每个访问器降级为 no-op / None / False。
"""

from __future__ import annotations

import threading
from typing import Any

_lock = threading.Lock()
_impls: dict[str, Any] = {}


def register(key: str, impl: Any) -> None:
    """在 ``key`` 下注册一个应用层适配器（幂等：重复注册覆盖）。"""
    with _lock:
        _impls[key] = impl


def register_many(entries: dict[str, Any]) -> None:
    """批量注册适配器。"""
    with _lock:
        _impls.update(entries)


def unregister(key: str) -> None:
    """注销适配器；不存在时静默。"""
    with _lock:
        _impls.pop(key, None)


def get(key: str) -> Any | None:
    """取 ``key`` 对应的适配器；未注册返回 None。"""
    return _impls.get(key)


def is_registered(key: str) -> bool:
    """``key`` 是否已注册适配器。"""
    return key in _impls


# ----------------------------------------------------------------------------
# events —— SSE broadcaster 单例（对应 app.gateway.routers.events）
#   M8+ 再接真实适配器；当前仅提供降级语义的最小骨架。
# ----------------------------------------------------------------------------


class _BroadcasterProxy:
    """``await broadcaster.broadcast(...)`` 的惰性代理。

    保持调用点写法零改动；没有注册适配器时自身就是 no-op。
    """

    async def broadcast(self, thread_id: str, event_type: str, data: dict[str, Any]) -> None:
        impl = get("events.broadcaster")
        if impl is None:
            return
        await impl.broadcast(thread_id, event_type, data)


broadcaster = _BroadcasterProxy()


def get_event_broadcaster() -> Any | None:
    """返回 Gateway SSE broadcaster 单例；非 Gateway 进程返回 None。"""
    return get("events.broadcaster")


async def broadcast_event(thread_id: str, event_type: str, data: dict[str, Any]) -> bool:
    """异步向 SSE 订阅者广播；无适配器或广播失败返回 False。

    返回 bool 是为了让调用方（外部 LangGraph 进程）能回退到 HTTP relay 路径，
    与旧版语义一致。永不抛异常。
    """
    impl = get("events.broadcaster")
    if impl is None:
        return False
    try:
        await impl.broadcast(thread_id, event_type, data)
        return True
    except Exception:  # noqa: BLE001 —— 广播失败不拖垮主流程，静默降级返回 False
        return False


def get_broadcaster() -> Any | None:
    """``get_event_broadcaster`` 的别名。"""
    return get_event_broadcaster()


# ----------------------------------------------------------------------------
# automation —— 自动化模式 LangGraph 外层提示规则（Gateway 侧文案）
# ----------------------------------------------------------------------------


def automation_langgraph_outer_rules() -> str | None:
    """自动化模式的 LangGraph 外层提示规则（Gateway 文案）；无适配器返回 None。"""
    return get("automation.outer_rules")


# ----------------------------------------------------------------------------
# M8+ 按需再接的域访问器清单（原版 evoflow/runtime/ports.py 同构，当前不实现）：
#   - stream_inject   实时 run 注入队列（schedule_inject_evf_frame / inject_langgraph_custom）
#   - middle_layer    collab 中间层（covers_thread / get_active / resume_tool_approval）
#   - proxy           实时 runs/stream 代理（asgi_stream_active / unregister_active_stream_proxy）
#   - reconcile       run 状态缓存失效（invalidate_runs_probe_cache / is_thread_run_active）
#   - snapshot/defer  实时 run 快照 + run-finished 延迟（clear_gateway_live_snapshot 等）
#   - mirror          流镜像写入（enqueue_wire_text / set_mirror_model_ctx）
#   - kb_citations    实时 KB 引用 SSE 推送（publish_kb_citations）
#   - channels        通道服务与推送路由（get_channel_service / resolve_push_target）
#   - speech          火山 TTS/ASR（synthesize_speech_v3）
#   - diagnostics     事件循环健康（event_loop_lag_seconds）
#   - logs            网关日志目录与清理（resolve_gateway_logs_dir）
#   - goal            hosted-goal 实时态（is_goal_active_for_session）
#   - unattended      无人值守任务流水线（advance_unattended_task）
# 以上域在 AgentFlow 尚无对应应用层实现，待 M8+ 出现真实适配器时按原版同构补齐。
# ----------------------------------------------------------------------------
