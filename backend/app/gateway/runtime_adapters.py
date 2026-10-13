# ============================================================================
# AgentFlow · app/gateway/runtime_adapters.py —— 应用层适配器注册入口
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【结构图】
# ┌──────────────────────────────────────────────────────────────────────┐
# │ create_app() 启动时调用 register_runtime_adapters()                 │
# │      │  模块级 _registered 标志保证幂等                              │
# │      ▼                                                              │
# │ from agentflow.runtime import ports                                 │
# │      ports.register("<域>.<能力>", <真实实现>)                       │
# └──────────────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【设计思想】
# 这是从 app 反向"喂"实现给 agentflow.runtime.ports 的唯一 sanctioned
# 入口（规则 R1）。Gateway 进程启动时跑一次（先于挂路由），端口就都解析到真实
# 实现；外部进程 / CLI / 纯核心测试永远不 import 本模块 → 端口保持 no-op/None 降级。
#
# 当前 AgentFlow 尚无 SSE broadcaster / streaming / proxy / channels / speech 等
# 应用层实现（gateway 下只有 app/model_store/sse/routers），因此本函数体目前为空
# 实现 + 分域注释占位；M8+ 出现真实域时按原版同构补 register。
# ----------------------------------------------------------------------------
# 🎯 【实用场景】
# 1. 未来新增 SSE broadcaster → 在 events 分块里 from app.gateway.routers
#    import events; ports.register("events.broadcaster", events.broadcaster)。
# 2. 测试可直接调 ports.register/unregister 注入假适配器，无需走本函数。
# ----------------------------------------------------------------------------
# 📊 【顺序执行链流程图】
# create_app() → register_runtime_adapters()
#   → if _registered: return（幂等，重复调用直接返回）
#   → _registered = True → from agentflow.runtime import ports
#   → （M8+）逐域 ports.register(...)
# ----------------------------------------------------------------------------
# 🧩 【代码解析】
# - _registered 是模块级全局：跨 create_app 多次调用（测试里反复建 app）只装一次。
# - 真正的 from agentflow.runtime import ports 放在函数体内（惰性），
#   保证本模块被 import 时零副作用、import 安全。
# ----------------------------------------------------------------------------
# ❓ Q&A
# Q: 为什么不能在模块层就 import ports 并注册？
# A: 模块层副作用会让"import 本模块"这件事产生全局状态，测试难以隔离；
#    且应用层模块可能尚未就绪。惰性 + 幂等是原版既定约定。
# ----------------------------------------------------------------------------
# ⚠️ 【风险点】
# 1. 本文件当前不得 import 任何尚不存在的应用层模块——否则 import 期就炸。
# 2. 新增 register 时用 try/except 包裹单域，避免一个域缺失拖垮整个启动。
#
# 页脚：2026-10-13（对齐 evoflow/app/gateway/runtime_adapters.py 结构）
# ============================================================================

"""把应用层适配器装进核心 runtime 端口（R1 唯一反向桥的注册端）。

当前 AgentFlow 无真实适配器可注册，本函数为幂等空实现 + 分域注释占位。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_registered = False


def register_runtime_adapters() -> None:
    """把应用层适配器装进 ``agentflow.runtime.ports``（幂等）。"""
    global _registered
    if _registered:
        return
    _registered = True

    from agentflow.runtime import ports

    # ── events: SSE broadcaster ─────────────────────────────────────────
    # 待 M8+ 注册：
    #   from app.gateway.routers import events as _ev
    #   ports.register("events.broadcaster", _ev.broadcaster)
    #   ports.register("events.broadcaster_cls", _ev.EventBroadcaster)

    # ── stream_inject: 实时 run 注入队列 ────────────────────────────────
    # 待 M8+ 注册（streaming/session_stream_inject）。

    # ── middle_layer: collab 中间层 ─────────────────────────────────────
    # 待 M8+ 注册（streaming/stream_middle_layer）。

    # ── proxy: 实时 runs/stream 代理 ────────────────────────────────────
    # 待 M8+ 注册（routers/langgraph_proxy）。

    # ── reconcile / snapshot / defer: run 状态与快照 ────────────────────
    # 待 M8+ 注册（run_status_reconcile / live_run_snapshot / post_stream_ui_normalize）。

    # ── mirror / kb_citations: 流镜像与 KB 引用推送 ─────────────────────
    # 待 M8+ 注册（streaming/stream_mirror / kb_citations_publisher）。

    # ── channels: 通道服务与推送路由 ────────────────────────────────────
    # 待 M8+ 注册（app/channels/service / channel_result_push）。

    # ── speech: 火山 TTS/ASR ────────────────────────────────────────────
    # 待 M8+ 注册（gateway/speech/volcengine_speech）。

    # ── diagnostics / logs / automation / goal / unattended ────────────
    # 待 M8+ 注册（hang_diagnostics / logging_setup / automation_runner
    #              / goal_stream_events / unattended_task_pipeline）。

    logger.debug(
        "register_runtime_adapters: no real adapters yet (M8+), ports=%s stay no-op",
        ports.__name__,
    )
