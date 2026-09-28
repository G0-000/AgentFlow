# agents/checkpointer/provider.py — provider.py

> **文件路径**: `backend/packages/harness/agentflow/agents/checkpointer/provider.py`
> **目录位置**: agents → checkpointer → provider.py
> **职责**: 同步 SQLite 检查点

## 📋 结构图

```text
┌──────────────────────────────────────────────┐
│ create_sqlite_checkpointer(db_path)          │
│   conn = sqlite3.connect(db_path,            │
│           check_same_thread=False)           │
│   return SqliteSaver(conn)                   │
│                                              │
│ 用法（agent.py）:                             │
│   create_agent(..., checkpointer=checkpointer)│
└──────────────────────────────────────────────┘
```

## 📤 关键导出

**函数**

- `create_sqlite_checkpointer()`

## 💡 设计思想

1. 3.x 的 from_conn_string() 返回上下文管理器（with 才拿到实例），
   不适合这里；直接构造 SqliteSaver(conn) 更简单（P-010 教训）。
2. 每步自动把图状态序列化存入 SQLite（无需手写存取）。

## 🎯 实用场景

1. SQLite 检查点工厂：SqliteSaver 连接封装（thread_id 维度持久化）

## ⚠️ 风险点

1. check_same_thread=False 是必须的（CLI 单线程跑，但 langgraph 内部可能跨线程）
2. 换异步场景用 async_provider.py，不要改本文件

---
_自动生成于 doc-code 规范落地（2026-09-28）。来源：provider.py 头部注释 + 顶层符号。_
