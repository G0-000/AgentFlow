# ============================================================================
# AgentFlow · tools/tools.py —— 工具收集模块（延迟加载 + 去重 + 按Tier排序）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/tools/tools.py
# 对标来源: evoflow/tools/tools.py
#   原版共 566 行：get_builtin_tools 使用 lru_cache + 函数内 import 实现延迟加载，
#   原版包含 50+ 工具、退役工具表、工具别名、社区工具等完整能力。
#   当前 M2 版本做精简裁剪：仅保留【工具收集 + 去重 + 按 tier 排序】核心逻辑。
# 里程碑: M2
# built-in = 内置的、原生自带
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────────────┐
# │ get_builtin_tools() -> tuple[BaseTool, ...]                 │
# │   @lru_cache：首次调用才导入 5 个工具模块，加快项目启动速度  │
# │   返回内置工具元组：(clarification, todo, knowledge, plan,  │
# │                     fetch_url)                              │
# │                                                             │
# │ _finalize_tool_catalog(tools) -> list[BaseTool]             │
# │   工具目录后置处理：                                         │
# │     ① 根据工具 name 去重，保留第一个出现的工具定义          │
# │     ② 依据 ToolTier 优先级顺序进行排序（runtime → core →    │
# │        workspace → …）                                      │
# │                                                             │
# │ get_available_tools() -> list[BaseTool]                     │
# │   对外入口：输出最终挂载给 Agent 使用的工具列表             │
# └────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 参考文档：doc/doc-dev/01-里程碑/M2-工具与中间件.md §2
# 2. 原版 EvoFlow 设计动机：工具数量庞大（50+），启动时一次性全部 import
#    会拖慢启动；使用 @lru_cache + 函数内部 import 实现延迟加载：
#    仅第一次调用 get_builtin_tools 时加载，后续直接复用缓存。
# 3. M2 精简改造：移除退役工具表、工具别名、社区工具、沙箱相关逻辑，
#    只保留核心收集流程。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. get_builtin_tools: 加载内置工具集合，带缓存延迟加载
# 2. get_available_tools: Agent 使用的最终工具入口
# 🔒 内部私有函数
# 1. _finalize_tool_catalog: 工具列表后置处理（去重 + 排序）
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. TOOL_TIER_ORDER 元组顺序直接影响工具排序结果，不可随意调整
# 2. get_builtin_tools 带有 lru_cache 缓存；修改工具定义后，需要清空缓存才能生效
# 3. 去重规则：按工具 name 字段，保留最先出现的工具，丢弃后续同名工具
# ============================================================================
from __future__ import annotations

from functools import lru_cache

from langchain.tools import BaseTool

from agentflow.tools.tool_catalog import resolve_tool_tier, tier_sort_key


@lru_cache(maxsize=1)
def get_builtin_tools() -> tuple[BaseTool, ...]:
    """收集全部内置工具（延迟加载：函数内 import，照原版）。

    为什么延迟：5 个工具模块含 requests 等重量依赖，
    全部模块级 import 会拖慢 CLI 启动；lru_cache 保证只加载一次。
    """
    from agentflow.tools.builtins.clarification_tool import ask_clarification_tool
    from agentflow.tools.builtins.dispatch_tool import dispatch_subagents
    from agentflow.tools.builtins.fetch_url_tool import fetch_url_tool
    from agentflow.tools.builtins.file_tools import read_file, write_file
    from agentflow.tools.builtins.knowledge_tool import knowledge_tool
    from agentflow.tools.builtins.plan_tool import plan_tool
    from agentflow.tools.builtins.terminal_tool import terminal_run
    from agentflow.tools.builtins.todo_tool import todo_tool

    return (
        ask_clarification_tool,
        todo_tool,
        knowledge_tool,
        plan_tool,
        fetch_url_tool,
        terminal_run,
        read_file,
        write_file,
        dispatch_subagents,
    )


def _finalize_tool_catalog(tools: list[BaseTool]) -> list[BaseTool]:
    """工具目录收尾：去重 + 按 tier 排序（照原版思想，简化版）。

    去重规则：同名只保留第一个（避免重复注册报错/重复挂载）。
    排序规则：runtime → core → workspace → plan → goal → optional → retired。
    """
    seen: set[str] = set()
    unique: list[BaseTool] = []
    for t in tools:
        name = (t.name or "").strip().lower()
        if not name or name in seen:
            continue
        seen.add(name)
        unique.append(t)
    return sorted(unique, key=lambda t: tier_sort_key(resolve_tool_tier(t.name)))


def get_available_tools() -> list[BaseTool]:
    """返回最终给 Agent 挂载的工具列表（M2 = 全部内置工具）。"""
    return _finalize_tool_catalog(list(get_builtin_tools()))
