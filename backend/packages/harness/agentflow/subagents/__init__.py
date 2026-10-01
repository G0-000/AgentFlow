# ============================================================================
# AgentFlow · subagents/__init__.py —— 子代理包入口
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/subagents/__init__.py
# 对标来源: evoflow/subagents/__init__.py（原版用 __getattr__ 延迟加载防环）
#   简化: M4 包小，直接导入（无循环风险）。
# 里程碑: M4
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────────────┐
# │ subagents/ 对外导出:                                   │
# │   SubagentConfig（config.py）                        │
# │   SubagentStatus / SubagentResult / SubagentExecutor │
# │   （executor.py）                                    │
# │   get_subagent_config / list_subagents（registry.py）│
# └──────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 包入口只 re-export，不承载逻辑（使用者 import subagents 一个点）。
# 2. M4 包小无需延迟加载；若未来 subagents 变重，再学原版 __getattr__。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. SubagentConfig / SubagentStatus / SubagentResult / SubagentExecutor
# 2. get_subagent_config / list_subagents / get_subagent_names
# 🔒 内部私有函数
# 无
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. 新增导出记得加进 __all__（否则 from subagents import * 拿不到）
# 2. 导入环风险：builtins 只依赖 config，registry 依赖 builtins，
#    executor 依赖 config——保持单向依赖
# ============================================================================

from __future__ import annotations

from agentflow.subagents.config import SubagentConfig
from agentflow.subagents.executor import (
    SubagentExecutor,
    SubagentResult,
    SubagentStatus,
    cleanup_background_task,
    get_background_task_result,
    list_background_tasks,
)
from agentflow.subagents.registry import (
    get_subagent_config,
    get_subagent_names,
    list_subagents,
)

__all__ = [
    "SubagentConfig",
    "SubagentExecutor",
    "SubagentResult",
    "SubagentStatus",
    "cleanup_background_task",
    "get_background_task_result",
    "get_subagent_config",
    "get_subagent_names",
    "list_background_tasks",
    "list_subagents",
]
