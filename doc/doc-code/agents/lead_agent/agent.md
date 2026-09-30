# agents/lead_agent/agent.py — agent.py

> **文件路径**: `backend/packages/harness/agentflow/agents/lead_agent/agent.py`
> **目录位置**: agents → lead_agent → agent.py
> **职责**: 主 Agent 构建

## 📋 结构图

```text
┌──────────────────────────────────────────────────────┐
│ make_lead_agent(                                     │
│     model: BaseChatModel,                            │
│     checkpointer: Checkpointer,                      │
│     tools: list[BaseTool] = [],                      │
│     middlewares: list[AgentMiddleware] = [],         │
│     system_prompt: str | None = None,                │
│ ) → CompiledStateGraph                               │
│                                                      │
│   create_agent(model, tools, checkpointer,           │
│                middleware)                           │
│   = langchain 官方"模型↔工具"循环 Agent:              │
│     模型 → 想调工具? → 调 → 结果回填 → 再想 → 回复    │
│     每步状态自动过 checkpointer 存 SQLite            │
│     middleware 挂横向能力（标题/线程目录等）          │
│                                                      │
│ 调用方: cli/main.py（stream 时传 thread_id）         │
└──────────────────────────────────────────────────────┘
```

## 📤 关键导出

**函数**

- `make_lead_agent()`

## 💡 设计思想

1. 参考文档：doc/doc-dev/01-里程碑/M2-工具与中间件.md §2
2. 状态类型默认用 create_agent 内置（messages + 中间件扩展字段），
   自定义 ThreadState 在工具复杂化后再接入。
3. checkpointer 依赖注入：CLI 可换同步/异步，测试可换内存检查点。
4. 系统提示词默认由 prompt.py 构建（原版思想：时间/技能/工具段
   都在 prompt 侧拼装，不散在调用处）。

## 🎯 实用场景

1. 主 Agent 构建：make_lead_agent 装配模型+检查点+工具+中间件
2. 会话持久化：create_agent checkpointer 参数让每步状态落 SQLite
3. M2 扩展点：tools/middlewares 参数挂工具目录与横向能力

## ⚠️ 风险点

1. create_agent 的中间件参数名是【单数 middleware】（P-017）
2. tools/middlewares 列表为空时行为 = 纯对话 Agent（M1 形态），勿改默认
3. 系统提示词缺省走 prompt.py；直接传 system_prompt 会覆盖默认注入

## ❓ Q&A / 知识点（问答自动归档区）

### checkpointer 是如何注入 langgraph 的？（2026-09-30 用户提问）

**链路**（注入点就在 `create_agent`）：

```text
main.py ⑤  create_sqlite_checkpointer(db_path)
              └─ 返回 SqliteSaver（langgraph 的 SQLite 存档员，持连接）
main.py ⑨  make_lead_agent(checkpointer=checkpointer, ...)
              └─ 本文件 return create_agent(
                     model=model,
                     tools=tools or [],
                     checkpointer=checkpointer,   ← 注入点
                     middleware=middlewares or [],
                     system_prompt=...,
                 )
              └─ langchain 内部：create_agent → langgraph 编译
                 → 返回 CompiledStateGraph（"图"）
                 → checkpointer 挂到图的 checkpointer 属性上
```

**"图"指什么**：`create_agent` 返回的 `CompiledStateGraph`——编译好的可执行图（模型↔工具循环）。图状态（graph state）= 运行中的 `messages` 列表 + 中间件扩展字段（如 `title`）。

**注入后 langgraph 内部做什么**（checkpointer 是被动对象，图主动用它）：

```text
agent.stream(config={"configurable": {"thread_id": "abc"}})
  │ 每执行完一步（super-step），图自动调存档员：
  saver.put(config, checkpoint, metadata, new_versions)
  │   → 图状态序列化 → 写 SQLite，按 thread_id 分档
  ▼
同一 thread_id 再跑 → 图初始化时：
  saver.get_tuple(config)
  │   → 按 thread_id 读回最近快照 → 填充图状态 → 上轮对话恢复
  ▼
继续 stream
```

**为什么不在 create_agent 里自己建 checkpointer（依赖注入）**：
CLI 传 SQLite 版（真实持久化），测试可传内存版（InMemorySaver 跑完自动清）——同一份 agent 代码不用改。

**一句话**：`create_sqlite_checkpointer(db_path)` 造存档员 → `create_agent(checkpointer=...)` 挂到图上 → langgraph 每步自动 `put`、按 `thread_id` `get_tuple`——这就是"同一 thread_id 恢复对话"的完整机制。

---
_自动生成于 doc-code 规范落地（2026-09-28）。来源：agent.py 头部注释 + 顶层符号。_
_2026-09-30 追加：Q&A 归档区（checkpointer 注入机制，用户提问自动归纳）。_
