# ============================================================================
# AgentFlow · agents/lead_agent/agent.py —— 主 Agent 构建
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/agents/lead_agent/agent.py
# 对标来源: evoflow/agents/lead_agent/agent.py
# 里程碑: M1（M2 加 tools + middlewares 挂载）
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────────────┐
# │ make_lead_agent(                                     │
# │     model: BaseChatModel,                            │
# │     checkpointer: Checkpointer,                      │
# │     tools: list[BaseTool] = [],                      │
# │     middlewares: list[AgentMiddleware] = [],         │
# │     system_prompt: str | None = None,                │
# │ ) → CompiledStateGraph                               │
# │                                                      │
# │   create_agent(model, tools, checkpointer,           │
# │                middleware)                           │
# │   = langchain 官方"模型↔工具"循环 Agent:              │
# │     模型 → 想调工具? → 调 → 结果回填 → 再想 → 回复    │
# │     每步状态自动过 checkpointer 存 SQLite            │
# │     middleware 挂横向能力（标题/线程目录等）          │
# │                                                      │
# │ 调用方: cli/main.py（stream 时传 thread_id）         │
# └──────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 参考文档：doc/doc-dev/01-里程碑/M2-工具与中间件.md §2
# 2. 状态类型默认用 create_agent 内置（messages + 中间件扩展字段），
#    自定义 ThreadState 在工具复杂化后再接入。
# 3. checkpointer 依赖注入：CLI 可换同步/异步，测试可换内存检查点。
# 4. 系统提示词默认由 prompt.py 构建（原版思想：时间/技能/工具段
#    都在 prompt 侧拼装，不散在调用处）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. make_lead_agent: 构建主 Agent（模型+检查点+工具+中间件 → 编译图）
# 🔒 内部私有函数
# 无
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. create_agent 的中间件参数名是【单数 middleware】（P-017）
# 2. tools/middlewares 列表为空时行为 = 纯对话 Agent（M1 形态），勿改默认
# 3. 系统提示词缺省走 prompt.py；直接传 system_prompt 会覆盖默认注入
# ============================================================================

from __future__ import annotations

# create_agent: langchain 的官方 Agent 构造器（与原版同款 API）
# 注意: 不要 from langgraph.prebuilt import create_agent——
#       prebuilt 1.0.8（锁定版）只有 create_react_agent；
#       langchain.agents.create_agent 在内部做了正确封装（含 checkpointer 支持）
from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver

# 提示词域（同包）：系统提示词构建（含当前时间注入，对齐原版 prompt.py）
from agentflow.agents.lead_agent.prompt import build_lead_agent_system_prompt


def make_lead_agent(
    model: BaseChatModel,
    checkpointer: BaseCheckpointSaver,
    tools: list[BaseTool] | None = None,
    middlewares: list[AgentMiddleware] | None = None,
    system_prompt: str | None = None,
):
    """构建主 Agent（M1 入口：模型 + 检查点 + 工具 + 中间件 + 系统提示词）。

    参数:
        model: 对话模型（factory.create_chat_model 产出）
        checkpointer: SQLite 检查点（thread_id 维度持久化状态）
        tools: 工具列表（M1 为空；M2 传 get_builtin_tools()）
        middlewares: 中间件列表（M2: TitleMiddleware / ThreadDataMiddleware）
        system_prompt: 系统提示词；缺省用 prompt.build_lead_agent_system_prompt()
                       （内含当前时间注入，学原版 prompt.py 的做法）

    返回:
        CompiledStateGraph: 已编译的 LangGraph，可 .stream() 调用

    设计说明:
        - 状态类型默认用 create_agent 内置（messages + 中间件扩展字段），
          自定义 ThreadState 在工具复杂化后再接入
        - checkpointer 传进来而不是在里面建——依赖注入，
          CLI 可换同步/异步，测试可换内存检查点
        - 系统提示词默认由 prompt.py 构建（原版思想：时间/技能/工具段
          都在 prompt 侧拼装，而不是散在调用处）
    """
    return create_agent(
        model=model,
        tools=tools or [],
        checkpointer=checkpointer,  # 每步状态落盘（会话可恢复的核心）
        middleware=middlewares or [],  # M2：挂横向能力中间件（参数名是单数 middleware）
        system_prompt=system_prompt or build_lead_agent_system_prompt(),
    )
