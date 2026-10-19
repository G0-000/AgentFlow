// ============================================================================
// AgentFlow · evopanel/src/lib/api-client.js —— API 封装（请求 + SSE 流式）
// ============================================================================
// 对标来源: EvoFlow/evopanel/src/lib/api-client.js（裁剪：去掉 Tauri 直连分支，
//   学习版只保留 Vite dev 相对路径 + 兜底地址）
// 里程碑: M8（前端界面）
// ----------------------------------------------------------------------------
// 💡 设计思想
// 1. apiUrl(path)：统一解析后端地址——Vite dev 走相对路径 `/api/*`（由
//    vite.config.js proxy 转发到 gateway），不写死 38012 到页面代码。
// 2. request()：fetch 薄封装，统一带 JSON 头 + 错误归一（非 2xx 抛带 detail 的
//    ApiError）。所有页面（chat/models/login）只跟它打交道。
// 3. streamSSE()：聊天流式核心。后端是两段式（POST /api/runs 拿 run_id →
//    GET /api/runs/{id}/stream），本函数封装 fetch ReadableStream 逐行解析
//    SSE 帧（event:/data:），onDelta/onDone/onError 回调。
// 4. 登录态：token 存 localStorage（学习版；后端 JWT 校验中间件为 M8+ 增强）。
// ============================================================================

const TOKEN_KEY = 'agentflow_token'

/** 归一化 API 基础路径：Vite dev 走相对 /api（proxy 转发），否则兜底直连。 */
export function apiUrl(path) {
  const p = path.startsWith('/') ? path : `/${path}`
  try {
    // Vite dev：相对路径由 proxy 转发（见 vite.config.js）
    if (import.meta && import.meta.env && import.meta.env.DEV) return `/api${p}`
  } catch {
    // ignore
  }
  return `/api${p}` // 生产构建：同源 /api（反代或 gateway 同源部署）
}

/** 统一请求：method + JSON body → 解析 JSON；非 2xx 抛 ApiError(detail)。 */
export async function request(path, { method = 'GET', body = null } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  const resp = await fetch(apiUrl(path), {
    method,
    headers,
    body: body === null ? undefined : JSON.stringify(body),
  })
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`
    try {
      const data = await resp.json()
      if (data && data.detail) detail = data.detail
    } catch {
      // 非 JSON 响应，保留 HTTP 状态
    }
    const err = new Error(detail)
    err.status = resp.status
    throw err
  }
  return resp.json()
}

/** 登录 token 存取（localStorage；学习版会话保持的最小实现）。 */
export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) || ''
  } catch {
    return ''
  }
}
export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

/**
 * SSE 流式对话：POST /api/runs 创建 run → GET /api/runs/{id}/stream 消费流。
 * 后端事件（见 backend/app/gateway/sse.py）：
 *   event: delta  data: {"delta": "文本块"}          ← 逐块追加
 *   event: done   data: {"status":"success","response": 全文}  ← 流结束
 *   event: error  data: {"error": "消息"}            ← 失败
 * @param {object} opts
 * @param {string} opts.message 用户消息
 * @param {string|null} opts.threadId 复用会话；null 则新建
 * @param {(text:string)=>void} opts.onDelta 每个文本块
 * @param {(full:string)=>void} opts.onDone 流结束（带全文）
 * @param {(error:string)=>void} opts.onError 失败
 * @param {({run_id:string, thread_id:string})=>void} opts.onCreated run 创建后立即回调（前端回填会话 id 用）
 * @returns {Promise<void>}
 */
export async function streamSSE({ message, threadId = null, onDelta, onDone, onError, onCreated }) {
  // ① 创建 run（两段式第一步）
  const run = await request('/runs', {
    method: 'POST',
    body: { message, thread_id: threadId },
  })
  onCreated?.(run)
  // ② 打开 SSE 流
  const resp = await fetch(apiUrl(`/runs/${run.run_id}/stream`))
  if (!resp.ok || !resp.body) {
    onError?.(`流打开失败 HTTP ${resp.status}`)
    return
  }
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let eventName = ''
  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      // SSE 帧以空行分隔；逐帧解析
      let sep
      while ((sep = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, sep)
        buffer = buffer.slice(sep + 2)
        if (!frame.trim()) continue
        for (const line of frame.split('\n')) {
          if (line.startsWith('event:')) eventName = line.slice(6).trim()
          else if (line.startsWith('data:')) {
            let payload
            try {
              payload = JSON.parse(line.slice(5).trim())
            } catch {
              continue // 非 JSON data 行（如注释），跳过
            }
            if (eventName === 'delta') onDelta?.(payload.delta ?? '')
            else if (eventName === 'done') onDone?.(payload.response ?? '')
            else if (eventName === 'error') onError?.(payload.error ?? '未知错误')
            eventName = ''
          }
        }
      }
    }
  } catch (err) {
    onError?.(err.message || '流读取中断')
  }
}

/** API 封装：models（模型设置页数据面）。 */
export const modelsApi = {
  list: () => request('/models'),
  create: (body) => request('/models', { method: 'POST', body }),
  update: (name, body) => request(`/models/${encodeURIComponent(name)}`, { method: 'PATCH', body }),
  remove: (name) => request(`/models/${encodeURIComponent(name)}`, { method: 'DELETE' }),
}

/** API 封装：threads（会话列表数据面）。 */
export const threadsApi = {
  list: () => request('/threads'),
  create: (body = {}) => request('/threads', { method: 'POST', body }),
  remove: (threadId) => request(`/threads/${encodeURIComponent(threadId)}`, { method: 'DELETE' }),
}

/** API 封装：auth（登录）。 */
export const authApi = {
  login: (username, password) =>
    request('/auth/login', { method: 'POST', body: { username, password } }),
}
