# ============================================================================
# AgentFlow · persistence/session_repositories.py —— 会话数据访问
# ----------------------------------------------------------------------------
# 文件: backend/packages/harness/agentflow/persistence/session_repositories.py
# 仿原: evoflow/persistence/session_repositories.py + thread_repositories.py
#       （原版会话/线程分两个 repo，M1 合并成一个 SessionRepository）
# 里程碑: M1
# ----------------------------------------------------------------------------
# 结构图:
# ┌────────────────────────────────────────────────────┐
# │ SessionRepository(BaseRepository)                  │
# │   table_name → "sessions"                          │
# │   create(thread_id, title="") → 建会话            │
# │   get(thread_id) → 会话行                         │
# │   delete(thread_id) → 删会话                      │
# │   add_message(session_id, role, content)          │
# │       → 写入 session_messages（带时间戳）          │
# │   list_messages(session_id) → 按时间序消息        │
# │   touch(thread_id) → 更新 updated_at              │
# │   update_title(thread_id, title) → 改标题         │
# └────────────────────────────────────────────────────┘
# ============================================================================
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from agentflow.persistence.repositories import BaseRepository


class SessionRepository(BaseRepository):
    """sessions / session_messages 两张表的数据访问。

    职责边界:
        - 这里存"业务记录"（会话 + 明文消息）
        - 图状态（ThreadState）由 checkpointer 管（另一个文件）
        - 两者通过 thread_id 关联，各管各的，不混淆
    """

    @property
    def table_name(self) -> str:
        return "sessions"

    # ---------- 会话 CRUD ----------
    def create(self, thread_id: str, title: str = "") -> None:
        """创建会话（thread_id 即 LangGraph thread_id）。"""
        now = datetime.now(UTC).isoformat()
        self._execute(
            "INSERT OR IGNORE INTO sessions (id, created_at, updated_at, title) "
            "VALUES (?, ?, ?, ?)",
            (thread_id, now, now, title),  # INSERT OR IGNORE: 已存在则跳过（幂等）
        )

    def get(self, thread_id: str) -> sqlite3.Row | None:
        """按 thread_id 取会话。"""
        return self._fetch_one("SELECT * FROM sessions WHERE id = ?", (thread_id,))

    def delete(self, thread_id: str) -> None:
        """删除会话（同时清掉其消息——外键 ON DELETE 未级联，需手动）。"""
        self._execute("DELETE FROM session_messages WHERE session_id = ?", (thread_id,))
        self._execute("DELETE FROM sessions WHERE id = ?", (thread_id,))

    def touch(self, thread_id: str) -> None:
        """刷新会话更新时间（每次对话结束时调用）。"""
        now = datetime.now(UTC).isoformat()
        self._execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, thread_id))

    def update_title(self, thread_id: str, title: str) -> None:
        """更新会话标题（M2 标题中间件写这里）。"""
        self._execute("UPDATE sessions SET title = ? WHERE id = ?", (title, thread_id))

    # ---------- 消息 ----------
    def add_message(self, session_id: str, role: str, content: str) -> None:
        """追加一条消息记录（user/assistant/tool）。"""
        now = datetime.now(UTC).isoformat()
        self._execute(
            "INSERT INTO session_messages (session_id, role, content, created_at) "
            "VALUES (?, ?, ?, ?)",
            (session_id, role, content, now),
        )

    def list_messages(self, session_id: str) -> list[sqlite3.Row]:
        """按时间顺序列出会话全部消息。"""
        return self._fetch_all(
            "SELECT * FROM session_messages WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        )
