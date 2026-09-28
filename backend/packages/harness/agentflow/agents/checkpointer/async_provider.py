# ============================================================================
# AgentFlow · agents/checkpointer/async_provider.py —— 异步 SQLite 检查点
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/agents/checkpointer/async_provider.py
# 对标来源: evoflow/agents/checkpointer/async_provider.py
# 里程碑: M1（建好对齐结构，M7 gateway 才真正使用）
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
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
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 异步检查点基于 aiosqlite，为 M7 gateway（FastAPI async 端点）预留。
# 2. 与 provider.py 同步版并存：CLI 用同步，gateway 用异步，互不干扰。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. create_async_sqlite_checkpointer: 建异步 SQLite 检查点
# 🔒 内部私有函数
# 无
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. 返回的 saver 需 await setup() 初始化表（同步版无需）
# 2. M1-M6 不使用此文件，勿在 CLI 误用（会缺初始化步骤）
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
