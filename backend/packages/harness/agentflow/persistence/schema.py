# ============================================================================
# AgentFlow · persistence/schema.py —— 表结构定义
# ----------------------------------------------------------------------------
# 文件: backend/packages/harness/agentflow/persistence/schema.py
# 仿原: evoflow/persistence/schema.py + data_layout.py
#       （原版 data_layout.py 是"数据布局先行"的权威清单；
#        M1 只建会话两张表）
# 里程碑: M1
# ----------------------------------------------------------------------------
# 结构图:
# ┌────────────────────────────────────────────────┐
# │ SCHEMA_SQL（唯一表定义处）                     │
# │   sessions         会话表                      │
# │     id PK / created_at / updated_at / title    │
# │   session_messages 消息表                      │
# │     id PK / session_id FK→sessions             │
# │     role / content / created_at               │
# │   └── 为什么拆表: 会话元信息与消息分开，       │
# │       未来查询各取所需（M7 前端会话列表）       │
# └────────────────────────────────────────────────┘
# ============================================================================
from __future__ import annotations

SCHEMA_SQL = """
-- 会话表：一条记录 = 一个会话（thread）
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,        -- 会话 id（对应 LangGraph thread_id）
    created_at  TEXT NOT NULL,           -- 创建时间（UTC ISO，timestamps.now_utc_iso）
    updated_at  TEXT NOT NULL,           -- 最后更新时间
    title       TEXT DEFAULT ''          -- 会话标题（M2 标题中间件自动生成后写入）
);

-- 消息表：明文消息副本（checkpointer 存的是图状态，这里是业务记录）
CREATE TABLE IF NOT EXISTS session_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,  -- 自增主键
    session_id  TEXT NOT NULL REFERENCES sessions(id),  -- 外键 → 会话
    role        TEXT NOT NULL,           -- user / assistant / tool
    content     TEXT NOT NULL,           -- 消息内容
    created_at  TEXT NOT NULL            -- 创建时间
);
"""
