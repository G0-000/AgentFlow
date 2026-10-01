# ============================================================================
# AgentFlow · persistence/sandbox_audit_repositories.py —— 沙箱审计仓库
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/persistence/sandbox_audit_repositories.py
# 对标来源: 无（M4 新增——沙箱审计是 M4 验收点 4 的可追溯性配套）
# 里程碑: M4
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────────────┐
# │ SandboxAuditRepository(BaseRepository)               │
# │   record(thread_id, subagent_name, action, target,   │
# │          allowed, reason) → 写一条审计               │
# │   query(thread_id=None, limit=100) → 最近审计记录    │
# │   count() → 审计总条数（CLI 启动信息/测试用）        │
# │   表: sandbox_audit（schema.py 定义）                │
# └──────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 每次沙箱操作（放行/拦截）都落库——"谁在什么时候对什么
#    做了什么"全程可追溯（验收点 4 的证明：拦截有据可查）。
# 2. 用 db_path 模式（P-018）：工具在后台线程跑 SQL，
#    线程本地连接，避免 SQLite 跨线程报错。
# 3. allowed 用 INTEGER 而非 BOOLEAN：SQLite 无布尔，0/1 直读。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. SandboxAuditRepository: 沙箱审计数据访问类
# 🔒 内部私有函数
# 无
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. record 是写操作（_execute 自动 commit）
# 2. query 按 thread_id 过滤 + 时间倒序，limit 防全表拉取
# ============================================================================

from __future__ import annotations

from agentflow.persistence.repositories import BaseRepository


class SandboxAuditRepository(BaseRepository):
    """沙箱审计数据访问（sandbox_audit 表）。"""

    @property
    def table_name(self) -> str:
        return "sandbox_audit"

    def record(
        self,
        action: str,
        target: str,
        allowed: bool,
        reason: str = "",
        thread_id: str = "",
        subagent_name: str = "",
    ) -> None:
        """写一条沙箱审计记录（放行/拦截都记）。"""
        self._execute(
            f"INSERT INTO {self.table_name}"
            " (thread_id, subagent_name, action, target, allowed, reason, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                thread_id,
                subagent_name,
                action,
                target[:500],  # 命令/路径截断防脏数据
                1 if allowed else 0,
                reason[:300],
                _now_iso(),
            ),
        )

    def query(self, thread_id: str | None = None, limit: int = 100) -> list[dict]:
        """最近审计记录（可过滤会话；按时间倒序）。"""
        sql = f"SELECT * FROM {self.table_name}"
        params: tuple = ()
        if thread_id:
            sql += " WHERE thread_id = ?"
            params = (thread_id,)
        sql += " ORDER BY id DESC LIMIT ?"
        rows = self._fetch_all(sql, params + (limit,))
        return [dict(r) for r in rows]

    def count(self) -> int:
        """审计总条数（CLI 启动信息 / 测试断言用）。"""
        row = self._fetch_one(f"SELECT COUNT(*) AS n FROM {self.table_name}")
        return int(row["n"]) if row else 0

    # ---- BaseRepository 抽象契约实现（CRUD） ----
    def create(self, **kwargs) -> None:
        """通用创建入口（record 的字典化包装，满足基类契约）。"""
        self.record(
            action=str(kwargs.get("action", "")),
            target=str(kwargs.get("target", "")),
            allowed=bool(kwargs.get("allowed", True)),
            reason=str(kwargs.get("reason", "")),
            thread_id=str(kwargs.get("thread_id", "")),
            subagent_name=str(kwargs.get("subagent_name", "")),
        )

    def get(self, row_id: str) -> object | None:
        """按主键取一条审计记录。"""
        return self._fetch_one(
            f"SELECT * FROM {self.table_name} WHERE id = ?", (row_id,)
        )

    def delete(self, row_id: str) -> None:
        """按主键删除审计记录（清理用）。"""
        self._execute(f"DELETE FROM {self.table_name} WHERE id = ?", (row_id,))


def _now_iso() -> str:
    """当前 UTC 时间（ISO 秒精度，对齐 timestamps 惯例）。"""
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat(timespec="seconds")
