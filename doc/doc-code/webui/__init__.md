# webui/__init__.py — __init__.py

> **文件路径**: `backend/packages/harness/agentflow/webui/__init__.py`
> **目录位置**: webui → __init__.py
> **职责**: Web UI 域包入口（登录鉴权 + 守卫中间件，M6）

## 📋 结构图

```text
（无复杂调用图）
```

## 📤 关键导出

（无顶层导出，见各子模块）

- `webui/auth.py` → `hash_password` / `verify_password` / `generate_jwt` / `verify_jwt`
- `webui/middleware.py` → `WebuiAuthGuard`（public 白名单 + JWT 校验 + 401 语义）

## 💡 设计思想

1. 只做统一导出/包声明，不承载业务逻辑。
2. 鉴权分两层：auth（PBKDF2 哈希 + JWT 纯函数）→ middleware（白名单/放行/拒绝判定）。

## 🎯 实用场景

1. 登录建号：hash_password 落自含格式，登录 verify_password 后 generate_jwt 发 token
2. 请求守卫：WebuiAuthGuard.check 判定放行/401，require_api 抛 AuthRequiredError

## ⚠️ 风险点

1. 勿在此放业务逻辑（保持包入口纯净）
2. JWT secret 泄漏即失守；白名单 `/` 与 `/static` 需确认不误放行敏感页

---
_2026-10-05 M6 新增：目录 + 结构图 + 流程图 + 成块代码解析（参数逐条表）+ Q&A。_
