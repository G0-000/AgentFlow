# ============================================================================
# AgentFlow · agents/goal/goal_state.py —— 长任务状态常量 + GoalRow
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/agents/goal/goal_state.py
# 对标来源: evoflow/agents/goal/goal_state.py
#   原版 GoalState 含 messages 字段（M5 砍：消息交 checkpointer）。
# 里程碑: M5
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────────────┐
# │ goal_status 8 态常量                                 │
# │ step status 4 态常量（pending/executing/...）         │
# │ GoalRow(dataclass) —— goals 表列的内存镜像           │
# │ goal_row_from_row(sqlite3.Row) → GoalRow              │
# └──────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 状态字符串集中在此，散模块不裸写 "executing" 等字面量（防漂移）。
# 2. GoalRow 字段 = goals 表列（DDL 见 persistence/schema.py M5 段）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. 状态常量（GOAL_STATUS_* / STEP_STATUS_*）
# 2. GoalRow: goal 行数据类
# 3. goal_row_from_row: sqlite3.Row → GoalRow
# ----------------------------------------------------------------------------

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

# ---------- goal_status 8 态 ----------
GOAL_STATUS_PENDING = "pending"
GOAL_STATUS_PLANNING = "planning"
GOAL_STATUS_PLANNED = "planned"
GOAL_STATUS_EXECUTING = "executing"
GOAL_STATUS_PAUSED = "paused"
GOAL_STATUS_COMPLETED = "completed"
GOAL_STATUS_FAILED = "failed"
GOAL_STATUS_CANCELLED = "cancelled"

# ---------- step status 4 态 ----------
STEP_STATUS_PENDING = "pending"
STEP_STATUS_EXECUTING = "executing"
STEP_STATUS_COMPLETED = "completed"
STEP_STATUS_FAILED = "failed"

# 可恢复态（4 态）：get_active_by_thread 的 WHERE 集合。
# pending 无步骤可恢复（plan_steps_json 还是 "[]"），不算可恢复态。
OPEN_GOAL_STATUSES = frozenset(
    {
        GOAL_STATUS_PLANNING,
        GOAL_STATUS_PLANNED,
        GOAL_STATUS_EXECUTING,
        GOAL_STATUS_PAUSED,
    }
)

# 终态：infer_lifecycle_stage 映射 done
TERMINAL_GOAL_STATUSES = frozenset(
    {GOAL_STATUS_COMPLETED, GOAL_STATUS_FAILED, GOAL_STATUS_CANCELLED}
)

# patch 守卫可写态：全部非终态（含 pending）。
# patch() 的 WHERE 守卫语义 = "防终态覆盖"：终态行（completed/failed/cancelled）
# 不允许被原子补丁覆写；pending 行（刚 create、尚未开跑规划）必须可 patch——
# 否则 service.begin_planning()（pending→planning）命中 0 行静默无写入。
PATCHABLE_GOAL_STATUSES = frozenset(
    {
        GOAL_STATUS_PENDING,
        GOAL_STATUS_PLANNING,
        GOAL_STATUS_PLANNED,
        GOAL_STATUS_EXECUTING,
        GOAL_STATUS_PAUSED,
    }
)


@dataclass
class GoalRow:
    """goals 表行的内存镜像（字段与 DDL 列逐一对齐）。"""

    goal_id: str
    thread_id: str
    goal_text: str
    goal_status: str
    current_step: str
    plan_steps_json: str
    max_steps: int
    completed_steps: int
    last_error: str
    stop_reason: str
    summary: str
    outcome: str
    created_at: str
    updated_at: str


def goal_row_from_row(row: sqlite3.Row) -> GoalRow:
    """sqlite3.Row → GoalRow（引擎内部用数据类替代裸 Row）。"""
    return GoalRow(
        goal_id=row["goal_id"],
        thread_id=row["thread_id"],
        goal_text=row["goal_text"],
        goal_status=row["goal_status"],
        current_step=row["current_step"],
        plan_steps_json=row["plan_steps_json"],
        max_steps=row["max_steps"],
        completed_steps=row["completed_steps"],
        last_error=row["last_error"],
        stop_reason=row["stop_reason"],
        summary=row["summary"],
        outcome=row["outcome"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
