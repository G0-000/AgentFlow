# ============================================================================
# AgentFlow · subagents/builtins/__init__.py —— 内置子代理注册表
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/subagents/builtins/__init__.py
# 对标来源: evoflow/subagents/builtins/__init__.py（原版 12 个，M4 只留 2 个）
# 里程碑: M4
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────────────┐
# │ BUILTIN_SUBAGENTS: dict[str, SubagentConfig]         │
# │   "general-purpose" → GENERAL_PURPOSE_CONFIG         │
# │   "bash"            → BASH_AGENT_CONFIG              │
# │   registry 查表键 = 子代理 name                      │
# └──────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 代码侧默认配置集中一处（原版同款）；后续 M5 再学
#    "agents 目录持久化配置覆盖"。
# 2. M4 只内置 2 个最小子代理，够验证"派发-并行-回传"链路。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. BUILTIN_SUBAGENTS: 内置子代理注册表（name → config）
# 🔒 内部私有函数
# 无
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. 新增子代理 = 加配置文件 + 在此注册（键名必须等于 config.name）
# 2. 注册表键与 config.name 不一致 → registry 查不到（静默失败）
# ============================================================================

from __future__ import annotations

from agentflow.subagents.builtins.bash_agent import BASH_AGENT_CONFIG
from agentflow.subagents.builtins.general_purpose import GENERAL_PURPOSE_CONFIG

__all__ = ["BASH_AGENT_CONFIG", "BUILTIN_SUBAGENTS", "GENERAL_PURPOSE_CONFIG"]

# 内置子代理注册表：name → SubagentConfig
# 键名必须与 config.name 一致（registry.get_subagent_config 按 name 查表）
BUILTIN_SUBAGENTS: dict[str, object] = {
    "general-purpose": GENERAL_PURPOSE_CONFIG,
    "bash": BASH_AGENT_CONFIG,
}
