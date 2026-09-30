# ============================================================================
# AgentFlow · persistence/memory_repositories.py —— 记忆数据访问
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/persistence/memory_repositories.py
# 对标来源: evoflow/persistence/memory_repositories.py（原版记忆分多表多 repo）
#   原版记忆系统复杂（L2/L3/L4 分层、KG、衰减）；M3 简化成
#   【一张 memories 表】存用户事实，够"跨会话记住"的最小闭环。
# 里程碑: M3
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────┐
# │ MemoryRepository(BaseRepository)               │
# │   table_name → "memories"                      │
# │   create(thread_id, content, source_role)      │
# │     → 落一条事实（含时间戳）                   │
# │   recall(thread_id?, limit) → 按时间序取记忆   │
# │     thread_id=None 时跨会话取全部              │
# │     （M3 验收点 1: 新会话也能记得 → 跨会话）   │
# │   count() → 记忆条数（CLI 启动信息用）         │
# └────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 记忆 = 用户事实（明文），不是对话全文——沉淀时已做提取。
# 2. recall 跨会话：thread_id 只是"来源"字段，不是隔离键——
#    这正是"新会话记得旧事实"的实现基础。
# 3. 原版有分层/衰减/合并，M3 全去掉（最小闭环，M5 再学）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. MemoryRepository: 记忆数据访问
# 🔒 内部私有函数
# 无
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. recall 默认跨会话返回；若未来要"仅本会话记忆"，加 thread_id 过滤即可
# 2. 记忆去重（同内容不重复落）由 consolidate 层负责，repo 不判重
# ============================================================================

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from agentflow.persistence.repositories import BaseRepository


class MemoryRepository(BaseRepository):
    """memories 表数据访问（记忆 = 沉淀后的用户事实）。"""

    @property
    def table_name(self) -> str:
        return "memories"

    def create(self, thread_id: str, content: str, source_role: str = "user") -> None:
        """沉淀一条记忆（事实已由 consolidate 提取好，这里只管落库）。"""
        now = datetime.now(UTC).isoformat()
        self._execute(
            "INSERT INTO memories (thread_id, content, source_role, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (thread_id, content, source_role, now, now),
        )

    def recall(self, thread_id: str | None = None, limit: int = 10) -> list[sqlite3.Row]:
        """取记忆（默认跨会话，按时间倒序取最新 limit 条）。

        参数:
            thread_id: None = 全部会话（验收点 1 的关键：新会话也能取到旧事实）
            limit: 最多返回条数
        """
        if thread_id:
            return self._fetch_all(
                "SELECT * FROM memories WHERE thread_id = ? ORDER BY created_at DESC LIMIT ?",
                (thread_id, limit),
            )
        return self._fetch_all(
            "SELECT * FROM memories ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )

    def count(self) -> int:
        """记忆总条数（CLI 启动信息展示）。"""
        row = self._fetch_one("SELECT COUNT(*) AS n FROM memories")
        return int(row["n"]) if row else 0

    def get(self, row_id: str) -> sqlite3.Row | None:  # pragma: no cover - 未用
        """按主键取一条记忆。"""
        return self._fetch_one("SELECT * FROM memories WHERE id = ?", (int(row_id),))

    def delete(self, row_id: str) -> None:  # pragma: no cover - 未用
        """删除一条记忆。"""
        self._execute("DELETE FROM memories WHERE id = ?", (int(row_id),))
