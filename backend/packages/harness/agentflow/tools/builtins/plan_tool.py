# ============================================================================
# AgentFlow · tools/builtins/plan_tool.py —— 计划工具
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/tools/builtins/plan_tool.py
# 对标来源: evoflow/tools/builtins/plan_tool.py
#   原版 585 行：计划文档读写 + 中间件协作；M2 简化成
#   【会话内计划 dict】get/update/save。
# 里程碑: M2
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────────────┐
# │ _plan: dict —— 会话内计划存储（内存；原版是文档）           │
# │                                                             │
# │ plan_tool(action, plan_text) -> str                        │
# │   @tool("plan", return_direct=True)                        │
# │   get    → 读取当前计划（无则提示可 update 写入）           │
# │   update → 写入计划内容（plan_text 必填）                  │
# │   save   → 同 update（语义区分：保存到持久层，M2 同内存）   │
# └────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 计划是"任务级"能力：用户要求分步执行时，模型可把步骤写进
#    计划再逐项推进，避免上下文里反复重复计划全文。
# 2. M2 内存 dict 够用：单会话内读写；M3+ 落盘（文件/DB）时
#    只改存储实现，工具签名不动。
# 3. save 与 update 语义区分：update=改内存内容，save=持久化
#    （M2 两者同实现，为 M3+ 预留接口语义）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. plan_tool: 计划工具（LangChain @tool，注册名 "plan"）
# 🔒 内部私有函数
# 无
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. _plan 是模块级内存 dict：进程重启即清空（当前设计，调试够用）
# 2. update 无 plan_text 时返回错误提示，不可静默覆盖
# 3. save/update 语义在 M3+ 持久化时可能拆分，改动需同步 description
# ============================================================================
from __future__ import annotations

from typing import Literal

from langchain.tools import tool

# 会话内计划存储（原版计划是文档；M2 用内存 dict，后续 M 再落盘）
_plan: dict = {}


_PLAN_DESCRIPTION = """\
计划工具：维护当前任务的分步计划（get/update/save）。
当用户要求"先做个计划 / 按步骤来 / 更新计划"时使用。
action=get: 读取当前计划；action=update: 更新计划内容（plan_text 必填）；
action=save: 保存计划。
注意: 计划是会话级的，跨会话不保留。
"""


@tool("plan", description=_PLAN_DESCRIPTION, parse_docstring=False, return_direct=True)
def plan_tool(
    action: Literal["get", "update", "save"] = "get",
    plan_text: str | None = None,
) -> str:
    """维护任务计划（使用条件见工具 description）。"""
    if action == "update" or action == "save":
        if not plan_text:
            return "update/save 需要 plan_text 参数"
        _plan["content"] = plan_text
        return "计划已保存"
    if _plan.get("content"):
        return f"当前计划:\n{_plan['content']}"
    return "（暂无计划。需要时可用 plan update 写入）"
