# ============================================================================
# AgentFlow · persistence/bootstrap.py —— 幂等建表
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/persistence/bootstrap.py
# 对标来源: evoflow/persistence/bootstrap.py
# 里程碑: M1
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────┐
# │ init_db(db_path)                             │
# │   ① connect(db_path)  （db.py 统一配置）      │
# │   ② executescript(SCHEMA_SQL) 建表           │
# │   ③ commit                                   │
# │   ④ return conn（调用方可继续使用）           │
# │   └── 幂等: CREATE TABLE IF NOT EXISTS       │
# │       重复调用不会报错                        │
# └──────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 建表集中一处（schema.py），bootstrap 只负责执行 + 提交。
# 2. 幂等设计：启动/测试多次调用不报错（IF NOT EXISTS）。
# 3. init_db(":memory:") 内存库跑测试（无文件污染）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. init_db: 初始化数据库（建表）并返回连接
# 🔒 内部私有函数
# 无
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. 改 schema.py 的表结构后，旧库不自动迁移（M 后期补 migration）
# 2. 返回的 conn 由调用方负责 close（CLI 进程退出自动释放）
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
