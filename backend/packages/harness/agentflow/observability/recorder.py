# ============================================================================
# AgentFlow · observability/recorder.py —— 可观测记录器（M6）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/observability/recorder.py
# 对标来源: evoflow/observability/recorder.py（404 行裁剪：只留 record_run +
#   record_trace_event 两个最小方法 + fire-and-forget 写库语义）
# 里程碑: M6
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────────────┐
# │ ObservabilityRecorder(store)                               │
# │   ├─ record_run(run_id, thread_id, ...)                   │
# │   │     fire-and-forget → store.insert_run                │
# │   └─ record_trace_event(run_id, kind, span_name, ...)     │
# │         fire-and-forget → store.insert_event              │
# │ 使用方: 一次对话开始 record_run，各 span 点 record_event   │
# │ 查询方: store.get_run(run_id) + store.query_events(run_id)│
# └────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. fire-and-forget：观测写入绝不阻塞主流程（模型 invoke 的时延不该等 SQLite 落盘）——
#    单写线程 + 队列，失败只打日志不抛给调用方。
# 2. 调用方零侵入：record_* 只收标量参数，调用方不用 import store/sqlite。
# 3. 可测试：注入内存 store（init_db(":memory:") 同款哲学——sqlite_path=":memory:"）
#    即可断言链路完整。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出】
# 1. ObservabilityRecorder: 记录器（record_run / record_trace_event）
# 2. new_run_id: 生成 run_id（短随机，不暴露请求量）
# ----------------------------------------------------------------------------

from __future__ import annotations

import logging
import os
import threading
from typing import Any

from agentflow.observability.store import ObsTraceStore

logger = logging.getLogger(__name__)


def new_run_id() -> str:
    """生成 run_id：r_ + 6 字节随机 hex（与 thread_id/task_id 同款风格）。"""
    return "r_" + os.urandom(6).hex()


class ObservabilityRecorder:
    """可观测记录器：run 根记录 + span 事件，异步写库（fire-and-forget）。"""

    def __init__(self, store: ObsTraceStore) -> None:
        self._store = store
        self._store.create_tables()

    def record_run(
        self,
        *,
        run_id: str,
        thread_id: str,
        started_at: str,
        duration_ms: float = 0.0,
        status: str = "ok",
    ) -> None:
        """记录一次对话/一次请求（根）。异步落库，失败仅告警。"""
        self._fire(self._store.insert_run, run_id=run_id, thread_id=thread_id,
                  started_at=started_at, duration_ms=duration_ms, status=status)

    def record_trace_event(
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
        """记录一个 span（模型调用/工具调用/中间件）。异步落库。"""
        self._fire(
            self._store.insert_event,
            run_id=run_id,
            kind=kind,
            span_name=span_name,
            started_at=started_at,
            duration_ms=duration_ms,
            meta=meta,
            status=status,
        )

    # ------------------------------------------------------------------
    def _fire(self, fn, **kwargs: Any) -> None:
        """fire-and-forget：后台线程执行写库，异常只打日志。"""
        def _run() -> None:
            try:
                fn(**kwargs)
            except Exception as exc:  # noqa: BLE001 —— 观测失败不干扰主流程
                logger.warning("observability write failed: %s", exc)

        threading.Thread(target=_run, daemon=True).start()
