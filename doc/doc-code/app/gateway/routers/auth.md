# gateway/routers/auth.py — auth.py

> **文件路径**: `backend/app/gateway/routers/auth.py`
> **目录位置**: gateway/routers → auth.py
> **职责**: 登录端点（用户名 + 密码 → JWT token，M8 新增）

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
POST /api/auth/login  body{username, password}
  ① 用户名恒定时间比较（防用户枚举时序）
  ② verify_password(pw, stored_hash)   ← 复用 M6 webui/auth.py PBKDF2
  ③ generate_jwt(sub, username, secret) → {token, username, expires_in}
  auth 未配置（app.state.auth_config is None）→ 503 诚实报错
```

**配置装配**（app.py）：

```text
config.yaml auth 段 ──> create_default_app() 的 _load_auth_config()
                     ──> {"username", "password_hash"(明文启动哈希一次), "jwt_secret"}
                     ──> create_app(auth_config=...) → app.state.auth_config
```

## 📤 关键导出

- `router` — `POST /api/auth/login`（前缀 `/api`，挂在 app.py）

## 💡 设计思想

1. **复用核心层组件**：校验用 M6 `webui/auth.py` 的 `verify_password`（PBKDF2 恒定时间比较）+ `generate_jwt`（HS256，7 天 exp）——应用层只做编排，符合 R1（核心层被应用层合法 import）。
2. **统一 401 防枚举**：用户名错误和密码错误返回同一句"用户名或密码错误"，不泄漏"用户是否存在"。
3. **503 诚实报错**：`auth_config is None`（config.yaml 缺 auth 段）时登录不可用，显式 503 而不是假装成功——对齐项目"诚实原则"（声明位置已就位、真实实现后置时如实说明）。
4. **学习版教学选择**：⚠️ 原版 v1.1.0 是 **API token 体系**（`POST /api/auth/token` 直发 token + `GET /api/auth/whoami` 验证，无用户名密码登录）；AgentFlow 用 login/JWT 落地"登录/会话保持"验收点，原版 token 体系列 M8.1 对齐方向。

## 🎯 实用场景

1. 前端 `src/pages/login.js` 登录：`authApi.login(username, password)` → token 落 localStorage → `main.js` 登录态 gate 进主界面。
2. 配置未就绪时（无 auth 段）前端拿到 503，诚实提示"后端未配置登录"而非静默失败。

## 🧩 顺序执行链

```text
request ──> POST /api/auth/login
         ▼ 步骤 1：取 app.state.auth_config
         ├─ 无 → 503（未配置）
         └─ 有 → 步骤 2：用户名 compare_digest 比对
                 ├─ 不等 → 401
                 └─ 等 → 步骤 3：verify_password(pw, hash)
                         ├─ False → 401
                         └─ True  → 步骤 4：generate_jwt(...)
                                    ▼
                                    {token, username, expires_in}（200）
```

## ❓ Q&A / 知识点

**Q: 为什么用户名比对用 `secrets.compare_digest` 而不是 `==`？**
A: `==` 在字符不匹配时立刻返回，攻击者可利用耗时差异枚举用户名；`compare_digest` 恒定时间，防时序侧信道。密码哈希的 `verify_password` 内部同样用 `compare_digest`。

**Q: config.yaml 的 auth.password 是明文，安全吗？**
A: 学习版明文、启动时 `hash_password` 一次（不落盘哈希）。生产做法：预先把 `hash_password('密码')` 的结果填进 password 字段、删除明文行——config.yaml 注释里已写明替换命令。

**Q: 为什么没有 JWT 校验中间件？**
A: M8 验收点只要求"登录/会话保持"成立（登录后 token 存在），"登录后接口强制校验 JWT"是 M8.1 增强——当前所有 API 端点仍未鉴权，文档如实标注。

**Q: 401 和 503 分别表示什么？**
A: 401 = 凭证错（用户名或密码）；503 = 服务端未配置登录能力（auth 段缺失/格式错），属于"能力缺失"而非"凭证被拒"。

## ⚠️ 风险点

1. 明文密码在 config.yaml——生产必须换哈希（文件内注释有命令）
2. `jwt_secret` 默认值 `agentflow-m8-dev-secret`——生产必须显式配置，否则 token 可被伪造
3. 无 JWT 校验中间件（M8.1 增强），当前接口全部开放
4. 503 语义依赖 `auth_config` 装配正确——`_load_auth_config` 异常被吞掉时（`except Exception` → None），登录表现为 503 而非崩溃（符合"诚实"但排查时看 gateway 日志的 warning）

> 页脚：2026-10-17 · M8 前端配套 · 对齐 `evoflow/app/gateway/routers/auth.py`（原版为 API token 体系，学习版裁剪为 login/JWT）
