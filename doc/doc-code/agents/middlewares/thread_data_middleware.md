# agents/middlewares/thread_data_middleware.py — thread_data_middleware.py

> **文件路径**: `backend/packages/harness/agentflow/agents/middlewares/thread_data_middleware.py`
> **目录位置**: agents → middlewares → thread_data_middleware.py
> **职责**: 线程数据目录中间件

## 📋 结构图

```text
┌────────────────────────────────────────────────────────────┐
│ ThreadDataMiddlewareState(AgentState)                       │
│   thread_data: NotRequired[dict | None]                     │
│                                                             │
│ ThreadDataMiddleware(AgentMiddleware)                       │
│   before_agent(state, runtime) → dict | None                │
│     ① 从 runtime 取 thread_id（get_config）                 │
│     ② 路径 = {base}/threads/{thread_id}/user-data/          │
│              workspace / uploads / outputs                   │
│     ③ 同步 mkdir（M2 eager；原版 lazy 按需创建）             │
│     ④ 返回 {"thread_data": {...}} → merge 进 state          │
└────────────────────────────────────────────────────────────┘
```

## 📤 关键导出

**类**

- `ThreadDataMiddlewareState`
- `ThreadDataMiddleware`

**常量**

- `_DEFAULT_BASE_DIR`

## 💡 设计思想

1. 参考文档：doc/doc-dev/01-里程碑/M2-工具与中间件.md §2
2. 原版思想：每个会话有独立工作目录（文件类工具的输出落这里），
   是后续文件读写工具（M3+）的"地盘"。目录结构对齐原版命名。
3. M2 简化：去掉 Paths 解析，直接用 data/ 相对路径；
   建目录用 eager（一次建好）而非 lazy（按需创建），代码更简单。

## 🎯 实用场景

1. 会话工作区隔离：每个 thread 独立 user-data/{workspace,uploads,outputs}
2. M3 文件工具的地盘：文件读写工具的输出落这里，会话间不串扰
3. 上传/输出目录规划：uploads 收用户上传，outputs 放 Agent 生成物

## ❓ Q&A

**Q: 目录在哪？**

A: data/threads/{thread_id}/user-data/{workspace,uploads,outputs}

**Q: 为什么 eager 建目录？**

A: M2 简化：一次建好；原版 lazy 按需创建，M3 文件工具可改回

## ⚠️ 风险点

1. _DEFAULT_BASE_DIR="data" 是线程数据根；改它会让会话工作区整体迁移
2. 拿不到 thread_id 时静默跳过（before_agent 返回 None），不报错
3. M2 为 eager 建目录；改回 lazy 需同步调整 M3 文件工具的调用时机

---
_自动生成于 doc-code 规范落地（2026-09-28）。来源：thread_data_middleware.py 头部注释 + 顶层符号。_
