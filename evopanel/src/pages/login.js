// ============================================================================
// AgentFlow · evopanel/src/pages/login.js —— 登录页
// ============================================================================
// 对标来源: EvoFlow/evopanel/src/pages/login.js（裁剪：原版 390 行含注册/找回
//   密码等；学习版只留账号密码登录 + token 落 localStorage）
// 里程碑: M8（前端界面）
// ----------------------------------------------------------------------------
// 💡 设计思想
// 1. 调后端 POST /api/auth/login（M8 新增，复用 M6 webui/auth.py 的
//    verify_password + generate_jwt）→ {token} → 存 localStorage → 通知 main 进主界面。
// 2. 密码不落任何前端存储；token 是唯一会话凭据（7 天过期，由后端 exp 控制）。
// 3. render(container) 约定：把登录卡片画进容器；成功时 window.location.reload()
//    让 main.js 的登录态 gate 重新走一遍（最简单可靠的切换方式）。
// ============================================================================

import { authApi, setToken } from '../lib/api-client.js'

export function renderLogin(container) {
  container.innerHTML = `
    <div class="login-wrap">
      <div class="login-card">
        <h1>AgentFlow 控制面板</h1>
        <div class="field">
          <label>用户名</label>
          <input type="text" id="login-username" autocomplete="username" />
        </div>
        <div class="field">
          <label>密码</label>
          <input type="password" id="login-password" autocomplete="current-password" />
        </div>
        <div class="error" id="login-error"></div>
        <button class="btn btn-primary" id="login-btn" style="width:100%">登 录</button>
      </div>
    </div>
  `
  const username = container.querySelector('#login-username')
  const password = container.querySelector('#login-password')
  const errorEl = container.querySelector('#login-error')
  const btn = container.querySelector('#login-btn')

  const doLogin = async () => {
    errorEl.textContent = ''
    btn.disabled = true
    try {
      const res = await authApi.login(username.value.trim(), password.value)
      setToken(res.token)
      window.location.reload()
    } catch (err) {
      errorEl.textContent = err.message || '登录失败'
      btn.disabled = false
    }
  }
  btn.addEventListener('click', doLogin)
  password.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') doLogin()
  })
  username.focus()
}
