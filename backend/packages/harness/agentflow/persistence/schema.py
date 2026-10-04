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

-- 长任务表（M5）：一行 = 一个长任务尝试（goal + 步骤计划 JSON 同行）
CREATE TABLE IF NOT EXISTS goals (
    goal_id          TEXT PRIMARY KEY,           -- g_ + urandom(6).hex()
    thread_id        TEXT NOT NULL,              -- 归属会话（--thread 恢复定位键）
    goal_text        TEXT NOT NULL,              -- 用户原始长任务描述
    goal_status      TEXT NOT NULL DEFAULT 'pending',
        -- pending/planning/planned/executing/paused/completed/failed/cancelled
    current_step     TEXT NOT NULL DEFAULT '',   -- 正在执行的 step.ref（断点坐标）
    plan_steps_json  TEXT NOT NULL DEFAULT '[]', -- JSON 数组[PlanStep]（含每步 status）
    max_steps        INTEGER NOT NULL DEFAULT 12,
    completed_steps  INTEGER NOT NULL DEFAULT 0,
    last_error       TEXT NOT NULL DEFAULT '',
    stop_reason      TEXT NOT NULL DEFAULT '',   -- max_steps/judge_fallback/...
    summary          TEXT NOT NULL DEFAULT '',   -- 最终汇总报告（complete 时写）
    outcome          TEXT NOT NULL DEFAULT '',   -- done/failed/...
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_goals_thread ON goals (thread_id);
CREATE INDEX IF NOT EXISTS idx_goals_status ON goals (goal_status);

-- 定时任务定义表（M5）：一行 = 一条 automation
CREATE TABLE IF NOT EXISTS automations (
    task_id        TEXT PRIMARY KEY,             -- t_ + urandom(6).hex()
    name           TEXT NOT NULL DEFAULT '',
    prompt         TEXT NOT NULL,                -- 到点投递的提示词
    schedule       TEXT NOT NULL,                -- 归一化后 cron 5 字段 "m h dom mon dow"
    schedule_type  TEXT NOT NULL DEFAULT 'recurring',  -- recurring | once
    scheduled_at   TEXT,                         -- once 型目标时间（ISO）
    status         TEXT NOT NULL DEFAULT 'active',     -- active | paused
    once_fired     INTEGER NOT NULL DEFAULT 0,
    last_run       TEXT,
    last_status    TEXT NOT NULL DEFAULT '',
    run_count      INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_automations_status ON automations (status);

-- 定时任务执行历史表（M5，M5 唯一保留的事件历史）
CREATE TABLE IF NOT EXISTS automation_runs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id          TEXT NOT NULL,
    run_id           TEXT NOT NULL,
    started_at       TEXT NOT NULL,
    finished_at      TEXT,
    status           TEXT NOT NULL DEFAULT 'running',  -- running|success|failed
    output           TEXT NOT NULL DEFAULT '',
    error            TEXT NOT NULL DEFAULT '',
    duration_seconds REAL
);
CREATE INDEX IF NOT EXISTS idx_automation_runs_task ON automation_runs (task_id);
"""
