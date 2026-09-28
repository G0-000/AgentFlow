<!-- ============================================================
  AgentFlow doc · 文档注释
  更新时间: 2026-09-28
  维护约定: 本文件内容随里程碑推进更新；接手 AI 先读标题与正文引言。
  关联项目: AgentFlow（仿写 EvoFlow，原版参照 /Users/main/EvoFlow 只读）
================================================================ -->
# persistence 域（实现说明）

> 对应原版：`evoflow/persistence/`。**SQLite 唯一属主**——全项目只有这个域碰数据库。

## 设计原则（照搬原版 R1 精神的本地版）

1. **收口**：所有 SQL 在 persistence 域内；其他模块拿到的是 repo 对象，不是 Connection
2. **表结构先行**：schema.py 是唯一表定义处（对应原版 data_layout.py 的"布局先行"思想）
3. **repo 模式**：每个业务实体一个 `XxxRepository(conn)`，方法 = 该实体的读写操作

## 文件逐个看

### `db.py`
```python
def connect(db_path) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)  # 自动建目录
    conn.row_factory = sqlite3.Row                            # 行可 dict 化
    conn.execute("PRAGMA journal_mode=WAL")                   # WAL：读写不互斥
    conn.execute("PRAGMA foreign_keys=ON")                    # 外键约束
```

### `schema.py`
- `SCHEMA_SQL` 常量：`sessions` + `session_messages` 两张表
- 为什么拆表：会话元信息（标题/时间）与消息（逐条）分开，未来查询各取所需

### `bootstrap.py`
- `init_db(db_path=None)` → 幂等建表（IF NOT EXISTS），返回连接
- cli 启动时调用一次；重复调用安全

### `timestamps.py`
- `now_utc_iso()`：所有落库时间统一 UTC ISO，避免本地时区混入

### `repositories.py` / `session_repositories.py`
```python
class BaseRepository:          # 只持有连接句柄
    def __init__(self, conn): self._conn = conn

class SessionRepository(BaseRepository):
    create(session_id, title)     # INSERT OR IGNORE（幂等）
    get(session_id)               # → dict | None
    add_message(session_id, role, content)
```

## 与原版的差异（明确记录）

| 原版 | 我们 M1 |
|---|---|
| 60 个文件（chat/goal/auth/automation... 各 repo） | 6 个文件，只有 session repo |
| 自研异步 repo + 复杂迁移（bootstrap 还做模型迁移/seed） | 同步 sqlite3，纯建表 |
| checkpoint 状态与业务表共存于同一 DB | 同：checkpointer 用 SqliteSaver 连同一个 agentflow.db |

## 扩展点（后续里程碑）

- M2：title_repositories（会话标题自动生成落库）、tool_result 存储
- M3：memory / knowledge 表 + 向量列（sqlite-vec）
- M4：sandbox_audit（沙箱审计，仿原版 sandbox_audit_repositories）
- M5：plan / goal / task 表
- M7：app 层直接通过 repo 提供 REST API（不绕核心层）
