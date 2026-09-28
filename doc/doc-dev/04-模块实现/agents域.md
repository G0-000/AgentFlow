<!-- ============================================================
  AgentFlow doc · 文档注释
  更新时间: 2026-09-28
  维护约定: 本文件内容随里程碑推进更新；接手 AI 先读标题与正文引言。
  关联项目: AgentFlow（仿写 EvoFlow，原版参照 /Users/main/EvoFlow 只读）
================================================================ -->
# agents 域（实现说明）

> 对应原版：`evoflow/agents/`。项目的心脏。M1 只有三块：ThreadState / checkpointer / lead_agent。

## 核心思想：状态先行

原版 `thread_state.py` 里，图的一切信息都在 **ThreadState 这一个 dict** 里流转：

```python
class ThreadState(AgentState):      # AgentState 自带 messages + add_messages reducer
    thread_id: NotRequired[str | None]
    # M2 扩展：sandbox / thread_data / ui_messages ...
```

LangGraph 图的骨架 = 节点读写这个状态；中间件 = 在节点前后横切改状态。
**先搞清楚状态长什么样，才能写对逻辑**——这是 M1 最重要的心智模型。

## 文件逐个看

### `agents/thread_state.py`
- 继承 `langchain.agents.AgentState`：messages 字段 + 追加 reducer 直接可用
- M1 只加 `thread_id`；注释里预告 M2 扩展位（sandbox/thread_data/ui_messages）

### `agents/checkpointer/provider.py`
```python
def create_sqlite_checkpointer(db_path) -> SqliteSaver:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    return SqliteSaver(conn)   # 直接构造；原版注释明确不用 from_conn_string
```
- 一行代码实现"图状态自动持久化"：每次节点执行后写入 SQLite
- 会话恢复 = 同一 thread_id 重新 invoke，checkpointer 自动加载历史
- 注意：3.x 的 from_conn_string() 返回上下文管理器（P-010），原版也是直接 SqliteSaver(conn)

### `agents/checkpointer/async_provider.py`
- 对齐原版入口名（原版 langgraph.json 指向这里）；M1 薄封装同步版，M2 流式化

### `agents/lead_agent/agent.py`
```python
def make_lead_agent(model, checkpointer, tools=None, system_prompt=None):
    agent = create_agent(
        model=model,
        tools=tools or [],          # M1 空；M2 传工具目录
        checkpointer=checkpointer,  # 会话持久化
        system_prompt=system_prompt or build_lead_agent_system_prompt(),
    )                               # M1：0 工具，0 中间件
    return agent
```
- 对照原版 1700 行：M1 是**种子**，注释里预留 M2 扩展点（工具目录 + 中间件链）
- 系统提示词由 `prompt.py` 构建（含当前时间注入——原版无独立时间工具）
- 返回 `CompiledStateGraph`——可直接 `.invoke()` / `.stream()`

### `agents/lead_agent/prompt.py`（M1 新增，对齐原版同款文件）
```python
def format_runtime_now_for_prompt(dt=None) -> str:
    return "2026-09-28 周一 (UTC+08:00)"  # 原版同款格式（时间/星期/UTC偏移）
```
- 时间问题靠 **system prompt 注入** 而非工具（原版真实做法）
- M2 起在此追加技能段/工具段（学原版 get_skills_prompt_section 等）

## 验证过的调用方式（cli 里用的）

```python
config = {"configurable": {"thread_id": thread_id}}
for chunk in agent.stream({"messages": [("user", user)]}, config=config):
    ...
```
- `thread_id` 放在 config 的 configurable 里 → checkpointer 按它存取状态
- `.stream()` 逐块产出 → M2 流式输出的基础

## 扩展点（后续里程碑）

| 里程碑 | 加什么 |
|---|---|
| M2 | 中间件链（memory/title/transcript 雏形）+ tool_catalog 加载工具 |
| M3 | memory 中间件注入记忆、知识库工具 |
| M4 | subagents（并行派活）+ sandbox |
| M5 | goal_graph + goal_runtime（长任务引擎） |
