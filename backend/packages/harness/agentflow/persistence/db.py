# ============================================================================
# AgentFlow · persistence/db.py —— SQLite 连接管理
# ----------------------------------------------------------------------------
# 文件: backend/packages/harness/agentflow/persistence/db.py
# 仿原: evoflow/persistence/db.py
# 里程碑: M1
# ----------------------------------------------------------------------------
# 结构图:
# ┌──────────────────────────────────────────────┐
# │ connect(db_path) → sqlite3.Connection        │
# │   ① 自动创建父目录（mkdir parents=True）      │
# │   ② row_factory = Row（行可按列名取值）       │
# │   ③ PRAGMA journal_mode=WAL（读写不互斥）     │
# │   ④ PRAGMA foreign_keys=ON（外键约束生效）    │
# └──────────────────────────────────────────────┘
# ============================================================================
from __future__ import annotations

import sqlite3
from pathlib import Path


def connect(db_path: str) -> sqlite3.Connection:
    """打开 SQLite 连接（带项目级默认配置）。

    参数:
        db_path: 数据库文件路径（如 项目根/data/agentflow.db）

    返回:
        已配置好的 sqlite3.Connection

    细节说明:
        - WAL 模式: 读不阻塞写、写不阻塞读（长任务场景友好）
        - Row 工厂: fetchone() 返回的对象支持 row["列名"] 访问（dict 化方便）
        - 外键: sessions 表与 session_messages 表的 REFERENCES 约束需要它生效
    """
    # ① 自动建目录：data/ 不存在时先创建（幂等）
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    # ② 连接 + 行工厂
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # ③④ PRAGMA（每次连接都要设置，不持久化到文件）
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
