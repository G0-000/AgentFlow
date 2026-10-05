# authz/__init__.py — __init__.py

> **文件路径**: `backend/packages/harness/agentflow/authz/__init__.py`
> **目录位置**: authz → __init__.py
> **职责**: 鉴权守卫包入口（M6：JWT 401 语义）

## 📋 结构图

```text
（无复杂调用图）
```

## 📤 关键导出

（无顶层导出，见结构图）

## 💡 设计思想

1. 只做包声明，不承载业务逻辑；Bearer JWT 守卫在 `authz/http_guard.py`，
   JWT 签发/校验与 PBKDF2 密码哈希在 `webui/auth.py`。

## 🎯 实用场景

1. API 鉴权场景：require_api_auth 校验 Bearer JWT，无效抛 AuthRequiredError（401 语义）
2. 可选身份场景：resolve_auth_from_headers 只解析不抛错，None 即匿名

## ⚠️ 风险点

1. 勿在此放业务逻辑（保持包入口纯净）

---
_2026-10-05 M6 新增：目录 + 结构图 + 流程图 + 成块代码解析（参数逐条表）+ Q&A。_
