# ============================================================================
# AgentFlow · subagents/registry.py —— 子代理注册表
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/subagents/registry.py
# 对标来源: evoflow/subagents/registry.py
#   原版含文件系统 agents + SOUL + config.yaml 覆盖；M4 只做内置注册表查表。
# 里程碑: M4
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────────────┐
# │ get_subagent_config(name) → SubagentConfig | None    │
# │   查 BUILTIN_SUBAGENTS；未知名返回 None               │
# │                                                      │
# │ list_subagents() → list[SubagentConfig]              │
# │   全部内置子代理（按注册表顺序）                      │
# │                                                      │
# │ get_subagent_names() → list[str]                     │
# │   name 列表（CLI 启动信息/工具 description 用）       │
# └──────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 注册与查表分离：builtins 注册，registry 查表，
#    executor 只认 SubagentConfig，不感知注册来源。
# 2. 查不到返回 None 而非抛异常：dispatch 工具拿到 None
#    给友好提示（"未知子代理"），不崩模型循环。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. get_subagent_config: 按 name 取子代理配置（无则 None）
# 2. list_subagents: 列出全部内置子代理
# 3. get_subagent_names: 全部子代理 name
# 🔒 内部私有函数
# 无
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. 注册表键与 config.name 必须一致（否则查不到）
# 2. M4 无文件系统 agents/config.yaml 覆盖；M5 扩展 registry 时
#    保持三个对外函数签名不变
# ============================================================================

from __future__ import annotations

from agentflow.subagents.builtins import BUILTIN_SUBAGENTS
from agentflow.subagents.config import SubagentConfig

# 类型别名：注册表是 name → SubagentConfig 的映射（builtins 用 object 规避导入环）
_SUBAGENT_MAP: dict[str, SubagentConfig] = {
    name: cfg for name, cfg in BUILTIN_SUBAGENTS.items() if isinstance(cfg, SubagentConfig)
}


def get_subagent_config(name: str) -> SubagentConfig | None:
    """按 name 取子代理配置；未注册返回 None（dispatch 工具据此给友好提示）。"""
    return _SUBAGENT_MAP.get(name)


def list_subagents() -> list[SubagentConfig]:
    """列出全部内置子代理配置（按注册表顺序）。"""
    return list(_SUBAGENT_MAP.values())


def get_subagent_names() -> list[str]:
    """全部子代理 name（CLI 启动信息 / 派发工具 description 用）。"""
    return [cfg.name for cfg in list_subagents()]
