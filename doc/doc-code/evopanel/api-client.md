# evopanel/src/lib/api-client.js — api-client.js

> **文件路径**: `evopanel/src/lib/api-client.js`
> **对标来源**: `EvoFlow/evopanel/src/lib/api-client.js`（796 行；裁剪：去掉 Tauri 直连分支，学习版只留 Vite dev 相对路径 + 兜底）
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
apiUrl(path)         /api + path（Vite dev 相对路径，proxy 转发）
request(path, {method, body})   fetch 薄封装 → JSON；非 2xx 抛 Error(detail)
streamSSE(opts)      两段式流式：POST /runs → GET /runs/{id}/stream → 逐帧解析
getToken/setToken/clearToken   localStorage token（登录态）
modelsApi / threadsApi / authApi  三个数据面的封装
```

## 📤 关键导出

- `apiUrl` / `request` / `streamSSE`
- `getToken` / `setToken` / `clearToken`
- `modelsApi`（list/create/update/remove）、`threadsApi`（list/create/remove）、`authApi`（login）

## 💡 设计思想

1. **单一请求通道**：所有页面只跟 `request()` 打交道——统一 JSON 头、token 注入、错误归一（非 2xx 抛 `Error(detail)`，detail 来自后端 `{"detail": ...}`）。
2. **apiUrl 归一**：路径补前导 `/`，Vite dev 走 `/api/*` 相对路径（proxy 转发），不写死 gateway 地址（对齐原版"Vite dev / Tauri 直连 / 生产同源"三态，学习版砍掉 Tauri）。
3. **SSE 解析为手写状态机**：`ReadableStream` + `TextDecoder` 逐帧按 `\n\n` 分隔，行级解析 `event:` / `data:`——不依赖 EventSource（SSE 经 fetch 才能带 POST 的第二步拿流 + 统一错误处理）。
4. **两段式 run**：流式对话必须先 `POST /runs` 创建（拿 run_id/thread_id），再开 SSE 流——thread_id 在创建时就能回填（onCreated），解决"新会话如何记住 id"。

## 🎯 实用场景

1. 聊天页发消息：`streamSSE({message, threadId, onCreated, onDelta, onDone, onError})`——onCreated 回填会话、onDelta 打字机、onDone 落全文。
2. 登录页：`authApi.login` → `setToken(res.token)` → reload 进主界面。
3. 模型设置页：`modelsApi.list/create/update/remove` 对应表格操作。

## 🧩 顺序执行链

```text
streamSSE({message, threadId})
  ▼ 步骤 1：request('/runs', POST, {message, thread_id})
  ├─ 成功 → onCreated(run)（回填 thread_id）
  └─ 失败 → 抛错（调用方 catch）
  ▼ 步骤 2：fetch(apiUrl('/runs/{run_id}/stream'))
  ├─ 非 200 / 无 body → onError("流打开失败 HTTP x")
  └─ 200 → reader 循环 read()
          ▼ 步骤 3：buffer += decode(...)，CRLF 归一（\r\n→\n）后按 '\n\n' 切帧
          ├─ line 'event: delta' → data: {delta} → onDelta
          ├─ line 'event: done'  → data: {response} → onDone
          └─ line 'event: error' → data: {error} → onError
  ▼ 步骤 4：流结束（done）或异常 → 返回 / onError
```

## 🧩 代码解析

```js
const TOKEN_KEY = 'agentflow_token'

export function apiUrl(path) {                // 路径归一：/api 前缀（Vite dev proxy 转发）
  const p = path.startsWith('/') ? path : `/${path}`
  if (import.meta && import.meta.env && import.meta.env.DEV) return `/api${p}`
  return `/api${p}`                           // 生产同源
}

export async function request(path, { method = 'GET', body = null } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`   // 登录态注入
  const resp = await fetch(apiUrl(path), { method, headers,
    body: body === null ? undefined : JSON.stringify(body) })
  if (!resp.ok) {                             // 错误归一：非 2xx → Error(detail)
    let detail = `HTTP ${resp.status}`
    try { const data = await resp.json(); if (data?.detail) detail = data.detail } catch {}
    const err = new Error(detail); err.status = resp.status; throw err
  }
  return resp.json()
}

export async function streamSSE({ message, threadId = null, onDelta, onDone, onError, onCreated }) {
  const run = await request('/runs', { method: 'POST', body: { message, thread_id: threadId } })
  onCreated?.(run)                            // ① 两段式第一步：POST 建 run，回填 thread_id
  const resp = await fetch(apiUrl(`/runs/${run.run_id}/stream`))
  if (!resp.ok || !resp.body) { onError?.(`流打开失败 HTTP ${resp.status}`); return }
  const reader = resp.body.getReader()        // ② 第二步：读流
  const decoder = new TextDecoder()
  let buffer = '', eventName = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    buffer = buffer.replace(/\r\n/g, '\n')   // 归一 CRLF：兼容 sse-starlette 的 \r\n\r\n 帧分隔
    let sep
    while ((sep = buffer.indexOf('\n\n')) !== -1) {   // ③ 归一后按空行切 SSE 帧
      const frame = buffer.slice(0, sep); buffer = buffer.slice(sep + 2)
      if (!frame.trim()) continue
      for (const line of frame.split('\n')) {
        if (line.startsWith('event:')) eventName = line.slice(6).trim()
        else if (line.startsWith('data:')) {
          const payload = JSON.parse(line.slice(5).trim())
          if (eventName === 'delta') onDelta?.(payload.delta ?? '')
          else if (eventName === 'done') onDone?.(payload.response ?? '')
          else if (eventName === 'error') onError?.(payload.error ?? '未知错误')
          eventName = ''
        }
      }
    }
  }
}
```

**逐块拆解**：

- **`apiUrl`** — 所有请求统一走 `/api/*`；`import.meta.env.DEV` 分支存在但两条 return 相同（学习版 dev/生产都同源 /api，保留分支表达"Vite proxy / 生产反代"两种意图）。
- **`request`** — 三件事：JSON 头、token 注入（有 token 才带 `Authorization`）、错误归一（非 2xx 取后端 `detail` 作 `Error.message` 并附加 `status`）。所有页面只跟它打交道。
- **`streamSSE`** — 前端流式核心，对应后端两段式：`POST /runs` 拿 `run_id` → `GET /runs/{id}/stream` 读流。`onCreated` 在 run 创建后立即回调（聊天页用来回填新会话 thread_id）。
- **SSE 帧解析** — 手写状态机：`buffer` 累积解码文本 → 按 `\n\n` 切帧 → 行级解析 `event:`/`data:` → 按事件名分发到 onDelta/onDone/onError。用 fetch 而非 EventSource（见 Q&A）。
- **`modelsApi/threadsApi/authApi`** — 三个数据面薄封装，全部转调 `request()`：models（list/create/update/remove）、threads（list/create/remove）、auth（login）。

## ❓ Q&A / 知识点

**Q: 为什么不用原生 EventSource？**
A: EventSource 只能 GET；虽然流式端点本身是 GET，但两段式第一步 POST /runs 需要 fetch，且 fetch 流的统一错误处理（HTTP 状态、detail 解析）比 EventSource 可控。手写解析 SSE 帧（`\n\n` 分隔 + `event:`/`data:` 行）是标准做法，不依赖浏览器差异。

**Q: `request` 抛的 Error 为什么带 `status` 字段？**
A: 调用方需要区分"401 未登录 / 503 未配置 / 404 不存在"做 UI 分支——`err.status = resp.status` 保留 HTTP 状态，`err.message` 是后端 detail（或 `HTTP x` 兜底）。

**Q: token 存 localStorage 安全吗？**
A: 学习版最小实现。生产 XSS 可窃取 localStorage token；M8.1 若做 JWT 校验中间件，应改用 HttpOnly cookie 或短期 token + 刷新。

## ⚠️ 风险点

1. ~~SSE 帧解析按 `\n\n` 分隔~~（已修 2026-10-20）：sse-starlette 生产输出帧分隔是 `\r\n\r\n`（行内 `\n`），按 `\n\n` 切会永远切不开、事件全丢。现先 `replace(/\r\n/g,'\n')` 归一再切，兼容两种格式——测试同步改为 `\r\n\r\n` 生产格式 + 保留 `\n\n` 兼容用例
2. `import.meta.env.DEV` 判定：生产构建走同源 `/api`，需反代/同源部署（学习版以 dev 为主）
3. 并发流：聊天页用 `isStreaming` 防重入，但 streamSSE 本身不防——调用方负责
4. token 过期（7 天 exp）后 API 仍可用（无校验中间件），属 M8.1 增强范围

> 页脚：2026-10-20 · M8 前端核心 · 对标 `EvoFlow/evopanel/src/lib/api-client.js`（裁剪；10-20 补 🧩 代码解析 + 修 SSE 帧分隔：\r\n\r\n 归一，测试改生产格式）
