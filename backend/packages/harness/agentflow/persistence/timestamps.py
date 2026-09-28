# ============================================================================
# AgentFlow · persistence/timestamps.py —— 统一时间戳
# ----------------------------------------------------------------------------
# 文件: backend/packages/harness/agentflow/persistence/timestamps.py
# 仿原: evoflow/persistence/timestamps.py
# 里程碑: M1
# ----------------------------------------------------------------------------
# 结构图:
# ┌──────────────────────────────────────────────┐
# │ now_utc_iso() → str                          │
# │   datetime.now(timezone.utc)                 │
# │     .isoformat() → "2026-09-28T15:00:00.123Z"│
# │   设计动机: 全库统一 UTC ISO 字符串，        │
# │   避免各模块自己格式化（时区/格式漂移）       │
# └──────────────────────────────────────────────┘
# ============================================================================
from __future__ import annotations

from datetime import UTC, datetime


def now_utc_iso() -> str:
    """返回当前 UTC 时间的 ISO 字符串（全库唯一时间戳来源）。

    注意: 存 UTC，显示时由展示层转本地时区（M8 前端处理）。
    """
    return datetime.now(UTC).isoformat()
