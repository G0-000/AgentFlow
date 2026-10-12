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
3. **入口视角（本包是"通用门卫"）**：谁进门都过这把锁——M7 Gateway API 是主要挂点、
   飞书回调候选、CLI 本机信任不鉴权；职责边界 = 入口负责接、authz 负责验（你是谁/能不能进）、
   业务负责干。鉴权（authz）与第三方平台适配（community/）是两回事，别混。

## ⚠️ 风险点

1. 勿在此放业务逻辑（保持包入口纯净）

---
_2026-10-05 M6 新增：目录 + 结构图 + 流程图 + 成块代码解析（参数逐条表）+ Q&A。_
_2026-10-12 补充：实用场景 #3——入口视角（通用门卫：API 主挂点/飞书候选/CLI 不鉴权；与 community/ 平台适配区分）。_
