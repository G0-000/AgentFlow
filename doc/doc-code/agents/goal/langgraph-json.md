# backend/langgraph.json — LangGraph 图声明文件（对齐审计差异 #4）

> **文件路径**：`backend/langgraph.json`
> **对标来源**：`EvoFlow/backend/langgraph.json`（只读参照）
> **性质**：**对齐声明 + 学习参照**。AgentFlow 是纯代码装配项目，不依赖
> `langgraph` CLI / `langgraph dev` 运行——本文件不参与实际启动，但结构、
> 包名与入口字符串必须与原版同构，供架构对齐与后续真正接入 LangGraph
> Server 时直接复用。

## 📄 全文

```json
{
  "$schema": "https://langgra.ph/schema.json",
  "python_version": "3.12",
  "dependencies": ["."],
  "env": ".env",
  "graphs": {
    "lead_agent": "agentflow.agents.lead_agent.agent:make_lead_agent",
    "goal_agent": "agentflow.agents.goal.goal_graph:make_goal_graph"
  },
  "checkpointer": {
    "path": "./packages/harness/agentflow/agents/checkpointer/async_provider.py:make_checkpointer"
  }
}
```

## 🧩 与原版的逐项对齐

| 字段 | 原版 (evoflow) | AgentFlow | 对齐 |
| --- | --- | --- | --- |
| `$schema` | `https://langgra.ph/schema.json` | 同 | ✅ |
| `python_version` | `3.12` | `3.12` | ✅ |
| `dependencies` | `["."]` | `["."]` | ✅ |
| `env` | `.env` | `.env`（**声明保留，文件缺失**） | ⚠️ |
| `graphs.lead_agent` | `evoflow...agent:make_lead_agent` | `agentflow...agent:make_lead_agent` | ✅ 包名替换 |
| `graphs.goal_agent` | `evoflow...goal_graph:make_goal_graph` | `agentflow...goal_graph:make_goal_graph` | ✅ 指向新建骨架 |
| `checkpointer.path` | `.../async_provider.py:make_checkpointer` | `.../async_provider.py:make_checkpointer` | ✅ 指向追加工厂 |

## ⚠️ 三处必须知晓的偏差

### 偏差 1：`goal_agent` 入口是最小骨架，不是 compiled StateGraph

原版 `make_goal_graph(config, runtime)` 返回 `StateGraph(GoalState)` 编译产物
——含 `goal_controller` / `main_agent` 两个节点与条件边路由。AgentFlow M5
未移植该节点链，而是用同步外部 while 闭环 `GoalEngine`（见
[goal_loop.md](./goal_loop.md)）作为最小等价。

新建的 `agentflow/agents/goal/goal_graph.py` 里：

- `make_goal_graph(config=None, runtime=None)` **真实存在、可调用**；
- 返回的是轻量句柄 `GoalGraph`，其 `.build(agent, model, goal_repo)` 再
  装配出真实可跑的 `GoalEngine`；
- **不伪造 StateGraph**——避免声明一套跑不起来的图。
- 完整 StateGraph 移植列 **M8.1 后续**，届时句柄可替换为真编译图。

### 偏差 2：checkpointer 工厂已对齐为无参 async context manager（无多后端开关）

经评估，选择**在 `async_provider.py` 纯追加** `make_checkpointer()`
（不改既有 `create_async_sqlite_checkpointer`），因此 `checkpointer.path`
最对齐原版、无需标注"需传 db_path"。

- 已实现：无参 `@contextlib.asynccontextmanager`，进入打开 SQLite 连接 →
  `await setup()` 建表 → yield `AsyncSqliteSaver` → 退出关闭连接。
- 落库路径取 `config.paths.default_db_path()`（`data/agentflow.db`）。
- **与原版的差异**：原版读 `get_app_config().checkpointer`，支持
  memory / sqlite / postgres 三后端与 omit_transcript 包装；AgentFlow
  当前无此配置层，工厂固定落默认 SQLite。这是"工厂签名对齐、内部后端裁剪"。

### 偏差 3：`make_lead_agent` 签名不是 LangGraph CLI 入口形态

原版 `make_lead_agent` 是 LangGraph Server 入口（接收 `RunnableConfig`）。
AgentFlow 的 `make_lead_agent(model, checkpointer, tools, middlewares,
system_prompt)` 是**代码侧装配函数**——依赖由 CLI 显式注入，不是
`(config)` 形态的无参入口。因此本文件在 `graphs.lead_agent` 上做声明对齐，
但**它不能被 langgraph CLI 直接调用**（真正接入时需要再包一层
`(config)` → 解析依赖 → 调 `make_lead_agent(...)` 的适配）。

## 📁 `env: ".env"` 状态

`backend/.env` 当前**不存在**。`env` 字段按原版保留声明；一旦后续引入
环境变量加载（模型 key 等），在 `backend/` 放 `.env` 即生效，无需改本文件。

## 🎯 为什么仍要建这个文件

1. **结构对齐审计**：原版有 `langgraph.json`，仿写缺它即结构性差异 #4。
2. **入口字符串即地图**：`graphs.*` / `checkpointer.path` 把"谁是主 Agent、
   谁是长任务、检查点从哪来"落成可定位的字符串文档。
3. **未来零成本切换**：真接 LangGraph Server 时，文件结构已就位，只需把
   骨架句柄替换为真编译图、把 `make_lead_agent` 包成 `(config)` 入口。

***

*2026-10-13 新建：对齐审计差异 #4，补 `backend/langgraph.json` +
`goal_graph.py` 最小骨架 + `async_provider.make_checkpointer` 追加工厂；
文档记录三处偏差（goal_graph 最小骨架 / checkpointer 后端裁剪 /
make_lead_agent 签名非 CLI 形态）。*
