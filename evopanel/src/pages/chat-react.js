// ============================================================================
// AgentFlow · evopanel/src/pages/chat-react.js —— 聊天页（流式 + 多会话）
// ============================================================================
// 对标来源: EvoFlow/evopanel/src/pages/chat-react.js（原版 27 行薄壳挂 ChatApp；
//   学习版为可独立阅读的单文件，实现同等的"SSE 流式 + 会话切换"行为）
// 里程碑: M8（前端界面）
// ----------------------------------------------------------------------------
// 💡 设计思想
// 1. 数据流（对应 M7 gateway 两段式 runs）：
//    发消息 → streamSSE({message, threadId}) 内部 POST /api/runs 拿 run_id
//          → GET /api/runs/{id}/stream 消费 delta/done/error 事件
//          → onDelta 逐块追加 / onDone 落全文
// 2. 多会话：左侧列表来自 GET /api/threads；选中会话 → 历史恢复（本版后端
//    threads 只存会话壳，消息历史走 checkpointer；学习版以"切换会话后新消息
//    进对应 thread_id"为最小语义，历史逐条恢复标注为 M8+）。
// 3. 新建会话 = 不发 thread_id（后端自动生成）→ 切换时把 thread_id 记住。
// 4. 同一时刻只允许一个流：isStreaming 标志防重入，等待期间禁用发送。
// ============================================================================

import { threadsApi, streamSSE } from '../lib/api-client.js'

export function renderChat(container) {
  container.innerHTML = `
    <div class="chat-layout">
      <aside class="chat-sidebar">
        <div class="new-thread"><button class="btn" id="new-thread" style="width:100%">+ 新建会话</button></div>
        <div class="thread-list" id="thread-list"></div>
      </aside>
      <section class="chat-main">
        <div class="chat-messages" id="chat-messages"></div>
        <div class="chat-input-row">
          <input type="text" id="chat-input" placeholder="输入消息，回车发送（Enter）" />
          <button class="btn btn-primary" id="send-btn">发送</button>
        </div>
      </section>
    </div>
  `

  const listEl = container.querySelector('#thread-list')
  const msgsEl = container.querySelector('#chat-messages')
  const inputEl = container.querySelector('#chat-input')
  const sendBtn = container.querySelector('#send-btn')

  let currentThreadId = null
  let isStreaming = false

  /** 渲染会话列表（active 高亮 + 删除按钮）。 */
  async function refreshThreads() {
    try {
      const res = await threadsApi.list()
      const threads = (res && res.threads) || []
      listEl.innerHTML = ''
      for (const t of threads) {
        const item = document.createElement('div')
        item.className = 'thread-item' + (t.thread_id === currentThreadId ? ' active' : '')
        item.innerHTML = `
          <span class="title">${escapeHtml(t.title || t.thread_id.slice(0, 8))}</span>
          <button class="del" title="删除">×</button>
        `
        item.addEventListener('click', (e) => {
          if (e.target.classList.contains('del')) return
          switchThread(t.thread_id)
        })
        item.querySelector('.del').addEventListener('click', async (e) => {
          e.stopPropagation()
          await threadsApi.remove(t.thread_id)
          if (currentThreadId === t.thread_id) {
            currentThreadId = null
            msgsEl.innerHTML = ''
          }
          refreshThreads()
        })
        listEl.appendChild(item)
      }
    } catch (err) {
      listEl.innerHTML = `<div class="thread-item"><span class="title" style="color:var(--danger)">会话列表加载失败：${escapeHtml(err.message)}</span></div>`
    }
  }

  function switchThread(threadId) {
    currentThreadId = threadId
    msgsEl.innerHTML = ''
    msgsEl.appendChild(systemMsg('已切换到会话 ' + threadId.slice(0, 8) + '（历史消息恢复为 M8+ 增强项）'))
    refreshThreads()
  }

  function systemMsg(text) {
    const el = document.createElement('div')
    el.className = 'msg system'
    el.textContent = text
    return el
  }

  function appendMsg(role, text) {
    const el = document.createElement('div')
    el.className = `msg ${role}`
    el.textContent = text
    msgsEl.appendChild(el)
    msgsEl.scrollTop = msgsEl.scrollHeight
    return el
  }

  /** 发送一条消息：streamSSE 消费流式回复。 */
  async function send() {
    const text = inputEl.value.trim()
    if (!text || isStreaming) return
    inputEl.value = ''
    appendMsg('user', text)

    const assistantEl = appendMsg('assistant', '…')
    const typing = document.createElement('div')
    typing.className = 'typing'
    typing.textContent = '思考中…'
    msgsEl.appendChild(typing)

    isStreaming = true
    sendBtn.disabled = true
    try {
      let streamed = ''
      await streamSSE({
        message: text,
        threadId: currentThreadId,
        // run 创建即回调：首次发消息（无会话）时回填后端生成的 thread_id
        onCreated: (run) => {
          if (!currentThreadId && run && run.thread_id) {
            currentThreadId = run.thread_id
            refreshThreads()
          }
        },
        onDelta: (chunk) => {
          streamed += chunk
          assistantEl.textContent = streamed
          msgsEl.scrollTop = msgsEl.scrollHeight
        },
        onDone: (full) => {
          assistantEl.textContent = full || streamed || '（空回复）'
          refreshThreads()
        },
        onError: (msg) => {
          assistantEl.className = 'msg error'
          assistantEl.textContent = `错误：${msg}`
        },
      })
    } catch (err) {
      assistantEl.className = 'msg error'
      assistantEl.textContent = `请求失败：${err.message}`
    } finally {
      typing.remove()
      isStreaming = false
      sendBtn.disabled = false
      inputEl.focus()
    }
  }

  sendBtn.addEventListener('click', send)
  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') send()
  })
  container.querySelector('#new-thread').addEventListener('click', () => {
    currentThreadId = null
    msgsEl.innerHTML = ''
    msgsEl.appendChild(systemMsg('新会话已就绪——发送第一条消息将创建新会话'))
    refreshThreads()
  })

  refreshThreads()
  inputEl.focus()

  // 返回 cleanup（main.js 切标签时调用）
  return () => {}
}

function escapeHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}
