# gateway/routers/models.py — models.py

> **文件路径**: `backend/packages/harness/agentflow/gateway/routers/models.py`
> **目录位置**: gateway/routers → models.py
> **职责**: 模型管理 API（列表/创建/详情/PATCH/删除）

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
router(prefix="/api", tags=["models"])
  GET    /api/models          → list_all()
  POST   /api/models          → create()
  GET    /api/models/{name}   → get()
  PATCH  /api/models/{name}   → update() + 可选 is_primary
  DELETE /api/models/{name}   → delete()

存储: request.app.state.model_store (ModelStore, SQLite)
```

## 📤 关键导出

**router** — `models.router`

## 💡 设计思想

1. **裁剪对齐**：原版 models 路由 1000+ 行（探针/连接/降级），M7 只做配置 CRUD。
2. **PATCH 传 `is_primary:true` 即切换主模型**——runs 运行时现场读主模型，写 SQLite 后下一次 run 生效（验收点 4）。
3. **api_key 对外打码**：`ModelStore.to_dict(mask_key=True)`，不回显明文。

## 🎯 实用场景

1. 模型面板：增删改查模型连接
2. 切换对话模型：PATCH `{is_primary:true}`，下一次对话即用新模型（不重启）

## 🧩 顺序执行链

**创建模型链**：

```text
request: POST /api/models {name,model,api_key,...}
   ▼  create_model(request, body)
   ▼  store.create(...)                       ← 同名已存在 → ValueError → 409
   ▼  首个模型自动 is_primary=1
   ▼  return 201 to_dict(row)（api_key 打码）
```

**切换主模型链**：见 model_store.md 的顺序执行链（PATCH → set_primary → runs 现场读）。

## ❓ Q&A

**Q: 重复创建同名模型返回什么？**
A: 409 Conflict；更新/删除不存在返回 404。

## ⚠️ 风险点

1. `/api/models/{name}` 是动态段，勿在其前再定义 `/api/models/xxx` 静态段
2. PATCH 先改字段再独立处理 `is_primary`（两步解耦）
