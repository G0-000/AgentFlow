# gateway/runtime_adapters.py — runtime_adapters.py

> **文件路径**: `backend/app/gateway/runtime_adapters.py`
> **目录位置**: gateway → runtime_adapters.py
> **职责**: 应用层适配器注册入口——把 app 层真实实现装进核心 `agentflow.runtime.ports`（规则 R1 唯一反向桥的注册端；当前幂等空实现 + 分域占位）

## 📑 目录

- [📋 结构图 / 思维图](#📋-结构图--思维图)
- [📤 关键导出](#📤-关键导出)
- [💡 设计思想](#💡-设计思想)
- [🎯 实用场景](#🎯-实用场景)
- [🧩 顺序执行链](#🧩-顺序执行链)
- [🧩 代码解析](#🧩-代码解析)
- [❓ Q&A](#❓-qa)
- [⚠️ 风险点](#⚠️-风险点)

## 📋 结构图 / 思维图

```text
create_app() 启动时调用 register_runtime_adapters()
  │  模块级 _registered 标志保证幂等
  ▼
from agentflow.runtime import ports
  ports.register("<域>.<能力>", <真实实现>)      ← M8.1 起逐域填充
```

## 📤 关键导出

**register_runtime_adapters()** — 唯一导出（幂等）

## 💡 设计思想

1. **R1 唯一反向桥**：`app → agentflow` 方向的规则——核心层（`agentflow.runtime.ports`）定义端口，应用层（gateway）反向"喂"实现。本模块是**唯一 sanctioned 注册入口**，其他模块不直接 import ports 注册。
2. **启动时序**：Gateway 进程启动跑一次（先于挂路由）→ 端口解析到真实实现；外部进程 / CLI / 纯核心测试**永不 import 本模块** → 端口保持 no-op/None 降级。
3. **当前空实现 + 分域占位**：AgentFlow 尚无 SSE broadcaster / streaming / proxy / channels / speech 等应用层实现——函数体是注释占位（events/stream_inject/middle_layer/proxy/reconcile/mirror/channels/speech/diagnostics 9 个域），M8.1 出现真实域时按原版同构补 register。

## 🎯 实用场景

1. 未来新增 SSE broadcaster → events 分块里 `from app.gateway.routers import events; ports.register("events.broadcaster", events.broadcaster)`
2. 测试直接调 `ports.register/unregister` 注入假适配器，无需走本函数
3. CLI / 纯核心测试：不 import 本模块，端口自然保持降级

## 🧩 顺序执行链

```text
uvicorn --factory → create_default_app()
   ▼  create_app(config=cfg)
   ▼  register_runtime_adapters()          ← 工厂开头（先于 lifespan/挂路由）
   ▼  if _registered: return               ← 幂等：重复调用直接返回
   ▼  _registered = True
   ▼  from agentflow.runtime import ports  ← 惰性 import（函数体内）
   ▼  （M8.1）逐域 ports.register(...)      ← 当前仅注释占位
   ▼  logger.debug(no real adapters yet)   ← 空实现收尾
```

## 🧩 代码解析

```python
_registered = False

def register_runtime_adapters() -> None:
    global _registered
    if _registered:
        return
    _registered = True

    from agentflow.runtime import ports

    # ── events: SSE broadcaster ── 待 M8.1 注册：
    #   from app.gateway.routers import events as _ev
    #   ports.register("events.broadcaster", _ev.broadcaster)
    #   ...（stream_inject/middle_layer/proxy/reconcile/mirror/channels/speech/diagnostics）
```

**关键点**：

- **`_registered` 模块级全局**：测试里反复 `create_app()` 只装一次——幂等的核心是"全局标志 + 早退"。
- **`from agentflow.runtime import ports` 放函数体内（惰性）**：本模块被 import 时零副作用（不触发核心层 import）；应用层模块尚未就绪时也不炸。
- **工厂开头而非 lifespan**：测试用 TestClient 可能不触发 lifespan，但端口注册是"进程级一次性全局状态"，必须任何入口都执行过（与 app.py 块 3 决策一致）。
- **分域注释即路线图**：9 个域的注释块是 M8.1 的 register 清单——每完成一个域，把注释换成真实 `ports.register`。

## ❓ Q&A

**Q: 为什么不能在模块层直接 import ports 并注册？**
A: 模块层副作用会让"import 本模块"这件事产生全局状态，测试难以隔离；且应用层模块可能尚未就绪。惰性 + 幂等是原版既定约定。

**Q: 当前空实现的意义是什么？**
A: 装配位置与调用时序先行——`create_app` 已调它、幂等标志已在、ports 已惰性引入。M8.1 填真实 register 时**不用改装配链路**，只改本函数体。

**Q: 测试怎么注入假适配器？**
A: 测试直接 `from agentflow.runtime import ports; ports.register/unregister(...)` 注入/回收，不经过本函数——本函数是"生产装配路径"，测试路径独立。

## ⚠️ 风险点

1. 当前不得 import 任何尚不存在的应用层模块——否则 import 期就炸
2. 新增 register 时用 try/except 包裹单域，避免一个域缺失拖垮整个启动
3. `_registered` 是进程级全局：多进程/多副本各自维护，不共享（符合"进程级一次"语义）
4. 与 `doc-code/runtime/ports.md` 配套读：本文件是"注册端"，ports.md 是"端口定义端"

> 页脚：2026-10-19 · M7 Gateway 核心 · 对齐 `evoflow/app/gateway/runtime_adapters.py`（结构，空实现 + M8.1 分域占位）
