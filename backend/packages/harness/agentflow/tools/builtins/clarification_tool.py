# ============================================================================
# AgentFlow · tools/builtins/clarification_tool.py —— 澄清工具
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/tools/builtins/clarification_tool.py
# 对标来源: evoflow/tools/builtins/clarification_tool.py（39 行，几乎照搬）
#   原版：会话脊柱工具（SESSION_SYSTEM_TOOL_NAMES 之一 → runtime 档）；
#   M2：占位实现（真正交互由中间件/UI 处理）。
# 里程碑: M2
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────────┐
# │ @tool("ask_clarification", return_direct=True)         │
# │   ask_clarification(question, clarification_type,      │
# │     context, options, questions, title, category)      │
# │   用途: 信息缺失/歧义/方案选择/风险确认时向用户提问     │
# │   类型: missing_info | ambiguous_requirement |         │
# │         approach_choice | risk_confirmation |          │
# │         suggestion                                    │
# │   返回: "澄清请求已发出，等待用户回答"（占位）          │
# └────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. return_direct=True 必须为 True：否则 langchain create_agent 会
#    把工具结果再送进模型循环——澄清问题还没答就又调一次澄清（死循环）。
# 2. 本工具是"占位"：真正交互由中间件/UI 处理（M2 CLI 直接打印提问），
#    工具本体只负责"把提问意图结构化地表达出来"。
# 3. docstring 即说明书：clarification_type 枚举约束了提问类型，
#    model 看到 description 就知道何时用、怎么填。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. ask_clarification_tool: 澄清工具（LangChain @tool，注册名
#    "ask_clarification"，return_direct=True）
# 🔒 内部私有函数
# 无
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. return_direct 不可改为 False（否则模型循环死循环）
# 2. clarification_type 枚举与 description 必须同步（模型按 description 填参）
# 3. M2 是占位返回；M6 接真实澄清交互时只改函数体，签名保持
# ============================================================================
from typing import Any, Literal

from langchain.tools import tool

_ASK_CLARIFICATION_DESCRIPTION = """\
用于向用户发起结构化澄清（不要只在对话里列选项）。
当任务因缺少信息/需求歧义/方案选择/风险确认而阻塞时使用；最多 3 个问题。
Single: question + options[]。Multi: questions[{prompt,options,id?,context?,allow_multiple?}] + title。
类型: missing_info | ambiguous_requirement | approach_choice | risk_confirmation | suggestion。
调用后执行暂停，等待用户在界面回答。
"""


# return_direct=True: 澄清结果直接返回，不再回模型循环（原版注释，照搬）
@tool(
    "ask_clarification",
    description=_ASK_CLARIFICATION_DESCRIPTION,
    parse_docstring=False,
    return_direct=True,
)
def ask_clarification_tool(
    question: str = "",
    clarification_type: Literal[
        "missing_info",
        "ambiguous_requirement",
        "approach_choice",
        "risk_confirmation",
        "suggestion",
    ] = "missing_info",
    context: str | None = None,
    options: list[str] | None = None,
    questions: list[dict[str, Any]] | None = None,
    title: str | None = None,
    category: str | None = None,
) -> str:
    """向用户发起结构化澄清（使用条件见工具 description）。"""
    # M2 占位实现：真正交互由中间件/UI 处理（原版同款做法）
    return "澄清请求已发出，等待用户回答"
