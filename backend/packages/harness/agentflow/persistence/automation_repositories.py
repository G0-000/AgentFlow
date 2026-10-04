# ============================================================================
# AgentFlow · persistence/automation_repositories.py —— 定时任务数据访问（M5）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/persistence/automation_repositories.py
# 对标来源: evoflow/persistence/automation_repositories.py
# 里程碑: M5
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────────────────────┐
# │ AutomationRepository(BaseRepository)                          │
# │   automations 表（任务定义）:                                 │
# │     create/get/list_active/list/pause/resume/delete          │
# │     touch_last_run(last_status, run_count_inc, once_fired)  │
# │   automation_runs 表（执行历史）:                            │
# │     start_run(task_id)->run_id / finish_run(run_id,...)     │
# └──────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 走 BaseRepository db_path 模式（P-018）：scheduler daemon 线程与主线程
#    各持线程本地连接，不共享 conn；WAL 下读写不互斥。
# 2. 列名逐字对齐 M5 规划 §5 DDL（automations / automation_runs）。
# 3. delete 只删任务行，runs 历史保留（不级联）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. AutomationRepository: 定时任务 + 执行历史数据访问
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. 时间戳一律 now_utc_iso()（全库唯一来源）
# 2. once_fired 仅在传入时更新（None=不动该列）
# ============================================================================

from __future__ import annotations

import os

from agentflow.persistence.repositories import BaseRepository
from agentflow.persistence.timestamps import now_utc_iso


class AutomationRepository(BaseRepository):
    """automations（任务定义）+ automation_runs（执行历史）两表数据访问。"""

    @property
    def table_name(self) -> str:
        return "automations"

    # ---------- 任务定义 CRUD ----------
    def create(
        self,
        task_id: str,
        name: str,
        prompt: str,
        schedule: str,
        schedule_type: str = "recurring",
        scheduled_at: str | None = None,
        status: str = "active",
    ) -> None:
        """创建一条定时任务（schedule 应为 normalize_schedule 归一后的 5 字段 cron）。"""
        now = now_utc_iso()
        self._execute(
            "INSERT INTO automations "
            "(task_id, name, prompt, schedule, schedule_type, scheduled_at, "
            " status, once_fired, last_run, last_status, run_count, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 0, NULL, '', 0, ?, ?)",
            (task_id, name, prompt, schedule, schedule_type, scheduled_at, status, now, now),
        )

    def get(self, task_id: str) -> dict | None:
        """按 task_id 取任务行（dict）。"""
        row = self._fetch_one(
            "SELECT * FROM automations WHERE task_id = ?", (task_id,)
        )
        return dict(row) if row else None

    def list_active(self) -> list[dict]:
        """全部 active 任务（scheduler tick 每轮调用）。"""
        rows = self._fetch_all(
            "SELECT * FROM automations WHERE status = 'active'"
        )
        return [dict(r) for r in rows]

    def list(self) -> list[dict]:
        """全部任务（list 子命令用，按创建时间倒序）。"""
        rows = self._fetch_all(
            "SELECT * FROM automations ORDER BY created_at DESC"
        )
        return [dict(r) for r in rows]

    def pause(self, task_id: str) -> None:
        """暂停任务（active → paused）。"""
        self._execute(
            "UPDATE automations SET status = 'paused', updated_at = ? WHERE task_id = ?",
            (now_utc_iso(), task_id),
        )

    def resume(self, task_id: str) -> None:
        """恢复任务（paused → active）。"""
        self._execute(
            "UPDATE automations SET status = 'active', updated_at = ? WHERE task_id = ?",
            (now_utc_iso(), task_id),
        )

    def delete(self, task_id: str) -> None:
        """删除任务定义（automation_runs 历史保留，不级联删）。"""
        self._execute("DELETE FROM automations WHERE task_id = ?", (task_id,))

    def touch_last_run(
        self,
        task_id: str,
        last_status: str,
        run_count_inc: int = 1,
        once_fired: int | None = None,
    ) -> None:
        """一次执行结束后回写任务行：last_run 时间 / last_status / run_count 递增。

        once_fired 仅在显式传入时更新（once 型传 1 做落库幂等标记）。
        """
        now = now_utc_iso()
        if once_fired is not None:
            self._execute(
                "UPDATE automations SET last_run = ?, last_status = ?, "
                "run_count = run_count + ?, once_fired = ?, updated_at = ? "
                "WHERE task_id = ?",
                (now, last_status, run_count_inc, once_fired, now, task_id),
            )
        else:
            self._execute(
                "UPDATE automations SET last_run = ?, last_status = ?, "
                "run_count = run_count + ?, updated_at = ? WHERE task_id = ?",
                (now, last_status, run_count_inc, now, task_id),
            )

    # ---------- 执行历史 automation_runs ----------
    def start_run(self, task_id: str) -> str:
        """开一条运行记录（status='running'），返回 run_id。"""
        run_id = "r_" + os.urandom(6).hex()
        self._execute(
            "INSERT INTO automation_runs (task_id, run_id, started_at, status) "
            "VALUES (?, ?, ?, 'running')",
            (task_id, run_id, now_utc_iso()),
        )
        return run_id

    def finish_run(
        self,
        run_id: str,
        status: str,
        output: str = "",
        error: str = "",
        duration_seconds: float | None = None,
    ) -> None:
        """结束运行记录：写 finished_at / status / output / error / duration。"""
        self._execute(
            "UPDATE automation_runs SET finished_at = ?, status = ?, output = ?, "
            "error = ?, duration_seconds = ? WHERE run_id = ?",
            (now_utc_iso(), status, output, error, duration_seconds, run_id),
        )
