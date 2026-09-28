# tools/tool_result_store.py — tool_result_store.py

> **文件路径**: `backend/packages/harness/agentflow/tools/tool_result_store.py`
> **目录位置**: tools → tool_result_store.py
> **职责**: 工具结果存取模块（摘要截断 + 内存存储）

## 📋 结构图

```text
┌────────────────────────────────────────────────────────────┐
│ _PREVIEW_MAX_CHARS = 1200（预览截断阈值，照原版常量）        │
│ _SUMMARY_MAX_CHARS = 300（摘要默认展示长度）                │
│                                                             │
│ summarize_tool_result(text, max_chars) -> str               │
│   工具结果 → 聊天可见摘要（非字符串先转字符串，超长截断）    │
│                                                             │
│ ToolResultStore（内存版）                                   │
│   save(thread_id, tool_call_id, name, result) → 存完整结果   │
│   get(thread_id, tool_call_id) → 取完整结果                 │
│   summaries(thread_id) → 列出该线程全部摘要                 │
│   clear_thread(thread_id) → 清空某线程结果                  │
└────────────────────────────────────────────────────────────┘
```

## 📤 关键导出

**类**

- `ToolResultStore`

**函数**

- `summarize_tool_result()`

**常量**

- `_PREVIEW_MAX_CHARS`
- `_SUMMARY_MAX_CHARS`

## 💡 设计思想

1. 学原版：工具可能返回大结果（网页/文件），对话流只展示摘要；
   完整结果按 thread_id + tool_call_id 存这里，供后续引用 / UI 展示。
2. M2 用内存 dict（进程内有效）；M3+ 如需跨进程再落 SQLite。
3. 摘要与完整结果分开存，避免对话上下文被大结果撑爆（token 成本控制）。

## 🎯 实用场景

1. 对话流只显摘要：工具返回大结果（网页/文件/搜索）时，聊天里只展示截断摘要，避免刷屏与上下文爆炸
2. 追问引用完整结果：用户问"刚才那个网页具体内容"，Agent 按 thread_id+tool_call_id 取回原文
3. 调试审计：summaries(thread_id) 列出某会话全部工具调用摘要，排查"工具当时返回了什么"
4. UI 工具卡片（M7）：gateway 返回工具调用记录、前端渲染工具卡片时读 name+summary
5. 多会话隔离：thread 维度键设计，进程内多会话并行不串扰

## ❓ Q&A

**Q: 为什么摘要和原文分开存？**

A: 对话流 token 成本：只放摘要进上下文；原文按需取回，不重新调工具

**Q: 内存版会丢数据吗？**

A: 进程重启即丢；M3+ 跨进程场景落 SQLite 即可

## ⚠️ 风险点

1. _PREVIEW_MAX_CHARS / _SUMMARY_MAX_CHARS 是全局常量，调整影响所有摘要长度
2. 内存 dict 进程内有效；进程重启后结果丢失（当前仅调试用，可接受）

---
_自动生成于 doc-code 规范落地（2026-09-28）。来源：tool_result_store.py 头部注释 + 顶层符号。_
