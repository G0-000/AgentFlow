# agents/middlewares/title_middleware.py — title_middleware.py

> **文件路径**: `backend/packages/harness/agentflow/agents/middlewares/title_middleware.py`
> **目录位置**: agents → middlewares → title_middleware.py
> **职责**: 自动标题中间件

## 📋 结构图

```text
┌────────────────────────────────────────────────────────────┐
│ TitleMiddlewareState(AgentState)                           │
│   title: NotRequired[str | None]                            │
│                                                             │
│ TitleMiddleware(AgentMiddleware)                            │
│   state_schema = TitleMiddlewareState                       │
│   before_model(state, runtime) → dict | None                │
│     ① 取 messages 列表                                      │
│     ② 仅"首条消息 + 尚无标题"时生成标题                     │
│        title = 首条 user 消息前 20 字（规则截断）            │
│     ③ 返回 {"title": title} → merge 进图状态                │
│   （CLI 首轮对话后 get_state 读 title → 落库 sessions.title）│
└────────────────────────────────────────────────────────────┘
```

## 📤 关键导出

**类**

- `TitleMiddlewareState`
- `TitleMiddleware`

**常量**

- `_TITLE_MAX_CHARS`

## 💡 设计思想

1. 参考文档：doc/doc-dev/01-里程碑/M2-工具与中间件.md §2
2. 原版思想：标题是"横向能力"，挂在 AgentMiddleware 上，不进主图逻辑；
   标题生成只做一次（首条消息），避免重复 LLM 调用。
3. M2 简化：用规则截断而非 LLM（免费模型限流会挂，P-015）；
   后续想换 LLM 生成只需替换 _generate_title 内部实现。

## 🎯 实用场景

1. 会话列表显示：首条消息自动生成标题（截断 20 字），sessions.title 落库后列表可读
2. 免 LLM 稳定方案：规则截断不调模型，避开免费模型高峰限流（P-015）
3. 换 LLM 生成：后续想升级为智能标题只改 _generate_title 内部实现

## ❓ Q&A

**Q: 为什么不用 LLM 生成标题？**

A: 免费模型高峰限流（P-015）会让标题生成挂掉、拖慢首轮对话；规则截断 100% 稳定

**Q: 标题会重复生成吗？**

A: 不会——已有 title 时 before_model 直接返回 None，幂等

## ⚠️ 风险点

1. _TITLE_MAX_CHARS=20 是标题长度上限，调整影响 CLI 显示与落库标题
2. 幂等保证：已有 title 时 before_model 返回 None，不会重复生成
3. 只认 messages[0] 为 human 才生成；系统注入类消息（type!=human）不触发

---
_自动生成于 doc-code 规范落地（2026-09-28）。来源：title_middleware.py 头部注释 + 顶层符号。_
