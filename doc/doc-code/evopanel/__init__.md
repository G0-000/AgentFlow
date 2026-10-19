# evopanel/ — AgentFlow 控制面板（M8 前端工程）

> **目录位置**: `/Users/main/AgentFlow/evopanel/`
> **对标来源**: `EvoFlow/evopanel/`（v1.1.0 已重构为 zcode 五体系 + Tauri 壳；学习版裁剪为薄壳单页 React + Vite，浏览器 Web）
> **里程碑**: M8（前端界面，✅ 已实现 2026-10-17，验收 5/5）

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
evopanel/
├── package.json              React 19 + Vite 6 + vitest 3（pnpm 管理）
├── vite.config.js            dev 端口 5173 + /api proxy → 127.0.0.1:38012
├── pnpm-workspace.yaml       pnpm 12 allowBuilds: esbuild（构建脚本白名单）
├── index.html                SPA 挂载点
├── src/
│   ├── main.js               入口：登录态 gate + 顶栏 tabs（聊天/模型设置）
│   ├── style.css             最小 CSS 变量
│   ├── lib/api-client.js     请求封装：apiUrl / request / streamSSE + 三组 API
│   ├── components/modal.js   通用弹窗：showConfirm / showModal
│   └── pages/
│       ├── login.js          登录页（POST /api/auth/login）
│       ├── chat-react.js     聊天页（会话列表/流式回复）
│       └── models.js         模型设置页（增改删/设默认）
└── tests/test_api_client.js  vitest 10 用例
```

**与 M7 gateway 的对接面**（契约见各页面文档）：

| 前端文件 | 调用的后端端点 |
|---|---|
| login.js | `POST /api/auth/login`（M8 新增） |
| models.js | `/api/models` GET/POST + `/api/models/{name}` PATCH/DELETE |
| chat-react.js | `/api/threads` GET/POST/DELETE + `/api/runs` POST + `/api/runs/{id}/stream` SSE |

## 📤 关键导出

- `boot()`（main.js）：应用入口，登录态 gate
- `renderLogin(container)`（login.js）
- `renderChat(container)`（chat-react.js）
- `renderModels(container)`（models.js）
- `apiUrl / request / streamSSE / getToken / setToken / clearToken / modelsApi / threadsApi / authApi`（api-client.js）
- `showConfirm / showModal`（modal.js）

## 💡 设计思想

1. **"每页一个 render(container)"路由约定**：对齐原版 router.js 形态——页面模块只导出 `render(container)`（把自己画进容器）并返回 cleanup；`main.js` 持有全局布局（顶栏/tabs），切标签时先调旧页 cleanup 再挂新页，防事件泄漏。
2. **前端永远写相对路径 `/api/*`**：vite dev 由 proxy 转发到 gateway（对齐原版 api-client.js 的 apiUrl 逻辑，页面代码不写死 gateway 地址）。
3. **两段式 SSE 流式**：`POST /api/runs`（拿 run_id + thread_id）→ `GET /api/runs/{id}/stream`（消费 delta/done/error 事件）——onCreated 回填会话 id，onDelta 逐块追加，onDone 落全文。
4. **登录态 = localStorage token**：学习版最小会话保持；后端 JWT 校验中间件为 M8.1 增强。
5. **学习版边界（用户既定接受）**：不照搬原版 ChatApp.tsx（16879 行）与 zcode 组件体系；"薄壳 + 单页 React + SSE 流式"最小闭环覆盖 5 个验收点，zcode 体系为 M8.1 精读方向。

## 🎯 实用场景

1. `pnpm dev` → 浏览器打开 localhost:5173，admin/admin123 登录 → 聊天页发消息看流式回复 → 模型设置页增改模型/设默认（不重启代码下次对话生效）。
2. 学习对接"前端页面 ↔ gateway 路由"的接缝：api-client 是唯一请求通道，页面不直接 fetch。

## 🧩 顺序执行链

```text
浏览器 localhost:5173
  ──> main.js boot()
      ├─ 有 token → buildShell() → switchTab('chat') → renderChat()
      └─ 无 token → renderLogin()
  ──> 聊天页发消息
      ──> streamSSE({message, threadId})
          ├─ POST /api/runs（vite proxy → gateway :38012）
          ├─ onCreated → 回填 thread_id + refreshThreads()
          └─ GET /api/runs/{id}/stream → onDelta 逐块 / onDone 落全文
```

## ❓ Q&A / 知识点

**Q: 为什么 models.js 的编辑表单里 api_key 留空 = 不变？**
A: PATCH 语义——`modelsApi.update` 传 `{...}`，后端 `model_dump(exclude_unset=True)` 只处理显式字段；前端在编辑时 `delete body.api_key`（留空），后端白名单不收 None 就不改 key。新增时必传。

**Q: pnpm install 报 `ERR_PNPM_IGNORED_BUILDS` 是什么？**
A: pnpm 10+ 默认禁止依赖运行构建脚本（安全机制）。vite 依赖的 esbuild 需要 postinstall 下载二进制，需白名单：`pnpm approve-builds --all` 生成 `pnpm-workspace.yaml` 的 `allowBuilds: {esbuild: true}`。注意 pnpm 12 已**不再读取** package.json 的 `pnpm` 字段（配置移入 pnpm-workspace.yaml）。

**Q: 新建会话的 thread_id 什么时候拿到？**
A: 两段式第一步 `POST /api/runs` 的响应里带 `thread_id`（thread_id 缺省时后端自动生成）——`onCreated` 回调立即回填到 `currentThreadId`，后续消息复用。

## ⚠️ 风险点

1. JWT 校验中间件未做（M8.1）——当前接口全开放，仅登录页有 token 概念
2. 聊天历史逐条恢复为 M8.1 增强（后端 threads 只存会话壳，消息历史走 checkpointer）
3. 生产构建（vite build）走同源 /api，需反代或 gateway 同源部署；学习版以 dev 模式为主
4. SSE 经 vite proxy 透传——生产（无 proxy）时需确认 gateway 直接可被前端访问

> 页脚：2026-10-17 · M8 前端工程 · 对标 `EvoFlow/evopanel/`（v1.1.0，学习版裁剪）
