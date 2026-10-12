# gateway/routers/__init__.py — __init__.py

> **文件路径**: `backend/packages/harness/agentflow/gateway/routers/__init__.py`
> **目录位置**: gateway/routers → __init__.py
> **职责**: 路由包子入口（models / runs / threads 三个 router）

## 📋 结构图 / 思维图

```text
routers/（M7 只做 3 个；原版 60+）
  models.py   → models.router   模型增删改查
  runs.py     → runs.router     发起/查状态/SSE 流式
  threads.py  → threads.router 会话 CRUD
```

## 📤 关键导出

见各子模块 `router`（自带 `prefix="/api"`，由 `app.py` include_router 挂载）。

## 💡 设计思想

1. 只做包声明，不承载业务逻辑。
2. 各 router 自带 `/api` 前缀，挂载即生效。

## ⚠️ 风险点

1. 勿在此放业务逻辑（保持包入口纯净）
