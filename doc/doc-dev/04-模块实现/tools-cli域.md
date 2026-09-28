<!-- ============================================================
  AgentFlow doc · 文档注释
  更新时间: 2026-09-28
  维护约定: 本文件内容随里程碑推进更新；接手 AI 先读标题与正文引言。
  关联项目: AgentFlow（仿写 EvoFlow，原版参照 /Users/main/EvoFlow 只读）
================================================================ -->
# tools 域 + cli 域（实现说明）

> 对应原版：`evoflow/tools/` + `evoflow/cli/`。M1 的工具域为空壳（原版无独立时间工具），cli 是验收入口。

## tools 域

### 为什么工具要"独立成文件"而不是写在 agent 里

原版思想：**工具与 Agent 解耦**——工具是注册进目录的独立单元（有 schema、有分组），Agent 只声明"我用哪些工具"。好处：
- 工具可复用（多个 Agent 共享）
- 工具可测试（不启动 Agent 也能单测）
- M2 的 tool_catalog 就是"工具的注册表"

### M1 为什么没有 datetime 工具（学原版的关键一例）

原版 **没有** 独立的"当前时间工具"——时间靠 `agents/lead_agent/prompt.py` 的
`format_runtime_now_for_prompt()` 注入 system prompt：

```python
# agentflow/agents/lead_agent/prompt.py（M1 已实现，原版同款函数名/格式）
def format_runtime_now_for_prompt(dt=None) -> str:
    return "2026-09-28 周一 (UTC+08:00)"   # 本地时间 + 中文星期 + UTC 偏移

def build_lead_agent_system_prompt() -> str:
    return "...当前系统时间：" + format_runtime_now_for_prompt()
```

- 模型直接从 system prompt 读到当前日期，**无需工具调用**（省一次模型↔工具往返）
- 这正是原版的设计取舍，M1 照做；M2 学 tool_catalog 时才引入真正的工具（web_search 等）

## cli 域

### `cli/main.py` — 终端对话循环

流程：
```
load_dotenv() → load_config() → 校验 api_key
→ init_db()（建表）→ make_checkpointer() → make_lead_agent()
→ 循环：input("你 > ") → agent.stream({messages}, {thread_id}) → 打印 Agent 回复
```

### 为什么能验证"会话持久化"

```python
thread_id = args.thread or uuid.uuid4().hex[:12]
# 第一次跑：自动生成新 id
# 第二次跑：--thread <同一 id> → checkpointer 从 SQLite 加载历史 → Agent 记得之前的话
```

### 入口注册（仿原版）

```toml
# packages/harness/pyproject.toml
[project.scripts]
agentflow = "agentflow.cli.main:main"
```
→ 装好后可直接 `uv run agentflow`（不用 `python -m`）

## 扩展点（后续里程碑）

| 里程碑 | 加什么 |
|---|---|
| M2 | `tools/tool_catalog.py`（注册/分组/按需加载）+ 更多 builtins + `tool_result_store.py` |
| M4 | `tools/host_direct/`（read_file/write_file/terminal 直连）+ sandbox |
| M6 | mcp 工具接入（tools 目录里的工具直接来自外部服务器） |
