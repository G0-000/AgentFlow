# ============================================================================
# AgentFlow · agents/checkpointer/provider.py —— 同步检查点
# ----------------------------------------------------------------------------
# 文件: backend/packages/harness/agentflow/agents/checkpointer/provider.py
# 仿原: evoflow/agents/checkpointer/provider.py
# 里程碑: M1
# ----------------------------------------------------------------------------
# 结构图:
# ┌──────────────────────────────────────────────┐
# │ create_sqlite_checkpointer(db_path)          │
# │   conn = sqlite3.connect(db_path,            │
# │           check_same_thread=False)           │
# │   return SqliteSaver(conn)                   │
# │                                              │
# │ 注意: 3.x 的 from_conn_string() 返回上下文   │
# │      管理器（with 才拿到实例），不适合此处； │
# │      直接构造 SqliteSaver(conn) 更简单。     │
# │                                              │
# │ 用法（agent.py）:                             │
# │   create_agent(..., checkpointer=checkpointer)│
# └──────────────────────────────────────────────┘
# ============================================================================
from __future__ import annotations

import sqlite3

# SqliteSaver: langgraph-checkpoint-sqlite 官方同步检查点实现
# 每步自动把图状态序列化存入 SQLite（无需手写存取）
from langgraph.checkpoint.sqlite import SqliteSaver


def create_sqlite_checkpointer(db_path: str) -> SqliteSaver:
    """创建同步 SQLite 检查点。

    参数:
        db_path: SQLite 文件路径（建议与业务库同一个 data/agentflow.db）

    返回:
        SqliteSaver: 传给 create_agent 的 checkpointer

    实现说明:
        - 直接 SqliteSaver(conn) 构造（3.x 的 from_conn_string 返回
          上下文管理器，需 with 才能用，不适合这里）
        - check_same_thread=False: langgraph 内部线程池可能跨线程
          访问连接，SQLite 串行化由 WAL + 短事务保证
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    return SqliteSaver(conn)
