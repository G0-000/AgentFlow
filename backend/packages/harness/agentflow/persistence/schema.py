# ============================================================================
# AgentFlow · persistence/schema.py —— 表结构定义
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/persistence/schema.py
# 对标来源: evoflow/persistence/schema.py + data_layout.py
#   原版 data_layout.py 是"数据布局先行"的权威清单；M1 只建会话两张表。
# 里程碑: M1
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
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
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 表定义唯一权威来源：bootstrap 直接 executescript(SCHEMA_SQL)。
# 2. 拆表设计：会话元信息与消息分开，列表查询不拖消息内容。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. SCHEMA_SQL: 建表 SQL（sessions + session_messages）
# 🔒 内部私有函数
# 无
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. 改表结构 = 破坏性变更：旧库不迁移，需手动重建或写 migration
# 2. session_messages.session_id 外键 → sessions.id（外键约束依赖 db.py 开启）
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

-- 记忆表（M3）：一条记录 = 一条沉淀下来的用户事实
CREATE TABLE IF NOT EXISTS memories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,  -- 自增主键
    thread_id   TEXT NOT NULL,           -- 来源会话（thread_id）
    content     TEXT NOT NULL,           -- 事实内容（如"用户叫小王"）
    source_role TEXT NOT NULL DEFAULT 'user',  -- 来源角色（user/assistant）
    created_at  TEXT NOT NULL,           -- 沉淀时间
    updated_at  TEXT NOT NULL            -- 更新时间
);
CREATE INDEX IF NOT EXISTS idx_memories_thread ON memories (thread_id);

-- 知识库文档表（M3）：一条记录 = 一个导入的文档
CREATE TABLE IF NOT EXISTS knowledge_docs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,  -- 自增主键
    title       TEXT NOT NULL,           -- 文档标题
    source      TEXT DEFAULT '',         -- 来源（文件名/URL）
    created_at  TEXT NOT NULL            -- 导入时间
);

-- 知识库分块表（M3）：一条记录 = 一个分块 + 其向量
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,  -- 自增主键
    doc_id      INTEGER NOT NULL REFERENCES knowledge_docs(id),  -- 外键 → 文档
    content     TEXT NOT NULL,           -- 分块文本
    embedding   BLOB,                    -- 向量（JSON 序列化 float 列表）
    created_at  TEXT NOT NULL            -- 分块时间
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON knowledge_chunks (doc_id);

-- 沙箱审计表（M4）：一条记录 = 一次沙箱操作（放行/拦截）
CREATE TABLE IF NOT EXISTS sandbox_audit (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,  -- 自增主键
    thread_id   TEXT NOT NULL DEFAULT '',           -- 来源会话（thread_id）
    subagent_name TEXT NOT NULL DEFAULT '',         -- 操作方（子代理名/工具名）
    action      TEXT NOT NULL,                      -- 操作类型: terminal_run/read_file/write_file/...
    target      TEXT NOT NULL,                      -- 目标（命令或路径）
    allowed     INTEGER NOT NULL,                   -- 1=放行 0=拦截
    reason      TEXT NOT NULL DEFAULT '',           -- 拦截原因/备注
    created_at  TEXT NOT NULL                       -- 记录时间
);
CREATE INDEX IF NOT EXISTS idx_sandbox_audit_thread ON sandbox_audit (thread_id);
"""
