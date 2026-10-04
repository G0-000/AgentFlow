# ============================================================================
# AgentFlow · plans/service.py —— 长任务状态迁移守卫（M5）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/plans/service.py
# 对标来源: evoflow/collab/task_state_service.py + state_transitions.py
#   原版是 pydantic 记录 + hooks 的重型迁移器；M5 裁剪成"读行→校验→repo.patch"
#   的薄守卫。M5 自动授权：planned→executing 不再等人确认。
# 里程碑: M5
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────────┐
# │ ALLOWED_TRANSITIONS（goal 级迁移白名单，字符串态）      │
# │ GoalStateTransitionError                               │
# │ GoalStateService(goal_repo)                            │
# │   begin_planning / finalize_plan / begin_execution      │
# │   complete_step / fail_task / pause_task /             │
# │   resume_task / complete_task                           │
# │   —— 每个方法先校验迁移合法，再经 GoalRepository 落库   │
# └────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 分层：service 做守卫（能不能迁），repo 做原语（怎么写 SQL）。
#    goal_loop 一律经 service 走迁移，不直接裸改 goal_status。
# 2. 8 态白名单照 doc-dev/01-里程碑/M5-长任务与协作.md §3：
#    pending→planning/planned/executing/cancelled
#    planning→planned/failed/cancelled
#    planned→executing/planning/cancelled
#    executing→paused/completed/failed/cancelled
#    paused→executing/cancelled
#    failed→executing/cancelled
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. ALLOWED_TRANSITIONS: goal 状态迁移白名单
# 2. GoalStateTransitionError: 非法迁移异常
# 3. GoalStateService: 状态迁移器
# 🔒 内部私有函数
# 1. _current_status: 从 goal 行取 goal_status
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. patch() 自带"开放态 WHERE 守卫"，本 service 再叠一层迁移白名单校验——
#    双保险：即使绕过 service，终态行也不会被 SQL 覆盖
# ============================================================================

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agentflow.persistence.goal_repositories import GoalRepository


# goal 级状态迁移白名单（from → 允许的 to 集合）
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"planning", "planned", "executing", "cancelled"}),
    "planning": frozenset({"planned", "failed", "cancelled"}),
    "planned": frozenset({"executing", "planning", "cancelled"}),
    "executing": frozenset({"paused", "completed", "failed", "cancelled"}),
    "paused": frozenset({"executing", "cancelled"}),
    "failed": frozenset({"executing", "cancelled"}),
    "completed": frozenset(),  # 终态
    "cancelled": frozenset(),  # 终态
}


class GoalStateTransitionError(RuntimeError):
    """非法的 goal 状态迁移（当前态不在白名单允许路径上）。"""


def _current_status(row) -> str:
    """从 repo 行（sqlite3.Row）取 goal_status。"""
    if row is None:
        raise GoalStateTransitionError("目标行不存在")
    return str(row["goal_status"])


class GoalStateService:
    """长任务状态迁移器：所有 goal_status 变更的唯一合法入口。"""

    def __init__(self, goal_repo: GoalRepository):
        self._repo = goal_repo

    # ---------- 内部守卫 ----------
    def _assert_can(self, goal_id: str, to_status: str) -> str:
        """校验 goal 可迁到 to_status，返回当前状态；否则 raise GoalStateTransitionError。"""
        row = self._repo.get(goal_id)
        current = _current_status(row)
        allowed = ALLOWED_TRANSITIONS.get(current, frozenset())
        if to_status not in allowed:
            raise GoalStateTransitionError(
                f"非法迁移: goal={goal_id} {current} → {to_status}"
            )
        return current

    def _transition(self, goal_id: str, to_status: str, **patch_fields) -> None:
        """校验后落库：状态 + 附带字段（stop_reason/last_error 等）。"""
        self._assert_can(goal_id, to_status)
        self._repo.patch(goal_id, status=to_status, **patch_fields)

    # ---------- 迁移动作 ----------
    def begin_planning(self, goal_id: str) -> None:
        """pending → planning：开始生成步骤计划。"""
        self._transition(goal_id, "planning")

    def finalize_plan(self, goal_id: str, plan_steps_json: str) -> None:
        """planning → planned：拓扑校验通过，落计划 JSON。"""
        self._assert_can(goal_id, "planned")
        self._repo.update_plan(goal_id, plan_steps_json=plan_steps_json, status="planned")

    def begin_execution(self, goal_id: str) -> None:
        """planned → executing：M5 自动授权，不等用户二次确认。"""
        self._transition(goal_id, "executing")

    def complete_step(self, goal_id: str, step_ref: str, plan_steps_json: str) -> None:
        """一步执行完毕：要求目标处于 executing；走 repo.complete_step 原语。"""
        row = self._repo.get(goal_id)
        if _current_status(row) != "executing":
            raise GoalStateTransitionError(
                f"complete_step 需要 executing，当前={_current_status(row)}"
            )
        self._repo.complete_step(goal_id, current_step=step_ref, plan_steps_json=plan_steps_json)

    def pause_task(self, goal_id: str, stop_reason: str = "") -> None:
        """executing → paused：熔断/空回复/异常/步数上限等断点。"""
        self._transition(goal_id, "paused", stop_reason=stop_reason)

    def resume_task(self, goal_id: str) -> None:
        """paused → executing：--thread 恢复断点续跑。"""
        self._transition(goal_id, "executing")

    def fail_task(self, goal_id: str, last_error: str = "") -> None:
        """planning/executing → failed：计划生成失败等致命错误。"""
        self._transition(goal_id, "failed", last_error=last_error)

    def complete_task(self, goal_id: str, summary: str, outcome: str = "done") -> None:
        """executing → completed：全部步骤走完，写汇总报告。"""
        self._assert_can(goal_id, "completed")
        self._repo.complete_goal(goal_id, summary=summary, outcome=outcome)
