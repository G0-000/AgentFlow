// ============================================================================
// AgentFlow · evopanel/src/pages/models.js —— 模型设置页
// ============================================================================
// 对标来源: EvoFlow/evopanel/src/pages/models.js（原版 4252 行 vanilla JS；
//   学习版裁剪为同一数据面：列表 + 增改删 + 设默认）
// 里程碑: M8（前端界面）
// ----------------------------------------------------------------------------
// 💡 设计思想
// 1. 数据面 = M7 的 gateway models API（SQLite gateway_models 表）：
//    GET /api/models 列表 → POST 新增 → PATCH 改/设默认 → DELETE 删。
//    模型存 SQLite 而非 config.yaml —— 页面增删改后"不重启代码，下次对话用新模型"
//    （create_app 的默认 runner 每次调用都现场读主模型）。
// 2. 设默认 = PATCH is_primary:true；后端 set_primary 用事务翻转唯一主。
// 3. 弹窗/删除确认复用 components/modal.js。
// ============================================================================

import { modelsApi } from '../lib/api-client.js'
import { showConfirm, showModal } from '../components/modal.js'

export function renderModels(container) {
  container.innerHTML = `
    <div class="models-page">
      <div class="toolbar">
        <h2 style="margin:0">模型设置</h2>
        <button class="btn btn-primary" id="add-model">+ 新增模型</button>
      </div>
      <table class="models-table">
        <thead>
          <tr>
            <th>名称</th><th>服务商</th><th>模型</th><th>base_url</th>
            <th>temperature</th><th>状态</th><th style="width:190px">操作</th>
          </tr>
        </thead>
        <tbody id="models-tbody"></tbody>
      </table>
    </div>
  `

  const tbody = container.querySelector('#models-tbody')
  const errorBar = document.createElement('div')
  errorBar.style.cssText = 'color:var(--danger);margin:8px 0;font-size:var(--font-sm)'

  async function refresh() {
    tbody.innerHTML = '<tr><td colspan="7" style="color:var(--text-secondary)">加载中…</td></tr>'
    try {
      const res = await modelsApi.list()
      const rows = (res && res.models) || []
      if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="7" style="color:var(--text-secondary)">还没有模型，点右上角新增</td></tr>'
        return
      }
      tbody.innerHTML = ''
      for (const m of rows) {
        const tr = document.createElement('tr')
        tr.innerHTML = `
          <td>${escapeHtml(m.name)}</td>
          <td>${escapeHtml(m.provider || '-')}</td>
          <td>${escapeHtml(m.model || '-')}</td>
          <td style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escapeHtml(m.base_url || '-')}</td>
          <td>${m.temperature ?? '-'}</td>
          <td>${m.is_primary ? '<span class="badge primary">主模型</span>' : '<span class="badge">备用</span>'}</td>
          <td>
            <button class="btn" data-op="set-primary" style="font-size:12px;padding:4px 8px">设默认</button>
            <button class="btn" data-op="edit" style="font-size:12px;padding:4px 8px">编辑</button>
            <button class="btn btn-danger" data-op="del" style="font-size:12px;padding:4px 8px">删除</button>
          </td>
        `
        // 行内操作
        tr.querySelector('[data-op="set-primary"]').addEventListener('click', async () => {
          try {
            await modelsApi.update(m.name, { is_primary: true })
            refresh()
          } catch (err) { flash(err.message) }
        })
        tr.querySelector('[data-op="edit"]').addEventListener('click', () => openForm(m))
        tr.querySelector('[data-op="del"]').addEventListener('click', async () => {
          const ok = await showConfirm(`删除模型「${m.name}」？不可恢复。`)
          if (!ok) return
          try {
            await modelsApi.remove(m.name)
            refresh()
          } catch (err) { flash(err.message) }
        })
        tbody.appendChild(tr)
      }
    } catch (err) {
      tbody.innerHTML = ''
      errorBar.textContent = `模型列表加载失败：${err.message}`
      container.querySelector('.models-page').insertBefore(errorBar, tbody)
    }
  }

  function flash(msg) {
    errorBar.textContent = msg
    if (!errorBar.parentElement) container.querySelector('.models-page').insertBefore(errorBar, tbody)
    setTimeout(() => errorBar.remove(), 4000)
  }

  /** 新增/编辑表单（showModal 通用模态）。 */
  function openForm(existing = null) {
    const isEdit = !!existing
    const v = (k, d = '') => (existing && existing[k] !== undefined ? existing[k] : d)
    const html = `
      <div style="display:grid;gap:10px">
        <div><label style="font-size:12px;color:var(--text-secondary)">名称（唯一标识）</label>
          <input type="text" id="f-name" value="${escapeAttr(v('name'))}" ${isEdit ? 'disabled' : ''} /></div>
        <div><label style="font-size:12px;color:var(--text-secondary)">服务商 provider</label>
          <input type="text" id="f-provider" value="${escapeAttr(v('provider', 'openai-compatible'))}" /></div>
        <div><label style="font-size:12px;color:var(--text-secondary)">模型名 model</label>
          <input type="text" id="f-model" value="${escapeAttr(v('model'))}" /></div>
        <div><label style="font-size:12px;color:var(--text-secondary)">base_url</label>
          <input type="text" id="f-base" value="${escapeAttr(v('base_url'))}" /></div>
        <div><label style="font-size:12px;color:var(--text-secondary)">api_key（${isEdit ? '留空则不变' : '可选'}）</label>
          <input type="password" id="f-key" value="${escapeAttr(v('api_key'))}" /></div>
        <div><label style="font-size:12px;color:var(--text-secondary)">temperature</label>
          <input type="number" id="f-temp" step="0.1" min="0" max="2" value="${v('temperature', 0.3)}" /></div>
        <div><label><input type="checkbox" id="f-primary" ${v('is_primary', false) ? 'checked' : ''} /> 设为主模型</label></div>
      </div>`

    showModal({
      title: isEdit ? `编辑模型「${existing.name}」` : '新增模型',
      html,
      actions: [
        {
          label: isEdit ? '保存' : '创建',
          primary: true,
          handler: async () => {
            const body = {
              provider: container.querySelector('#f-provider').value.trim(),
              model: container.querySelector('#f-model').value.trim(),
              base_url: container.querySelector('#f-base').value.trim(),
              api_key: container.querySelector('#f-key').value.trim(),
              temperature: Number(container.querySelector('#f-temp').value || 0.3),
              is_primary: container.querySelector('#f-primary').checked,
            }
            try {
              if (isEdit) {
                delete body.api_key // PATCH 语义：api_key 留空则后端不改（见 models.py）
                await modelsApi.update(existing.name, body)
              } else {
                await modelsApi.create(body)
              }
              refresh()
            } catch (err) {
              alert(`保存失败：${err.message}`)
              throw err // 保持模态打开
            }
          },
        },
      ],
    })
  }

  container.querySelector('#add-model').addEventListener('click', () => openForm())
  refresh()
}

function escapeHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}
function escapeAttr(str) {
  return escapeHtml(str).replace(/'/g, '&#39;')
}
