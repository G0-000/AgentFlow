# ============================================================================
# AgentFlow · observability/store.py —— 可观测 SQLite 存储（M6）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/observability/store.py
# 对标来源: evoflow/observability/sqlite_store.py（885 行裁剪：只留 runs + trace_events
#   两表的建表/insert/查询，砍 8 表 schema 升级/thinking 索引/复杂查询）
# 里程碑: M6
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────────────┐
# │ ObsTraceStore(sqlite_path)                                 │
# │   ├─ create_tables(): runs + trace_events 两表（幂等）     │
# │   ├─ insert_run(run_id, thread_id, started_at, ...)        │
# │   ├─ insert_event(run_id, kind, span_name, started_at,     │
# │   │               duration_ms, meta_json, status)          │
# │   ├─ get_run(run_id) → run dict | None                    │
# │   └─ query_events(run_id) → [span dict]（按 started_at）  │
# └────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 独立数据库（默认 data/obs.db）：可观测数据与业务库分离——
#    业务库坏了不影响观测，观测库膨胀可整体删（M6 不做归档）。
# 2. run 是根、event 是 span：一次对话 = 1 run + N events（模型调用/工具调用/
#    中间件），按 run_id 一查即得完整链路（验收点 4）。
# 3. meta_json 存 JSON 文本（span 细节），查询层再解析——列模型最小化。
# 4. row_factory=Row：查询返回 dict 形状，上层不用记列序。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出】
# 1. ObsTraceStore: 可观测存储类（建表/写入/查询）
# ----------------------------------------------------------------------------

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from agentflow.observability.tables import ObservabilityTable


class ObsTraceStore:
    """可观测链路存储（SQLite）。

    runs: 一次对话/一次请求的根记录（run_id/thread_id/started_at/duration_ms/status）
    trace_events: 该 run 下的 span 明细（kind/span_name/started_at/duration_ms/meta/status）
    """

    def __init__(self, sqlite_path: str | Path) -> None:
        self._path = Path(sqlite_path)
        # P-018 教训：线程本地连接，绝不跨线程共享 conn
        # （recorder 的 fire-and-forget 在后台线程写库，共享主线程 conn 会撞
        #   SQLite check_same_thread 限制）
        self._local = threading.local()

    def _connection(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self._path), timeout=10)
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
            self._create_tables(conn)  # 每个线程首次连接自动建表（幂等）
        return conn

    def _create_tables(self, conn: sqlite3.Connection) -> None:
        """建表 SQL（对给定连接执行）。幂等。"""
        conn.executescript(
            f"""
            CREATE TABLE IF NOT EXISTS {ObservabilityTable.RUNS} (
                run_id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                started_at TEXT NOT NULL,
                duration_ms REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'ok'
            );
            CREATE TABLE IF NOT EXISTS {ObservabilityTable.TRACE_EVENTS} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                span_name TEXT NOT NULL,
                started_at TEXT NOT NULL,
                duration_ms REAL NOT NULL DEFAULT 0,
                meta_json TEXT NOT NULL DEFAULT '{{}}',
                status TEXT NOT NULL DEFAULT 'ok'
            );
            CREATE INDEX IF NOT EXISTS idx_obs_events_run
                ON {ObservabilityTable.TRACE_EVENTS}(run_id, started_at);
            """
        )
        conn.commit()

    def create_tables(self) -> None:
        """公开建表入口（幂等）。内部各方法首次访问连接时也会自动建表。"""
        self._create_tables(self._connection())

    def insert_run(
        self,
        *,
        run_id: str,
        thread_id: str,
        started_at: str,
        duration_ms: float = 0.0,
        status: str = "ok",
    ) -> None:
        """写一条 run（根记录）。"""
        conn = self._connection()
        conn.execute(
            f"INSERT OR REPLACE INTO {ObservabilityTable.RUNS}"
            "(run_id, thread_id, started_at, duration_ms, status) VALUES (?,?,?,?,?)",
            (run_id, thread_id, started_at, duration_ms, status),
        )
        conn.commit()

    def insert_event(
        self,
        *,
        run_id: str,
        kind: str,
        span_name: str,
        started_at: str,
        duration_ms: float = 0.0,
        meta: dict[str, Any] | None = None,
        status: str = "ok",
    ) -> None:
        """写一条 span（run 下的事件）。kind 如 model_call / tool_call / middleware。"""
        conn = self._connection()
        conn.execute(
            f"INSERT INTO {ObservabilityTable.TRACE_EVENTS}"
            "(run_id, kind, span_name, started_at, duration_ms, meta_json, status)"
            " VALUES (?,?,?,?,?,?,?)",
            (
                run_id,
                kind,
                span_name,
                started_at,
                duration_ms,
                json.dumps(meta or {}, ensure_ascii=False),
                status,
            ),
        )
        conn.commit()

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        """按 run_id 查根记录；不存在 → None。"""
        conn = self._connection()
        row = conn.execute(
            f"SELECT * FROM {ObservabilityTable.RUNS} WHERE run_id = ?", (run_id,)
        ).fetchone()
        return dict(row) if row is not None else None

    def query_events(self, run_id: str) -> list[dict[str, Any]]:
        """按 run_id 查全部 span（按 started_at 升序）——完整链路。"""
        conn = self._connection()
        rows = conn.execute(
            f"SELECT * FROM {ObservabilityTable.TRACE_EVENTS}"
            " WHERE run_id = ? ORDER BY started_at ASC",
            (run_id,),
        ).fetchall()
        events = []
        for row in rows:
            d = dict(row)
            try:
                d["meta"] = json.loads(d.pop("meta_json") or "{}")
            except json.JSONDecodeError:
                d["meta"] = {}
            events.append(d)
        return events

    def close(self) -> None:
        """关闭当前线程的连接（幂等）。其他线程连接随线程消亡由 GC 回收。"""
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None
