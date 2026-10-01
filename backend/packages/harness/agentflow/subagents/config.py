# ============================================================================
# AgentFlow · subagents/config.py —— 子代理配置
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/subagents/config.py
# 对标来源: evoflow/subagents/config.py
#   原版含 recursion_limit 换算 + 环境变量覆盖；M4 简化保留核心字段。
# 里程碑: M4
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────────────┐
# │ SubagentConfig(@dataclass)                           │
# │   name: 唯一标识（"general-purpose" / "bash"）       │
# │   description: 给主 Agent 看的"何时派这个子代理"      │
# │   system_prompt: 子代理行为说明书                    │
# │   tools: 工具白名单（None = 继承父级全部）           │
# │   disallowed_tools: 黑名单（默认排除递归派发）        │
# │   model: "inherit" = 用父模型（M4 只支持 inherit）    │
# │   max_turns / timeout_seconds: 执行上限              │
# └──────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 配置与注册分离：builtins 定义配置，registry 负责查表。
# 2. 默认黑名单防递归：子代理默认不能用 subagent/dispatch 工具
#    （否则子代理再派子代理 → 无限嵌套）。
# 3. M4 只支持 model="inherit"（与父 Agent 同模型）；
#    多模型（各自配模型）留到 M6。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. SubagentConfig: 子代理配置数据类
# 🔒 内部私有函数
# 无
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. disallowed_tools 默认值不可删：防子代理递归派发（无限循环）
# 2. tools=None 表示继承父级全部工具（_filter_tools 白名单不生效）
# ============================================================================

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SubagentConfig:
    """子代理配置（M4 最小版，对齐原版核心字段）。

    字段:
        name: 唯一标识（注册表查表键）
        description: 给主 Agent 看的说明（何时派这个子代理）
        system_prompt: 子代理行为说明书（注入其 system prompt）
        tools: 工具白名单；None = 继承父级全部工具
        disallowed_tools: 工具黑名单（始终排除）
        model: "inherit" = 用父模型（M4 仅支持此值）
        max_turns: 模型最大轮数（防失控）
        timeout_seconds: 单任务最长执行秒数
    """

    name: str
    description: str
    system_prompt: str
    tools: list[str] | None = None
    disallowed_tools: list[str] | None = field(
        default_factory=lambda: ["subagent", "dispatch_subagents", "ask_clarification"]
    )
    model: str = "inherit"
    max_turns: int = 100
    timeout_seconds: int = 120
