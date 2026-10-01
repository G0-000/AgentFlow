# ============================================================================
# AgentFlow · tools/builtins/dispatch_tool.py —— 子代理派发工具
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/tools/builtins/dispatch_tool.py
# 对标来源: evoflow/tools/builtins/subagent_tool.py（原版 task_tool，M4 简化为 dispatch_subagents）
# 里程碑: M4
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────────────┐
# │ dispatch_subagents(tasks, subagent, max_parallel)    │
# │   @tool("dispatch_subagents", return_direct=True)    │
# │   ① 查子代理配置（registry）                         │
# │   ② SubagentExecutor(cfg, tools, model)             │
# │   ③ dispatch_parallel(tasks, ≤3) 并行执行           │
# │   ④ 结果按任务顺序汇总回传                           │
# │                                                      │
# │ configure_dispatch_service(tools, model)             │
# │   CLI 装配时注入（子代理工具集 + 父模型）            │
# └──────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 主 Agent 的"分身术"入口：把一个大任务拆成多个独立小任务
#    列表 → 派给子代理并行 → 拿回结构化结果（验收点 1/2/3 闭环）。
# 2. 工具依赖注入（configure_dispatch_service）：dispatch 工具
#    不能自己建模型（模型由 CLI 统一创建），对齐 knowledge_tool
#    的 configure 注入模式。
# 3. 结果汇总逐任务编号，主 Agent 可直接读表拼接最终答案。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. dispatch_subagents: 子代理并行派发工具（注册名 "dispatch_subagents"）
# 2. configure_dispatch_service: 注入子代理工具集 + 父模型
# 🔒 内部私有函数
# 无
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. 工具集注入前调用 dispatch → 返回"未配置"提示（不炸模型循环）
# 2. max_parallel 硬上限 3（executor 内部再 min 一次，双保险）
# 3. 子代理工具集不要传 dispatch_subagents 自己（config 黑名单也排了）
# ============================================================================

from __future__ import annotations

from langchain.tools import BaseTool, tool
from langchain_core.language_models import BaseChatModel

from agentflow.subagents import (
    SubagentExecutor,
    get_subagent_config,
    get_subagent_names,
)
from agentflow.subagents.config import SubagentConfig

# 派发服务句柄（CLI 装配注入；未注入时给友好提示）
_subagent_tools: list[BaseTool] | None = None
_subagent_model: BaseChatModel | None = None


def configure_dispatch_service(
    tools: list[BaseTool] | None,
    model: BaseChatModel | None,
) -> None:
    """注入子代理工具集 + 父模型（CLI main() 装配时调用）。"""
    global _subagent_tools, _subagent_model
    _subagent_tools = tools
    _subagent_model = model


_DISPATCH_DESCRIPTION = """\
子代理并行派发工具：把多个独立任务派给子代理并行执行，汇总结果后返回。
当任务可拆分成多个互不依赖的小任务（如"同时查 A 和 B 两个文件"、"并行处理 3 个数据源"）时使用。
参数:
- tasks: 任务描述列表（每个元素是一个独立子任务，会被单独派发）
- subagent: 子代理类型（默认 general-purpose；可选: general-purpose, bash）
- max_parallel: 并行上限（默认 3，最多 3 个同时跑）
用法示例: tasks=["总结 a.md 内容", "总结 b.md 内容"] → 两个子代理并行处理，各自返回结果。
"""


@tool("dispatch_subagents", description=_DISPATCH_DESCRIPTION, parse_docstring=False, return_direct=True)
def dispatch_subagents(
    tasks: list[str],
    subagent: str = "general-purpose",
    max_parallel: int = 3,
) -> str:
    """把任务列表派给子代理并行执行，返回按顺序汇总的结果。"""
    if not tasks:
        return "（没有任务可派发）"
    if len(tasks) > 10:
        return f"（任务过多：{len(tasks)} 个，单次最多 10 个）"
    cfg: SubagentConfig | None = get_subagent_config(subagent)
    if cfg is None:
        return f"（未知子代理: {subagent}；可选: {', '.join(get_subagent_names())}）"
    if _subagent_model is None or _subagent_tools is None:
        return "（派发服务未配置：CLI 未注入子代理工具集/模型）"
    executor = SubagentExecutor(cfg, _subagent_tools, model=_subagent_model)
    results = executor.dispatch_parallel(tasks, max_parallel=max_parallel)
    # 结果回传：逐任务编号汇总（主 Agent 直接读表拼答案）
    lines: list[str] = []
    for i, (task, r) in enumerate(zip(tasks, results), start=1):
        body = r.result if r.status.value == "completed" else f"[{r.status.value}] {r.error}"
        lines.append(f"【任务{i}】{task}\n→ {body}")
    return "\n\n".join(lines)
