# ============================================================================
# AgentFlow · agents/goal/goal_graph.py —— goal_agent LangGraph 图声明入口
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/agents/goal/goal_graph.py
# 对标来源: evoflow/agents/goal/goal_graph.py
# 里程碑: 对齐审计差异 #4（补 langgraph.json 的 goal_agent 入口声明）
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────────────────┐
# │ make_goal_graph(config=None, runtime=None)              │
# │   → GoalGraph 句柄（占据"goal_agent 编译图入口"位置）     │
# │                                                          │
# │ GoalGraph.build(agent, model, goal_repo, service=None)   │
# │   → GoalEngine（M5 同步外部 while 闭环，真实可跑）           │
# │                                                          │
# │ langgraph.json:                                          │
# │   graphs.goal_agent =                                    │
# │     "agentflow.agents.goal.goal_graph:make_goal_graph"   │
# └──────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 原版 make_goal_graph(config, runtime) 返回 StateGraph.compile()——
#    节点 goal_controller + main_agent，条件边 START/controller/main_agent。
# 2. AgentFlow M5 未移植 StateGraph 节点链（goal_loop.py 是同步外部 while
#    闭环 GoalEngine，对标原版 goal_runtime 的裁剪版）。为诚实对齐，本文件
#    不伪造 StateGraph：make_goal_graph 返回一个轻量句柄 GoalGraph，它在
#    "编译图入口"这一声明位置上占位，.build() 再装配出真实的 GoalEngine。
# 3. 完整 StateGraph 移植（goal_controller/main_agent 节点 + 条件边）列 M8+
#    后续；本文件只是对齐声明 + 学习参照的最小骨架。
# ----------------------------------------------------------------------------
# 🎯 【四、实用场景】
# 1. langgraph.json 的 graphs.goal_agent 指向本函数（声明对齐，可被
#    langgraph dev / CLI 按字符串定位）。
# 2. 代码侧需要"拿到 goal_agent 可运行体"时：先句柄 = make_goal_graph()，
#    再 engine = handle.build(agent, model, goal_repo)，随后
#    engine.start(thread_id, goal_text) / engine.resume(thread_id)。
# ----------------------------------------------------------------------------
# 📊 【五、顺序执行链流程图】
#   langgraph.json:make_goal_graph
#     └─▶ GoalGraph(config, runtime)        # 占位句柄，不碰模型/库
#           └─▶ .build(agent, model, goal_repo)
#                 └─▶ GoalEngine(...)          # M5 真实闭环
#                       ├─ .start()  → while 闭环
#                       └─ .resume() → 断点续跑
# ----------------------------------------------------------------------------
# 🧩 【六、代码解析】
# - GoalGraph：仅持有 config/runtime（与原版入口参数对齐），不做副作用。
# - build(...)：纯转发到 GoalEngine 构造（依赖仍由调用方注入，对齐
#   lead_agent 的依赖注入思想）。
# - make_goal_graph：签名 (config=None, runtime=None) 对齐原版
#   (config, runtime)，但用 Any 弱耦合——AgentFlow 不直接消费 RunnableConfig。
# ----------------------------------------------------------------------------
# 📌 【七、Q&A】
# Q1: 为什么不直接 build StateGraph？
# A: AgentFlow 当前无 goal_controller_node / main_agent_node / GoalState
#    图状态，伪造会"声明一套跑不起来的图"，违反诚实原则。
# Q2: make_goal_graph() 无参可调用吗？
# A: 可。config/runtime 都有默认值，返回句柄；真正跑长任务再 .build()。
# ----------------------------------------------------------------------------
# ⚠️ 【八、风险点 / 偏差】
# 1. 本入口不是 LangGraph CLI 期望的 compiled StateGraph——纯代码装配项目
#    下 langgraph.json 是对齐声明 + 学习参照，勿直接 langgraph dev 启动。
# 2. 完整 StateGraph 移植列 M8+；届时 GoalGraph 句柄可替换为真编译图。
# ============================================================================

from __future__ import annotations

from typing import Any

# GoalEngine：M5 真实闭环（goal_loop.py）——本入口的"最小等价可运行体"
from agentflow.agents.goal.goal_loop import GoalEngine


class GoalGraph:
    """``goal_agent`` 入口句柄（对齐原版 compiled StateGraph 的位置）。

    原版 evoflow .../goal_graph.py 的 ``make_goal_graph`` 返回
    ``StateGraph(...).compile()``（节点 ``goal_controller`` + ``main_agent``，
    条件边路由）。AgentFlow M5 未移植 StateGraph 节点链，而是以同步外部
    while 闭环 ``GoalEngine`` 为最小等价。本句柄占据"goal_agent 编译图入口"
    这一声明位置，实际通过 :meth:`build` 装配出 ``GoalEngine``。
    """

    def __init__(self, config: Any = None, runtime: Any = None) -> None:
        """记录入口参数（与原版 make_goal_graph(config, runtime) 对齐）。

        这里不做任何模型/数据库副作用——只占位，保持"拿到图"那一步轻量。
        """
        self._config = config
        self._runtime = runtime

    def build(self, agent, model, goal_repo, service=None) -> GoalEngine:
        """装配长任务引擎（等价于原版"拿到可运行编译图"的那一刻）。

        参数:
            agent: 主 Agent（sync compiled graph，经 make_lead_agent 构建）
            model: 判定模型（goal_judge 用）
            goal_repo: goals 表仓库（GoalRepository，db_path 模式）
            service: 可选 GoalStateService；缺省由 GoalEngine 内部包一层

        返回:
            GoalEngine: 真实可跑的 M5 闭环（.start() / .resume()）
        """
        return GoalEngine(agent, model, goal_repo, service)

    def __repr__(self) -> str:
        return "<GoalGraph goal_agent=GoalEngine(minimal-equivalent M5)>"


def make_goal_graph(config: Any = None, runtime: Any = None) -> GoalGraph:
    """LangGraph Server 入口（声明对齐）：``goal_agent``。

    原版返回 goal_controller↔main_agent 的 ``StateGraph`` compiled graph。
    AgentFlow 当前以同步 ``GoalEngine`` 闭环为最小等价（M5），完整 StateGraph
    移植列 M8+ 后续。本函数真实存在、可调用、返回 ``GoalGraph`` 句柄
    （``.build()`` 产出 ``GoalEngine``）——不伪装成已编译图。
    """
    return GoalGraph(config=config, runtime=runtime)


__all__ = ["GoalGraph", "make_goal_graph"]
