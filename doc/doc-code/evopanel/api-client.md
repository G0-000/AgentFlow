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
          ▼ 步骤 3：buffer += decode(...)，按 '\n\n' 切帧
          ├─ line 'event: delta' → data: {delta} → onDelta
          ├─ line 'event: done'  → data: {response} → onDone
          └─ line 'event: error' → data: {error} → onError
  ▼ 步骤 4：流结束（done）或异常 → 返回 / onError
```

## ❓ Q&A / 知识点

**Q: 为什么不用原生 EventSource？**
A: EventSource 只能 GET；虽然流式端点本身是 GET，但两段式第一步 POST /runs 需要 fetch，且 fetch 流的统一错误处理（HTTP 状态、detail 解析）比 EventSource 可控。手写解析 SSE 帧（`\n\n` 分隔 + `event:`/`data:` 行）是标准做法，不依赖浏览器差异。

**Q: `request` 抛的 Error 为什么带 `status` 字段？**
A: 调用方需要区分"401 未登录 / 503 未配置 / 404 不存在"做 UI 分支——`err.status = resp.status` 保留 HTTP 状态，`err.message` 是后端 detail（或 `HTTP x` 兜底）。

**Q: token 存 localStorage 安全吗？**
A: 学习版最小实现。生产 XSS 可窃取 localStorage token；M8.1 若做 JWT 校验中间件，应改用 HttpOnly cookie 或短期 token + 刷新。

## ⚠️ 风险点

1. SSE 帧解析按 `\n\n` 分隔——后端若发送单 `\n` 分隔帧会漏帧（当前 sse.py 由 sse-starlette 保证双换行）
2. `import.meta.env.DEV` 判定：生产构建走同源 `/api`，需反代/同源部署（学习版以 dev 为主）
3. 并发流：聊天页用 `isStreaming` 防重入，但 streamSSE 本身不防——调用方负责
4. token 过期（7 天 exp）后 API 仍可用（无校验中间件），属 M8.1 增强范围

> 页脚：2026-10-17 · M8 前端核心 · 对标 `EvoFlow/evopanel/src/lib/api-client.js`（裁剪）
