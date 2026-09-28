# agents/thread_state.py — thread_state.py

> **文件路径**: `backend/packages/harness/agentflow/agents/thread_state.py`
> **目录位置**: agents → thread_state.py
> **职责**: 图状态定义

## 📋 结构图

```text
┌──────────────────────────────────────────────────────┐
│ class ThreadState(AgentState)                         │
│   └─ AgentState（langchain 内置）自带:                │
│       messages: Annotated[list[AnyMessage],          │
│                              add_messages]           │
│       → "更新 = 追加" reducer，多轮上下文靠它累积     │
│   └─ M1 增加: thread_id: str                         │
│       → checkpointer 按它在 SQLite 定位历史状态      │
└──────────────────────────────────────────────────────┘
```

## 📤 关键导出

**类**

- `ThreadState`
- `SandboxState`

## 💡 设计思想

1. 继承 AgentState（而非自己写 TypedDict）= 原版做法，
   reducer 语义由官方维护，不重复造轮子。
2. thread_id 作为状态字段，检查点按它分桶存储/恢复。

## 🎯 实用场景

1. 自定义图状态：AgentState 子类，为后续复杂状态预留

## ⚠️ 风险点

1. M2 实际 create_agent 未用此状态（内置 messages 状态）；
   接入自定义状态时同步改 create_agent 的 state_schema

---
_自动生成于 doc-code 规范落地（2026-09-28）。来源：thread_state.py 头部注释 + 顶层符号。_
