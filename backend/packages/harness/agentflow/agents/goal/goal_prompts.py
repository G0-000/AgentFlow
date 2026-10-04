# ============================================================================
# AgentFlow · agents/goal/goal_prompts.py —— 长任务提示词构造
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/agents/goal/goal_prompts.py
# 对标来源: evoflow/agents/goal/goal_runtime.py
#   原版含远程流与 langgraph_sdk 注解；M5 裁成纯字符串模板。
# 里程碑: M5
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────────────┐
# │ build_goal_mode_preamble(goal_text) → str             │
# │   首转：要求模型吐严格 JSON steps 计划                  │
# │ build_continue_nudge(step: PlanStep) → str            │
# │   续跑：执行指定步，完成后用 <completed> 标签收尾       │
# └──────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 提示词 = 契约：preamble 定死 JSON 形状（plans/types.parse_steps_json
#    按此解析），nudge 定死收尾标签（goal_loop 判 "<completed>"）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. build_goal_mode_preamble: 计划阶段引导词
# 2. build_continue_nudge: 单步执行引导词
# ----------------------------------------------------------------------------

from __future__ import annotations

from agentflow.plans.types import PlanStep


def build_goal_mode_preamble(goal_text: str) -> str:
    """首转引导词：让主 Agent 先把长任务拆成 JSON 步骤计划，暂不动手执行。"""
    return (
        "你现在进入【长任务规划模式】。下面是用户的一个复杂长任务：\n"
        f"\n\"\"\"\n{goal_text}\n\"\"\"\n\n"
        "请先不要直接动手执行，而是把它拆成一组有序的执行步骤，"
        "只输出一个严格的 JSON 对象（不要任何解释、不要 markdown 代码块围栏），"
        "形状如下：\n"
        '{"steps":[{"ref":"s1","short_name":"短名","description":"该步骤要做什么",'
        '"depends_refs":[]}]}\n'
        "要求：\n"
        "1. ref 形如 s1/s2/s3……每个步骤唯一；\n"
        "2. depends_refs 填写本步依赖的前置步骤 ref 数组（无依赖填 []）；\n"
        "3. short_name 是不超过 15 字的短名；description 写清本步目标；\n"
        "4. 步骤总数控制在 3~12 步；\n"
        "5. 直接输出 JSON 对象本身。"
    )


def build_continue_nudge(step: PlanStep) -> str:
    """续跑引导词：让 Agent 执行指定步骤，并用 <completed> 标签声明本步完成。"""
    return (
        f"【执行步骤 {step.ref}】{step.short_name} —— {step.description}\n"
        "请完成这一步。完成后，请在回复末尾单独加上标签 <completed> 收尾，"
        "表示本步骤已完成；若尚未完成则不要加该标签。"
    )
