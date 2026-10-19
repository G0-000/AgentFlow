# evopanel/src/pages/chat-react.js — chat-react.js（聊天页）

> **文件路径**: `evopanel/src/pages/chat-react.js`
> **对标来源**: `EvoFlow/evopanel/src/pages/chat-react.js`（原版 27 行薄壳挂 ChatApp.tsx；学习版为可独立阅读的单文件，实现同等的"SSE 流式 + 会话切换"行为）
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
renderChat(container) → 左栏会话列表 + 右栏消息区 + 输入行

refreshThreads()   GET /api/threads → 列表渲染（active 高亮 + 删除按钮）
switchThread(id)   切换会话：清空消息区 + 提示"历史恢复为 M8.1"
send()             streamSSE({message, threadId, onCreated/onDelta/onDone/onError})
new-thread         清空 currentThreadId + 消息区（后端自动生成新 thread）
```

## 📤 关键导出

- `renderChat(container)` — 渲染聊天页，返回 cleanup（当前为空函数，main.js 切 tab 用）

## 💡 设计思想

1. **数据流对应 M7 gateway 两段式 runs**：发消息 → `streamSSE` 内部 POST /api/runs → GET stream → onDelta 逐块追加 / onDone 落全文。
2. **多会话最小语义**：后端 threads 只存会话壳（消息历史走 checkpointer），学习版以"切换会话后新消息进对应 thread_id"为最小语义；历史逐条恢复标注为 M8.1 增强。
3. **onCreated 回填会话 id**：首次发消息（无会话）时 POST /runs 响应带 thread_id → 立即回填 `currentThreadId` + 刷新列表——解决"新会话从哪里记住 id"。
4. **防重入**：`isStreaming` 标志 + 发送按钮禁用，同一时刻只允许一个流。

## 🎯 实用场景

1. 验收点 2（聊天页）：发消息看流式打字机回复。
2. 验收点 3（多会话）：新建/切换/删除会话，互不干扰。

## 🧩 顺序执行链

```text
用户输入 + Enter / 发送按钮
  ▼ send()
  ├─ 校验非空 && !isStreaming
  ├─ appendMsg('user', text) + 挂"思考中…"
  ├─ streamSSE({message, threadId: currentThreadId, ...})
  │   ├─ onCreated: 无 currentThreadId → 回填 run.thread_id + refreshThreads()
  │   ├─ onDelta:   assistantEl.textContent = 累积文本（打字机 + 自动滚动）
  │   ├─ onDone:    落全文（full || streamed || '空回复'）+ refreshThreads()
  │   └─ onError:   assistantEl 变 error 样式显示消息
  └─ finally: 移除"思考中…"、恢复 isStreaming/按钮、焦点回输入框
```

## ❓ Q&A / 知识点

**Q: 切换会话为什么不恢复历史消息？**
A: 后端 threads 表只存会话壳（thread_id/title/时间），消息历史在 langgraph checkpointer（按 thread_id 存）。恢复需要新端点（如 GET /api/threads/{id}/messages）——标注为 M8.1 增强，本期切换会话只保证"新消息进对会话"。

**Q: 删除当前会话后为什么清空消息区？**
A: 删除的会话 thread_id 失效，`currentThreadId` 置 null 回到"新会话"状态——避免后续消息发到已删除的 thread。

**Q: 为什么用 `el.textContent` 而不是 innerHTML 渲染回复？**
A: 模型输出不可信，textContent 天然防 XSS；会话标题等用户数据同样经 escapeHtml 转义。

## ⚠️ 风险点

1. 历史恢复缺失（M8.1）——验收清单已标注
2. 同一时刻单流（防重入）——多流并发为 M8.1 能力
3. 会话列表删除无确认框——学习版最小化；models 页有 showConfirm 可复用
4. escapeHtml 在文件底部定义（函数声明提升）——勿改成 const 箭头函数，否则提升失效

> 页脚：2026-10-17 · M8 聊天页 · 对标 `EvoFlow/evopanel/src/pages/chat-react.js`（原版薄壳挂 ChatApp.tsx，学习版单文件）
