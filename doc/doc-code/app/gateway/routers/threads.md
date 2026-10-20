# gateway/routers/threads.py — threads.py

> **文件路径**: `backend/app/gateway/routers/threads.py`
> **目录位置**: gateway/routers → threads.py
> **职责**: 会话(threads) CRUD API（创建/列表/删除）

## 📑 目录

- [📋 结构图 / 思维图](#📋-结构图--思维图)
- [📤 关键导出](#📤-关键导出)
- [💡 设计思想](#💡-设计思想)
- [🎯 实用场景](#🎯-实用场景)
- [🧩 顺序执行链](#🧩-顺序执行链)
- [❓ Q&A](#❓-qa)
- [⚠️ 风险点](#⚠️-风险点)

## 📋 结构图 / 思维图

```text
router(prefix="/api", tags=["threads"])
  POST   /api/threads             → 建会话（可指定 id/标题）
  GET    /api/threads            → 列出全部会话
  DELETE /api/threads/{thread_id} → 删会话（连带消息）

存储: request.app.state.sessions (SessionRepository)
```

## 📤 关键导出

**router** — `threads.router`

## 💡 设计思想

1. **会话即 LangGraph thread_id**：创建会话 = sessions 表插一行（幂等 INSERT OR IGNORE）。
2. **删除连带消息**：repo.delete 已手动删 session_messages（外键未级联）。
3. **列表查询走 sessions repo 自己的连接**（不裸连，复用 persistence.db 配置）。

## 🎯 实用场景

1. 前端会话侧栏：GET /api/threads 列出历史会话
2. 新建会话：POST /api/threads（或由 POST /api/runs 隐式建）
3. 删除会话：DELETE /api/threads/{id}

## 🧩 顺序执行链

**创建链**：

```text
request: POST /api/threads {thread_id?, title?}
   ▼  create_thread(request, body)
   ▼  thread_id = body.thread_id or 自动生成
   ▼  sessions.create(thread_id, title)        ← 幂等
   ▼  return 201 {thread_id, title, created_at, updated_at}
```

## 🧩 代码解析（成块对照 threads.py）

### 块 0：头部装配 —— router / ThreadCreate / _row_to_dict

```python
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api", tags=["threads"])   # 挂在 /api，端点 /api/threads/*

class ThreadCreate(BaseModel):
    """创建会话请求体（都可选）。"""
    thread_id: str | None = Field(default=None, description="指定会话 id；缺省自动生成")
    title: str = Field(default="", description="会话标题")

def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "thread_id": row["id"],
        "title": row["title"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
```

**关键点**：

- **`ThreadCreate`** — 请求体模型：`thread_id`/`title` **都可选**（会话可空创建）——与 runs 的 `RunCreate`（message 必填）相反：会话本身没有必填业务字段。
- **`_row_to_dict`** — SQLite row → JSON dict 的唯一映射点：只暴露前端需要的 4 字段（thread_id/title/created_at/updated_at），不泄露内部列。三个端点共用它（创建/列表）。
- **`sqlite3.Row` 按下标/列名双通道访问**：`row["id"]` 是列名索引（Row 支持），`id` 列在 sessions 表里就是 thread_id 的物理名——映射层把物理名翻译成 API 名。

### 块 1：`create_thread` —— 会话即 LangGraph thread_id

```python
@router.post("/threads", status_code=201)
async def create_thread(request: Request, body: ThreadCreate) -> dict:
    sessions = request.app.state.sessions
    thread_id = body.thread_id or os.urandom(8).hex()
    sessions.create(thread_id, title=body.title)
    row = sessions.get(thread_id)
    return _row_to_dict(row)  # type: ignore[arg-type]
```

**关键点**：

- **会话 = LangGraph thread_id**：`sessions.create` 在 `sessions` 表插一行（`INSERT OR IGNORE` 幂等——同一 thread_id 重复 POST 不炸，返回已存在行）。
- **thread_id 缺省自动生成**：`os.urandom(8).hex()` = 16 位随机 hex——与 runs 的 thread_id 生成逻辑一致（`POST /api/runs` 里也是这行）。
- **`sessions.get(thread_id)` 再取回**：`create` 可能命中幂等分支（已存在），所以**不信任 create 的返回值**，统一 GET 拿权威行。
- `_row_to_dict` 只暴露前端需要的字段（thread_id/title/created_at/updated_at），不泄露内部列。

### 块 2：`list_threads` + `delete_thread`

```python
@router.get("/threads")
async def list_threads(request: Request) -> dict:
    sessions = request.app.state.sessions
    rows = sessions.conn.execute("SELECT * FROM sessions ORDER BY updated_at DESC").fetchall()
    return {"threads": [_row_to_dict(r) for r in rows], "total": len(rows)}

@router.delete("/threads/{thread_id}")
async def delete_thread(request: Request, thread_id: str) -> dict:
    sessions = request.app.state.sessions
    sessions.delete(thread_id)
    return {"deleted": thread_id}
```

**关键点**：

- **`sessions.conn.execute` 直接查**：`SessionRepository` 暴露了 `conn`（线程本地连接属性），列表查询不额外加 repo 方法——"读"直接走连接，"写"走 repo 方法（写有业务逻辑：幂等/连带删除）。
- **`ORDER BY updated_at DESC`**：会话按最近活跃倒序——前端侧栏"最近会话"直接用它。
- **`sessions.delete` 连带清消息**：repo.delete 手动 `DELETE FROM session_messages WHERE thread_id=...`（外键未级联，手动补）。**但不清 LangGraph checkpoint 表**——M7 裁剪取舍。

## ❓ Q&A / 知识点

**Q: 删除会话会清掉 LangGraph checkpoint 吗？**
A: 不会（M7 裁剪）。`sessions.delete` 只清 `sessions` + `session_messages` 两张业务表；LangGraph checkpoint 表（`checkpoints`/`checkpoint_writes`）由 checkpointer 独立管理，不在 gateway 会话 API 的范围内。恢复对话仍可走 CLI `--thread <id>`（checkpoint 还在，图状态可恢复）。

**Q: 为什么 `sessions.create` 幂等（INSERT OR IGNORE），而不是先查后插？**
A: 并发安全：先查后插（`if not exists: insert`）在并发下仍有竞态（两请求同时查到不存在 → 都插 → 主键冲突炸）。`INSERT OR IGNORE` 是**数据库级别的原子幂等**——同 key 重复插入静默跳过，无竞态。代价：无法区分"新建成功"与"已存在"（所以 `create` 后必须 `get` 取回）。

**Q: thread_id 与会话 API、runs API、checkpoint 三者什么关系？**
A: 同一把钥匙三种用途：① `sessions` 表（业务会话记录 + 明文消息，gateway 可删）；② LangGraph checkpoint（图状态/多轮上下文，CLI/gateway 共用）；③ runs 的 `thread_id` 字段（POST /api/runs 复用）。前端新建会话 → POST /api/threads 拿到 thread_id → POST /api/runs 传同一 thread_id 续上下文。

## ⚠️ 风险点

1. 删除会话不清 checkpoint 表（M7 裁剪；恢复对话仍可走 `--thread <id>`）
2. POST 不传 thread_id 时自动生成（os.urandom 16 hex），无法由客户端预知——前端若需稳定 id 必须显式传
3. 列表查询直接走 `sessions.conn`（绕过 repo 封装）——若未来 sessions 换存储（非 SQLite），此处要同步改

> 页脚：2026-10-20 · M7 Gateway 核心 · 对齐 `evoflow/gateway/routers/threads.py`（裁剪；10-20 补块 0 头部装配：ThreadCreate/_row_to_dict）
