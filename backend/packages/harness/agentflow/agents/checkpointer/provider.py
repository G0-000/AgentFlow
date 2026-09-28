# ============================================================================
# AgentFlow · agents/checkpointer/provider.py —— 同步 SQLite 检查点
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/agents/checkpointer/provider.py
# 对标来源: evoflow/agents/checkpointer/provider.py
# 里程碑: M1
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────┐
# │ create_sqlite_checkpointer(db_path)          │
# │   conn = sqlite3.connect(db_path,            │
# │           check_same_thread=False)           │
# │   return SqliteSaver(conn)                   │
# │                                              │
# │ 用法（agent.py）:                             │
# │   create_agent(..., checkpointer=checkpointer)│
# └──────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 3.x 的 from_conn_string() 返回上下文管理器（with 才拿到实例），
#    不适合这里；直接构造 SqliteSaver(conn) 更简单（P-010 教训）。
# 2. 每步自动把图状态序列化存入 SQLite（无需手写存取）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. create_sqlite_checkpointer: 建 SQLite 检查点（thread_id 维度持久化）
# 🔒 内部私有函数
# 无
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. check_same_thread=False 是必须的（CLI 单线程跑，但 langgraph 内部可能跨线程）
# 2. 换异步场景用 async_provider.py，不要改本文件
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
