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

## ❓ Q&A

**Q: 删除会话会清掉 LangGraph checkpoint 吗？**
A: M7 裁剪不清 checkpoint 表；恢复对话仍可走 `--thread <id>`。

## ⚠️ 风险点

1. 删除会话不清 checkpoint 表（M7 裁剪）
2. POST 不传 thread_id 时自动生成（os.urandom）
