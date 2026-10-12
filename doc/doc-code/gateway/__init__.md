# gateway/__init__.py — __init__.py

> **文件路径**: `backend/packages/harness/agentflow/gateway/__init__.py`
> **目录位置**: gateway → __init__.py
> **职责**: 应用层网关包入口（REST/SSE API + 模型 SQLite 管理）

## 📋 结构图 / 思维图

```text
gateway/（M7 新增）
  app.py            应用工厂 create_app / create_default_app
  model_store.py    模型配置 SQLite 存储
  sse.py            SSE 流式（delta/done/error）
  routers/          models / runs / threads 三路由
```

## 📤 关键导出

见 `app.py`：`create_app` / `create_default_app`。

## 💡 设计思想

1. 只做包声明，不承载业务逻辑；统一入口是 `app.create_app`。

## ⚠️ 风险点

1. 勿在此放业务逻辑（保持包入口纯净）
