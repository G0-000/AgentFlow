# agents/checkpointer/async_provider.py — async_provider.py

> **文件路径**: `backend/packages/harness/agentflow/agents/checkpointer/async_provider.py`
> **目录位置**: agents → checkpointer → async_provider.py
> **职责**: 异步 SQLite 检查点

## 📋 结构图

```text
┌──────────────────────────────────────────────┐
│ async create_async_sqlite_checkpointer(     │
│         db_path) → AsyncSqliteSaver         │
│   conn = await aiosqlite.connect(db_path)   │
│   return AsyncSqliteSaver(conn)             │
│                                              │
│ 用法（M7 FastAPI）:                          │
│   cp = await create_async_sqlite_checkpointer│
│   await cp.setup()  （一次性初始化表）        │
└──────────────────────────────────────────────┘
```

## 📤 关键导出

（无顶层导出，见结构图）

## 💡 设计思想

1. 异步检查点基于 aiosqlite，为 M7 gateway（FastAPI async 端点）预留。
2. 与 provider.py 同步版并存：CLI 用同步，gateway 用异步，互不干扰。

## 🎯 实用场景

1. 异步检查点：AsyncSqliteSaver（未来 gateway 异步场景用）

## ⚠️ 风险点

1. 返回的 saver 需 await setup() 初始化表（同步版无需）
2. M1-M6 不使用此文件，勿在 CLI 误用（会缺初始化步骤）

---
_自动生成于 doc-code 规范落地（2026-09-28）。来源：async_provider.py 头部注释 + 顶层符号。_
