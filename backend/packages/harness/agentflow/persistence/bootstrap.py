# ============================================================================
# AgentFlow · persistence/bootstrap.py —— 幂等建表
# ----------------------------------------------------------------------------
# 文件: backend/packages/harness/agentflow/persistence/bootstrap.py
# 仿原: evoflow/persistence/bootstrap.py
# 里程碑: M1
# ----------------------------------------------------------------------------
# 结构图:
# ┌──────────────────────────────────────────────┐
# │ init_db(db_path)                             │
# │   ① connect(db_path)  （db.py 统一配置）      │
# │   ② executescript(SCHEMA_SQL) 建表           │
# │   ③ commit                                   │
# │   ④ return conn（调用方可继续使用）           │
# │   └── 幂等: CREATE TABLE IF NOT EXISTS       │
# │       重复调用不会报错                        │
# └──────────────────────────────────────────────┘
# ============================================================================
from __future__ import annotations

import sqlite3

from agentflow.persistence.db import connect
from agentflow.persistence.schema import SCHEMA_SQL


def init_db(db_path: str) -> sqlite3.Connection:
    """初始化数据库（建表）并返回连接。

    参数:
        db_path: 数据库文件路径

    返回:
        已建表的连接（cli 等调用方直接复用）

    设计说明: 所有表定义集中在 schema.py，此处只执行——
    以后加表（M3 记忆表 / M5 任务表）只需改 schema.py，不动这里。
    """
    conn = connect(db_path)      # ① 统一连接配置
    conn.executescript(SCHEMA_SQL)  # ② 一次执行全部建表语句
    conn.commit()                 # ③ 落盘
    return conn                   # ④ 返回给调用方
