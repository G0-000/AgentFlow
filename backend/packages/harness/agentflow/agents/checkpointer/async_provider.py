# ============================================================================
# AgentFlow · agents/checkpointer/async_provider.py —— 异步检查点
# ----------------------------------------------------------------------------
# 文件: backend/packages/harness/agentflow/agents/checkpointer/async_provider.py
# 仿原: evoflow/agents/checkpointer/async_provider.py
# 里程碑: M1（建好对齐结构，M7 gateway 才真正使用）
# ----------------------------------------------------------------------------
# 结构图:
# ┌──────────────────────────────────────────────┐
# │ async create_async_sqlite_checkpointer(     │
# │         db_path) → AsyncSqliteSaver         │
# │   conn = await aiosqlite.connect(db_path)   │
# │   return AsyncSqliteSaver(conn)             │
# │                                              │
# │ 用法（M7 FastAPI）:                          │
# │   cp = await create_async_sqlite_checkpointer│
# │   await cp.setup()  （一次性初始化表）        │
# └──────────────────────────────────────────────┘
# ============================================================================
from __future__ import annotations

import aiosqlite

# AsyncSqliteSaver: langgraph 官方异步检查点（基于 aiosqlite）
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


async def create_async_sqlite_checkpointer(db_path: str) -> AsyncSqliteSaver:
    """创建异步 SQLite 检查点（M7 gateway 用）。

    参数:
        db_path: SQLite 文件路径

    返回:
        AsyncSqliteSaver（调用方需 await cp.setup() 完成初始化）
    """
    conn = await aiosqlite.connect(db_path)
    return AsyncSqliteSaver(conn)
