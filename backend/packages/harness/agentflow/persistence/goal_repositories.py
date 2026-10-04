# ============================================================================
# AgentFlow · persistence/goal_repositories.py —— 长任务（goal）数据访问
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/persistence/goal_repositories.py
# 对标来源: evoflow/collab/plan_task_storage.py + agents/goal/goal_runtime.py
#   原版计划挂在主任务宽表上；M5 裁剪成独立 goals 表（一行 = 一个长任务尝试，
#   步骤计划 JSON 同行），走 BaseRepository 的 db_path 线程本地连接模式（P-018）。
# 里程碑: M5
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────────┐
# │ GoalRepository(BaseRepository)                          │
# │   table_name → "goals"                                  │
# │   create(goal_id, thread_id, goal_text, ...)            │
# │   get(goal_id) → 目标行                                 │
# │   get_active_by_thread(thread_id) → 未完成目标（恢复键） │
# │   update_plan(goal_id, plan_steps_json, status)         │
# │   patch(goal_id, **fields) —— 防终态覆盖（原子 UPDATE）  │
# │   begin_step(goal_id, current_step, plan_steps_json)     │
# │   complete_step(goal_id, current_step, plan_steps_json) │
# │       → completed_steps+1 / current_step / 回写 JSON    │
# │   complete_goal(goal_id, summary, outcome)              │
# └────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. repo 只做原语（SQL），状态迁移合法性由 plans/service.py 的服务层守卫；
#    patch() 带 WHERE goal_status IN 非终态集合（PATCHABLE_GOAL_STATUSES，含
#    pending），防终态行被覆盖（仿原版 patch_goal_runtime_atomic）。
# 2. 断点坐标 = current_step + plan_steps_json(每步 status) + completed_steps；
#    消息历史交 checkpointer，SQL 只管业务坐标（R3：先 invoke 落消息再写 SQL）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. GoalRepository: goals 表数据访问（继承 BaseRepository）
# 🔒 内部私有函数
# 无
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. patch() 的 WHERE 守卫放过全部非终态（PATCHABLE_GOAL_STATUSES，含 pending；
#    防的是终态 completed/failed/cancelled 被覆盖）；写终态请用
#    complete_goal/fail_task 专用方法。注意 pending 必须可 patch——
#    service.begin_planning() 就是靠 patch 把 pending 行迁到 planning。
# 2. get_active_by_thread 的可恢复态是 OPEN_GOAL_STATUSES（4 态，不含 pending），
#    与 patch 守卫不是同一个集合，勿混用。
# 3. 表列与 doc-dev/01-里程碑/M5-长任务与协作.md §5 DDL 逐字对齐，勿改列名
# ============================================================================

from __future__ import annotations

import sqlite3

from agentflow.agents.goal.goal_state import OPEN_GOAL_STATUSES, PATCHABLE_GOAL_STATUSES
from agentflow.persistence.repositories import BaseRepository
from agentflow.persistence.timestamps import now_utc_iso

# IN 子句片段：patch 守卫 = 全部非终态（含 pending）；恢复定位 = 4 态可恢复态
_PATCHABLE_IN = "(" + ", ".join(f"'{s}'" for s in sorted(PATCHABLE_GOAL_STATUSES)) + ")"
_OPEN_IN = "(" + ", ".join(f"'{s}'" for s in sorted(OPEN_GOAL_STATUSES)) + ")"


