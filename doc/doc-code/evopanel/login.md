# evopanel/src/pages/login.js — login.js（登录页）

> **文件路径**: `evopanel/src/pages/login.js`
> **对标来源**: `EvoFlow/evopanel/src/pages/login.js`（390 行含注册/找回密码；学习版只留账号密码登录 + token 落 localStorage）
> **里程碑**: M8

## 📑 目录

- [📋 结构图 / 思维图](#📋-结构图--思维图)
- [📤 关键导出](#📤-关键导出)
- [💡 设计思想](#💡-设计思想)
- [🎯 实用场景](#🎯-实用场景)
- [🧩 顺序执行链](#🧩-顺序执行链)
- [🧩 代码解析](#🧩-代码解析)
- [❓ Q&A](#❓-qa)
- [⚠️ 风险点](#⚠️-风险点)

## 📋 结构图 / 思维图

```text
renderLogin(container) → 登录卡片（用户名 + 密码 + 错误区 + 登录按钮）

doLogin() → authApi.login(username, password)
  ├─ 成功 → setToken(res.token) → window.location.reload()（main.js gate 重走）
  └─ 失败 → errorEl.textContent = err.message（401/503 的 detail）
Enter 键也触发 doLogin
```

## 📤 关键导出

- `renderLogin(container)` — 渲染登录页

## 💡 设计思想

1. **调 M8 新增端点 `POST /api/auth/login`**（复用 M6 webui/auth.py 的 PBKDF2 校验 + JWT 签发）。
2. **token 是唯一会话凭据**：7 天过期（后端 exp 控制），密码不落前端存储。
3. **成功即 reload**：让 main.js 的登录态 gate 重新走一遍——最简单可靠的切换方式（避免手动切换状态机）。

## 🎯 实用场景

1. 验收点 1/5：登录后进主界面（聊天/模型设置），退出登录（main.js logout 按钮）回登录页。
2. 配置未就绪（无 auth 段）→ 503 detail 显示在错误区，诚实提示。

## 🧩 顺序执行链

```text
用户输入 → 点登录 / 按 Enter
  ▼ doLogin()
  ├─ 清空错误区 + 禁用按钮
  ├─ authApi.login(username.trim(), password)
  │   ├─ 200 → setToken(token) → window.location.reload()
  │   └─ 非 2xx → errorEl = err.message（"用户名或密码错误" / "后端未配置登录"…）
  └─ finally：按钮恢复可用（成功时页面已跳转）
```

## 🧩 代码解析

```js
import { authApi, setToken } from '../lib/api-client.js'   // 数据面统一走 API 封装

export function renderLogin(container) {
  container.innerHTML = `…登录卡片…`          // ① 画卡片：用户名/密码/错误区/登录按钮
  const username = container.querySelector('#login-username')
  const password = container.querySelector('#login-password')
  const errorEl = container.querySelector('#login-error')
  const btn = container.querySelector('#login-btn')

  const doLogin = async () => {
    errorEl.textContent = ''                  // ② 清旧错误 + 禁按钮（防连点）
    btn.disabled = true
    try {
      const res = await authApi.login(username.value.trim(), password.value)
      setToken(res.token)                     // ③ token 落 localStorage
      window.location.reload()                // ④ 重载 → main.js gate 重走 → 主界面
    } catch (err) {
      errorEl.textContent = err.message || '登录失败'   // 后端 detail（401/503）
      btn.disabled = false                    // 失败恢复按钮，可重试
    }
  }
  btn.addEventListener('click', doLogin)
  password.addEventListener('keydown', (e) => { if (e.key === 'Enter') doLogin() })
  username.focus()
}
```

**逐块拆解**：

- **`import { authApi, setToken }`** — 全部网络调用收敛在 api-client.js（`request()` 统一 JSON/token/错误归一）；login.js 只做"收集输入 + 处理结果"。
- **`renderLogin(container)`** — 约定式渲染：main.js 传入 `#app` 容器，页面把自己画进去。卡片用 innerHTML 字符串（纯静态模板，无用户数据注入面）。
- **`doLogin`** — 唯一的业务动作：调 `POST /api/auth/login` → 成功 `setToken` + `reload`；失败把后端 detail（`用户名或密码错误` / `后端未配置登录`）显示到错误区。
- **`btn.disabled = true`** — 请求期间禁用按钮防连点；成功时页面即将 reload 无需恢复，失败才恢复（Q&A 有专问）。
- **Enter 提交** — `password` 输入框 `keydown` 监听，回车等价点击——表单直觉操作。

## ❓ Q&A / 知识点

**Q: 为什么失败时按钮要恢复，成功时不恢复？**
A: 成功时 `reload()` 立即执行，恢复按钮无意义；失败时若不恢复，用户无法重试（必须刷新页面）。

**Q: 为什么 401/503 的 detail 直接显示给用户？**
A: 后端 detail 已是面向用户的文案（"用户名或密码错误"、"后端未配置登录"）——request 封装把 detail 变成 err.message，页面直接展示，不做二次翻译。

## ⚠️ 风险点

1. 无 JWT 校验中间件（M8.1）——登录只是"前端有 token"，接口本身全开放
2. localStorage 存储 token——生产 XSS 面（M8.1 可换 HttpOnly cookie）
3. 密码输入无前端校验（空密码也提交，后端 401 兜底）

> 页脚：2026-10-20 · M8 登录页 · 对标 `EvoFlow/evopanel/src/pages/login.js`（学习版裁剪；10-20 补 🧩 代码解析）
