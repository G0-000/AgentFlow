# ============================================================================
# AgentFlow · agents/thread_state.py —— 图状态定义
# ----------------------------------------------------------------------------
# 文件: backend/packages/harness/agentflow/agents/thread_state.py
# 仿原: evoflow/agents/thread_state.py（原版还定义 SandboxState/ThreadDataState
#       等子状态 TypedDict，M1 只保留 ThreadState 本体 + SandboxState 占位）
# 里程碑: M1
# ----------------------------------------------------------------------------
# 结构图:
# ┌──────────────────────────────────────────────────────┐
# │ class ThreadState(AgentState)                         │
# │   └─ AgentState（langchain 内置）自带:                │
# │       messages: Annotated[list[AnyMessage],          │
# │                              add_messages]           │
# │       → "更新 = 追加" reducer，多轮上下文靠它累积     │
# │   └─ M1 增加: thread_id: str                         │
# │       → checkpointer 按它在 SQLite 定位历史状态      │
# │                                                      │
# │ 关键: 继承 AgentState（而非自己写 TypedDict）        │
# │       = 原版做法，reducer 语义由官方维护              │
# └──────────────────────────────────────────────────────┘
# ============================================================================
from __future__ import annotations

from typing import NotRequired

# AgentState: langchain 官方 Agent 状态基类
# 自带 messages + add_messages reducer（追加语义）——与 LangGraph 图天然契合
from langchain.agents import AgentState
from typing_extensions import TypedDict


class ThreadState(AgentState):
    """LangGraph 图的共享状态（每轮对话在节点间传递）。

    M1 只有一个自有字段:
        thread_id: 会话标识。checkpointer 用它在 SQLite 里定位
                   对应线程的历史状态（恢复会话的依据）

    继承 AgentState 说明:
        messages 字段（含追加 reducer）由官方基类提供，
        不用自己写 TypedDict——这是原版的做法。
    """

    thread_id: str


class SandboxState(TypedDict):
    """沙箱状态（对齐原版结构，M4 沙箱用；M1 只占位不启用）。"""

    sandbox_id: NotRequired[str | None]