class GoalRepository(BaseRepository):
    """goals 表数据访问（长任务 = goal 行 + 步骤计划 JSON 同行）。"""

    @property
    def table_name(self) -> str:
        return "goals"

    # ---------- CRUD ----------
    def create(
        self,
        goal_id: str,
        thread_id: str,
        goal_text: str,
        goal_status: str = "pending",
        plan_steps_json: str = "[]",
        max_steps: int = 12,
        completed_steps: int = 0,
    ) -> None:
        """建一条长任务行（初始 pending，由 service.begin_planning 迁到 planning）。"""
        now = now_utc_iso()
        self._execute(
            "INSERT INTO goals ("
            "goal_id, thread_id, goal_text, goal_status, current_step, "
            "plan_steps_json, max_steps, completed_steps, "
            "last_error, stop_reason, summary, outcome, created_at, updated_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                goal_id,
                thread_id,
                goal_text,
                goal_status,
                "",  # current_step：尚未开始
                plan_steps_json,
                max_steps,
                completed_steps,
                "",  # last_error
                "",  # stop_reason
                "",  # summary
                "",  # outcome
                now,
                now,
            ),
        )

    def get(self, goal_id: str) -> sqlite3.Row | None:
        """按 goal_id 取目标行。"""
        return self._fetch_one("SELECT * FROM goals WHERE goal_id = ?", (goal_id,))

    def get_active_by_thread(self, thread_id: str) -> sqlite3.Row | None:
        """按会话取未完成目标（断点恢复定位键）。

        可恢复态 = OPEN_GOAL_STATUSES（planning/planned/executing/paused；
        pending 无步骤可恢复，不算）；多行时取最新一条。
        """
        return self._fetch_one(
            f"SELECT * FROM goals WHERE thread_id = ? "
            f"AND goal_status IN {_OPEN_IN} "
            f"ORDER BY created_at DESC LIMIT 1",
            (thread_id,),
        )

    def delete(self, goal_id: str) -> None:
        """删除一条目标行（测试清理用）。"""
        self._execute("DELETE FROM goals WHERE goal_id = ?", (goal_id,))

    # ---------- 计划与迁移原语 ----------
    def update_plan(self, goal_id: str, plan_steps_json: str, status: str) -> None:
        """落步骤计划 JSON 并切目标状态（planning → planned，服务层校验后调用）。"""
        self._execute(
            "UPDATE goals SET plan_steps_json = ?, goal_status = ?, updated_at = ? "
            "WHERE goal_id = ?",
            (plan_steps_json, status, now_utc_iso(), goal_id),
        )

    def patch(self, goal_id: str, **fields) -> None:
        """原子打补丁（防终态覆盖）：只当 goal_status ∈ 非终态时才允许 UPDATE。

        可写态 = PATCHABLE_GOAL_STATUSES（全部非终态，含 pending）——
        pending 行必须可 patch，否则 service.begin_planning()（pending→planning）
        命中 0 行静默无写入（M5 实测 bug）。
        调用方用 `status=...` 关键字（自动映射到列 goal_status）；
        其余字段名与表列同名（current_step/plan_steps_json/last_error/
        stop_reason/summary/outcome/completed_steps/max_steps）。
        """
        if not fields:
            return
        data = dict(fields)
        if "status" in data:  # 关键字别名 → 真实列名 goal_status
            data["goal_status"] = data.pop("status")
        sets = [f"{col} = ?" for col in data]
        sets.append("updated_at = ?")
        params: list = list(data.values())
        params.append(now_utc_iso())
        params.append(goal_id)
        self._execute(
            f"UPDATE goals SET {', '.join(sets)} "
            f"WHERE goal_status IN {_PATCHABLE_IN} "
            f"AND goal_id = ?",
            tuple(params),
        )

    def begin_step(self, goal_id: str, current_step: str, plan_steps_json: str) -> None:
        """开始执行一步：写断点坐标 current_step + 回写该步 executing 的计划 JSON。"""
        self._execute(
            "UPDATE goals SET current_step = ?, plan_steps_json = ?, updated_at = ? "
            "WHERE goal_id = ?",
            (current_step, plan_steps_json, now_utc_iso(), goal_id),
        )

    def complete_step(self, goal_id: str, current_step: str, plan_steps_json: str) -> None:
        """完成一步：completed_steps+1、current_step 更新、回写 completed 后的 JSON。"""
        self._execute(
            "UPDATE goals SET completed_steps = completed_steps + 1, "
            "current_step = ?, plan_steps_json = ?, updated_at = ? WHERE goal_id = ?",
            (current_step, plan_steps_json, now_utc_iso(), goal_id),
        )

    def complete_goal(self, goal_id: str, summary: str, outcome: str) -> None:
        """目标整体完工：写 summary/outcome 并切终态 completed。"""
        self._execute(
            "UPDATE goals SET summary = ?, outcome = ?, goal_status = 'completed', "
            "updated_at = ? WHERE goal_id = ?",
            (summary, outcome, now_utc_iso(), goal_id),
        )
