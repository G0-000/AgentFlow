// ============================================================================
// AgentFlow · evopanel/src/main.js —— 应用入口（路由选择页面）
// ============================================================================
// 对标来源: EvoFlow/evopanel/src/main.js + router.js（"每页一个 render()"约定）
// 里程碑: M8（前端界面）
// ----------------------------------------------------------------------------
// 💡 设计思想
// 1. 全局布局（顶栏 + 标签 + 内容区）由 main.js 持有；页面模块只导出
//    render(container) → 把自己画进容器，并返回 cleanup（可选）。
// 2. 登录态 gate：localStorage 有 token → 主界面；否则登录页。
// 3. 标签切换（聊天 / 模型设置）时先调用旧页 cleanup 再挂新页，避免事件泄漏。
// ============================================================================

import './style.css'
import { getToken, clearToken } from './lib/api-client.js'
import { renderLogin } from './pages/login.js'
import { renderChat } from './pages/chat-react.js'
import { renderModels } from './pages/models.js'

const app = document.getElementById('app')

function buildShell() {
  app.innerHTML = `
    <header class="app-header">
      <div class="brand">AgentFlow 控制面板</div>
      <nav class="tabs">
        <button data-tab="chat" class="active">聊天</button>
        <button data-tab="models">模型设置</button>
      </nav>
      <div class="spacer"></div>
      <button class="logout">退出登录</button>
    </header>
    <main class="app-main"></main>
  `
  const tabs = app.querySelectorAll('.tabs button')
  const main = app.querySelector('.app-main')
  app.querySelector('.logout').addEventListener('click', () => {
    clearToken()
    boot()
  })

  let cleanup = null
  const switchTab = (name) => {
    tabs.forEach((b) => b.classList.toggle('active', b.dataset.tab === name))
    cleanup?.()
    main.innerHTML = ''
    if (name === 'chat') cleanup = renderChat(main)
    else cleanup = renderModels(main)
  }
  tabs.forEach((b) => b.addEventListener('click', () => switchTab(b.dataset.tab)))
  switchTab('chat')
}

/** 入口：登录态 gate。 */
export function boot() {
  app.innerHTML = ''
  if (getToken()) buildShell()
  else renderLogin(app)
}

boot()
