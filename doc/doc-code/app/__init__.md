# app/__init__.py — __init__.py

> **文件路径**: `backend/app/__init__.py`
> **目录位置**: app → __init__.py
> **职责**: 应用层包入口（M7：Gateway API + IM 渠道，对齐原版 backend/app）

## 📋 结构图

```text
app/（应用层）
├── gateway/   FastAPI 网关（REST/SSE + 模型管理）
└── channels/  IM 渠道桥接（飞书先发）
```

## 📤 关键导出

（无顶层导出——子包各自导出：`gateway.create_app` / `channels.FeishuChannel` 等）

## 💡 设计思想

1. **对齐原版 backend/app 分层**：应用层（gateway + channels）与核心层（agentflow/
   其余包）分离；应用层只做"接入口 + 装配"，业务逻辑在核心层。
2. 只做包声明，不承载业务逻辑；统一入口见 `app.gateway.app.create_app`。

## 🎯 实用场景

1. 应用层统一落点：所有"对外的入口"（HTTP API、IM 渠道）都在这里，
   与核心层（agents/config/persistence 等）隔离——改入口不动核心。
2. 读代码路径：找"对外能力"先看 `app/gateway/`（API）与 `app/channels/`（渠道）。

## ⚠️ 风险点

1. 保持包入口纯净，勿放业务逻辑（子包各自承载）

---
_2026-10-13 新建：应用层 app/ 包入口文档（M7 gateway+channels 迁入，对齐原版 backend/app）。_
