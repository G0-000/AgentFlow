# ============================================================================
# AgentFlow · agents 域 —— Agent 构建与状态
# ----------------------------------------------------------------------------
# 文件: backend/packages/harness/agentflow/agents/__init__.py
# 仿原: evoflow/agents/（原版 15 个子包，M1 只有 lead_agent + checkpointer）
# 里程碑: M1
# ----------------------------------------------------------------------------
# 结构图:
# ┌────────────────────────────────────────────────────────┐
# │ agents/ （Agent 域：图的状态 + 检查点 + 主 Agent）       │
# │   thread_state.py        图状态定义（ThreadState）      │
# │   checkpointer/          状态持久化（SQLite）           │
# │     provider.py          SqliteSaver（同步）            │
# │     async_provider.py    AsyncSqliteSaver（异步）       │
# │   lead_agent/            主 Agent                       │
# │     agent.py             make_lead_agent() 构建入口     │
# └────────────────────────────────────────────────────────┘
# ============================================================================
