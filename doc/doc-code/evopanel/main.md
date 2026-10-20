# evopanel/src/main.js — main.js（应用入口）

> **文件路径**: `evopanel/src/main.js`
> **对标来源**: `EvoFlow/evopanel/src/main.js` + `router.js`（"每页一个 render()"约定）
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
boot()（模块加载即执行）
  ├─ getToken() 有 → buildShell()
  │   ├─ 顶栏：brand + tabs（聊天/模型设置）+ 退出登录
  │   └─ switchTab('chat') → cleanup?.() → renderChat(main)
  │       switchTab('models') → cleanup?.() → renderModels(main)
  └─ 无 token → renderLogin(app)

退出登录：clearToken() → boot()（回登录页）
```

## 📤 关键导出

- `boot()` — 应用入口（登录态 gate）

## 💡 设计思想

1. **页面模块只导出 `render(container)` 约定**：main.js 持有全局布局（顶栏 + tabs + 内容区），切标签时先调用旧页 cleanup 再挂新页——防事件泄漏/重复绑定。
2. **登录态 gate 在最外层**：token 决定渲染登录页还是主界面；logout 清 token 后重新 boot。
3. **学习版路由**：只有两个 tab（聊天/模型设置）；原版 router.js 有完整路由表（页面 30+），M8.1 精读方向。

## 🎯 实用场景

1. 验收点 1：页面加载 → 登录 → 主界面 tabs 切换。
2. 学习"页面 = render + cleanup"的前端架构约定（对齐原版路由思想）。

## 🧩 顺序执行链

```text
浏览器加载 → import './style.css' + 各页面模块
  ▼ boot()
  ├─ 无 token → renderLogin(app) → 登录成功 reload → 再 boot → buildShell
  └─ 有 token → buildShell()
               ▼ switchTab(name)
               ├─ tabs active 切换
               ├─ cleanup?.()（旧页卸载）
               ├─ main.innerHTML = ''（清空容器）
               └─ renderChat / renderModels（挂新页）
  ▼ 退出登录 → clearToken() → boot()
```

## 🧩 代码解析

```js
import './style.css'
import { getToken, clearToken } from './lib/api-client.js'
import { renderLogin } from './pages/login.js'
import { renderChat } from './pages/chat-react.js'
import { renderModels } from './pages/models.js'

const app = document.getElementById('app')

function buildShell() {
  app.innerHTML = `…顶栏(brand/tabs/退出) + main 内容区…`
  const tabs = app.querySelectorAll('.tabs button')
  const main = app.querySelector('.app-main')
  app.querySelector('.logout').addEventListener('click', () => { clearToken(); boot() })

  let cleanup = null
  const switchTab = (name) => {
    tabs.forEach((b) => b.classList.toggle('active', b.dataset.tab === name))
    cleanup?.()                    // ① 先卸载旧页（防事件泄漏）
    main.innerHTML = ''            // ② 清空容器
    if (name === 'chat') cleanup = renderChat(main)      // ③ 挂新页，拿新 cleanup
    else cleanup = renderModels(main)
  }
  tabs.forEach((b) => b.addEventListener('click', () => switchTab(b.dataset.tab)))
  switchTab('chat')                // 默认进聊天页
}

export function boot() {
  app.innerHTML = ''
  if (getToken()) buildShell()     // 登录态 gate：有 token 主界面
  else renderLogin(app)            // 无 token 登录页
}

boot()                             // 模块加载即启动
```

**逐块拆解**：

- **`const app = document.getElementById('app')`** — 模块级容器引用；`boot()` 里 `innerHTML=''` 清空后重挂，全应用只有一个挂载点。
- **`buildShell()`** — 全局布局（顶栏 + tabs + 内容区）。**`switchTab`** 是前端"路由"：切标签时 `cleanup?.()` 卸载旧页 → 清容器 → 挂新页并保存新 cleanup。`let cleanup` 闭包持有当前页清理函数。
- **`boot()`** — 入口 gate：`getToken()` 决定渲染登录页还是主界面；logout 按钮 `clearToken()` 后重新 `boot()` 回登录页。
- **页面约定** — 每个页面模块只导出 `render(container)`（login 无 cleanup；chat/models 返回 cleanup 供 main 调用）。这是对齐原版"每页一个 render()"的轻量路由。
- **`boot()` 底部直接调用** — 纯浏览器 SPA 无 SSR，模块加载即启动（风险点 3 已注明）。

## ❓ Q&A / 知识点

**Q: 为什么登录成功用 `window.location.reload()` 而不是直接调 `boot()`？**
A: 简单可靠——reload 重置所有模块状态（包括 main.js 顶部的 `app` 引用），避免"旧 render 的事件监听残留 + 新 render 重复绑定"的边界问题。学习版以稳为先。

**Q: renderChat/renderModels 返回的 cleanup 为什么有的为空函数？**
A: 页面内部使用局部变量 + DOM 元素引用（每次 render 重建），无需显式卸载；cleanup 是"约定存在、实现按需"——chat-react 返回空函数占位，将来加事件解绑时填充即可（诚实原则）。

## ⚠️ 风险点

1. 登录后 reload 会丢页面状态（学习版可接受；SPA 内部状态本就不持久）
2. tabs 只有两个——扩展页面时 switchTab 需加分支（对应原版 router 表）
3. `boot()` 在模块加载时立即执行——测试/SSR 场景需注意（学习版纯浏览器 SPA，无 SSR）

> 页脚：2026-10-20 · M8 应用入口 · 对标 `EvoFlow/evopanel/src/main.js` + router.js（学习版裁剪；10-20 补 🧩 代码解析）
