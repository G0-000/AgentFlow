// ============================================================================
// AgentFlow · evopanel/src/components/modal.js —— 通用弹窗（对齐原版）
// ============================================================================
// 对标来源: EvoFlow/evopanel/src/components/modal.js（裁剪：去掉 Tauri 拖拽
//   与 browser-embed 联动，保留 showConfirm/showModal 两个核心导出）
// 里程碑: M8（前端界面）
// ----------------------------------------------------------------------------
// 💡 设计思想
// 1. showConfirm(message) 返回 Promise<boolean>，替代原生 confirm()——
//    浏览器与 Tauri WebView 行为一致，且可样式化。
// 2. showModal({title, html, actions}) 通用模态：调用方传 HTML 字符串 +
//    action 按钮（label/handler），返回 Promise 等用户操作。
// 3. 遮罩点击 = 取消（确认框）/关闭（模态），ESC 关闭；promise 保证只 resolve 一次。
// ============================================================================

/** 转义 HTML 属性/文本，防止注入破坏结构。 */
function escapeHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function _removeOverlay(overlay) {
  overlay.remove()
  document.body.classList.remove('modal-open')
}

/**
 * 自定义确认弹窗（替代原生 confirm）。
 * @param {string} message 确认消息
 * @returns {Promise<boolean>} 确认 true / 取消 false
 */
export function showConfirm(message) {
  return new Promise((resolve) => {
    const overlay = document.createElement('div')
    overlay.className = 'modal-overlay'
    overlay.innerHTML = `
      <div class="modal" style="max-width:420px">
        <div class="modal-title">确认操作</div>
        <div class="modal-body" style="white-space:pre-wrap">${escapeHtml(message)}</div>
        <div class="modal-actions">
          <button class="btn" data-act="cancel">取消</button>
          <button class="btn btn-primary" data-act="ok">确认</button>
        </div>
      </div>`
    document.body.appendChild(overlay)
    document.body.classList.add('modal-open')

    let settled = false
    const done = (v) => {
      if (settled) return
      settled = true
      _removeOverlay(overlay)
      resolve(v)
    }
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) return done(false) // 点遮罩 = 取消
      const act = e.target.closest('[data-act]')?.dataset.act
      if (act === 'ok') done(true)
      else if (act === 'cancel') done(false)
    })
    const onKey = (e) => {
      if (e.key === 'Escape') {
        window.removeEventListener('keydown', onKey)
        done(false)
      }
    }
    window.addEventListener('keydown', onKey)
  })
}

/**
 * 通用模态：HTML 内容 + 操作按钮。
 * @param {object} opts
 * @param {string} opts.title 标题
 * @param {string} opts.html 正文 HTML（已由调用方转义/信任内容）
 * @param {Array<{label:string; primary?:boolean; handler:(el:HTMLElement)=>void}>} opts.actions
 * @returns {Promise<void>}
 */
export function showModal({ title, html = '', actions = [] }) {
  return new Promise((resolve) => {
    const overlay = document.createElement('div')
    overlay.className = 'modal-overlay'
    overlay.innerHTML = `
      <div class="modal">
        <div class="modal-title">${escapeHtml(title)}</div>
        <div class="modal-body">${html}</div>
        <div class="modal-actions">
          ${actions
            .map(
              (a, i) =>
                `<button class="btn ${a.primary ? 'btn-primary' : ''}" data-i="${i}">${escapeHtml(a.label)}</button>`,
            )
            .join('')}
          <button class="btn" data-i="__close">关闭</button>
        </div>
      </div>`
    document.body.appendChild(overlay)
    document.body.classList.add('modal-open')

    overlay.addEventListener('click', async (e) => {
      if (e.target === overlay) return _close()
      const btn = e.target.closest('button[data-i]')
      if (!btn) return
      if (btn.dataset.i === '__close') return _close()
      const act = actions[Number(btn.dataset.i)]
      if (act?.handler) await act.handler(overlay)
      if (!act?.keepOpen) _close()
    })
    const _close = () => {
      window.removeEventListener('keydown', onKey)
      _removeOverlay(overlay)
      resolve()
    }
    const onKey = (e) => {
      if (e.key === 'Escape') _close()
    }
    window.addEventListener('keydown', onKey)
  })
}
