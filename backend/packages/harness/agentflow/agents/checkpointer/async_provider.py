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

import contextlib
from collections.abc import AsyncIterator

import aiosqlite

# AsyncSqliteSaver: langgraph 官方异步检查点（基于 aiosqlite）
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

# 追加（对齐审计 #4）：make_checkpointer 落库位置取默认数据路径
from agentflow.config.paths import default_db_path


async def create_async_sqlite_checkpointer(db_path: str) -> AsyncSqliteSaver:
    """创建异步 SQLite 检查点（M7 gateway 用）。

    参数:
        db_path: SQLite 文件路径

    返回:
        AsyncSqliteSaver（调用方需 await cp.setup() 完成初始化）
    """
    conn = await aiosqlite.connect(db_path)
    return AsyncSqliteSaver(conn)


# ----------------------------------------------------------------------------
# 追加（对齐审计 #4）：LangGraph Server checkpointer 工厂入口
# ----------------------------------------------------------------------------
# 对标 evoflow/agents/checkpointer/async_provider.py:make_checkpointer。
# LangGraph CLI 通过 langgraph.json 的 checkpointer.path 定位本工厂。
# 偏差: AgentFlow 无 config.yaml checkpointer 多后端（memory/sqlite/postgres）
#       开关，本工厂固定落默认 SQLite（default_db_path()）；签名仍为无参
#       async context manager（与原版一致），差异仅在不读 app_config。


@contextlib.asynccontextmanager
async def make_checkpointer() -> AsyncIterator[AsyncSqliteSaver]:
    """异步 checkpointer 工厂（LangGraph Server 入口，无参 async context manager）。

    用法（FastAPI lifespan / langgraph dev）::

        async with make_checkpointer() as checkpointer:
            ...  # 图运行期持有 checkpointer

    - 连接进入时打开、退出时关闭（无全局状态，对齐原版生命周期）。
    - 落库路径取 config.paths.default_db_path()（项目根/data/agentflow.db），
      父目录缺失自动创建。
    - 与 create_async_sqlite_checkpointer(db_path) 并存：后者是 M7 gateway
      显式传路径的底层原语；本工厂是对齐原版"无参入口"的声明包装。
    """
    import pathlib

    db_path = default_db_path()
    parent = pathlib.Path(db_path).parent
    parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(db_path)
    try:
        saver = AsyncSqliteSaver(conn)
        await saver.setup()  # 建表（异步 saver 必须显式 setup）
        yield saver
    finally:
        await conn.close()
