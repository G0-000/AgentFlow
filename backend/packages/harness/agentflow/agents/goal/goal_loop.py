# ============================================================================
# AgentFlow · agents/goal/goal_loop.py —— 长任务外部 while 闭环引擎（M5）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/agents/goal/goal_loop.py
# 对标来源: evoflow/agents/goal/goal_runtime.py + goal_auto_continue_middleware.py
#   原版闭环在 middleware after_model 钩子 jump_to（伪 goal_graph）；
#   M5 砍 goal_graph/middleware 钩子，改同步外部 while（对齐 CLI 同步主循环）。
# 里程碑: M5
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────────┐
# │ GoalEngine(agent, model, goal_repo, service=None)       │
# │   start(thread_id, goal_text, max_steps=12)              │
# │     建 goal 行 → preamble invoke → 解析 JSON 计划 →      │
# │     topo_sort → update_plan → 自动授权 executing → _run   │
# │   resume(thread_id)                                     │
# │     get_active_by_thread 定位 → 恢复 steps → _run 续跑   │
# │   _run(thread_id, goal)                                 │
# │     while: next_ready_step → None 则 complete_task       │
# │     步数上限/空回复×2/fallback_streak≥3 → paused 断点    │
# └────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 写序固定（R3）：先 agent.invoke（checkpointer 落消息）→ 再写步状态 SQL；
#    恢复以 SQL 的 completed_steps/current_step 为坐标，checkpointer 只管消息。
# 2. 断点重跑：resume 时把 plan_steps_json 里残留 executing 的步重置回 pending
#    （杀进程最坏发生在"步已开跑未落完成"，幂等 nudge 重跑该步，可接受）。
# 3. 判定 continue 不 mark 完成：步 status 回落 pending，下一圈 while 重新捡起；
#    连续 continue 计 fallback_streak，≥3 熔断 paused（R1）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. GoalEngine: 长任务引擎
# 🔒 内部私有函数
# 1. _ai_text: 取 invoke 返回最后一条消息文本
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. 全程同步 invoke（lead_agent 是 sync compiled graph），勿改 async
# ============================================================================

from __future__ import annotations

import os

from langchain_core.messages import HumanMessage

from agentflow.agents.goal.goal_judge import judge_last_reply
from agentflow.agents.goal.goal_prompts import (
    build_continue_nudge,
    build_goal_mode_preamble,
)
from agentflow.agents.goal.goal_state import (
    STEP_STATUS_COMPLETED,
    STEP_STATUS_EXECUTING,
    STEP_STATUS_PENDING,
    GoalRow,
    goal_row_from_row,
)
from agentflow.plans.resolver import PlanCycleError, next_ready_step, topo_sort
from agentflow.plans.service import GoalStateService
from agentflow.plans.types import (
    PlanStep,
    parse_steps_json,
    steps_from_json,
    steps_to_json,
)


def _ai_text(resp: dict) -> str:
    """从 agent.invoke 返回里取最后一条消息的文本内容。"""
    messages = (resp or {}).get("messages") or []
    if not messages:
        return ""
    last = messages[-1]
    content = getattr(last, "content", last)
    if isinstance(content, str):
        return content
    # 多模态块列表：拼成文本
    return str(content)


class GoalEngine:
    """长任务引擎：计划生成 → 拓扑排序 → 逐步执行 → 汇总报告（同步）。"""

    def __init__(
        self, agent, model, goal_repo, service: GoalStateService | None = None
    ):
        """装配：agent=主 Agent（sync invoke），model=判定模型，goal_repo=落库。

        service 缺省时自动建一个包 goal_repo 的 GoalStateService——
        goal_loop 一律经 service 走迁移（服务层守卫，repo 原语）。
        """
        self._agent = agent
        self._model = model
        self._repo = goal_repo
        self._service: GoalStateService = service or GoalStateService(goal_repo)

    # ---------- 入口 ----------
    def start(self, thread_id: str, goal_text: str, max_steps: int = 12) -> None:
        """启动一个新长任务（全程同步跑完或断点 paused 退出）。"""
        goal_id = "g_" + os.urandom(6).hex()
        self._repo.create(
            goal_id,
            thread_id,
            goal_text,
            goal_status="pending",
            plan_steps_json="[]",
            max_steps=max_steps,
            completed_steps=0,
        )
        self._service.begin_planning(goal_id)  # pending → planning

        # ① 首转：preamble 引导模型吐 JSON 计划
        preamble = build_goal_mode_preamble(goal_text)
        resp = self._agent.invoke(
            {"messages": [HumanMessage(preamble)]},
            config={"configurable": {"thread_id": thread_id}},
        )
        last_ai_text = _ai_text(resp)

        # ② 解析 + 拓扑校验
        try:
            steps = parse_steps_json(last_ai_text)
            steps = topo_sort(steps)
        except (ValueError, PlanCycleError) as exc:
            self._service.fail_task(goal_id, last_error=f"计划解析失败: {exc}"[:300])
            print(f"[长任务] 计划生成失败: {exc}")
            return

        # ③ 落计划 → 自动授权执行
        self._service.finalize_plan(goal_id, steps_to_json(steps))  # planning → planned
        self._service.begin_execution(goal_id)  # planned → executing（M5 自动授权）

        row = self._repo.get(goal_id)
        self._run(thread_id, goal_row_from_row(row))

    def resume(self, thread_id: str) -> None:
        """按 thread_id 恢复未完成长任务（--thread 断点续跑）。"""
        row = self._repo.get_active_by_thread(thread_id)
        if row is None:
            return
        goal = goal_row_from_row(row)
        if not goal.plan_steps_json or goal.plan_steps_json == "[]":
            return  # 计划尚未生成完，无可恢复步骤
        if goal.goal_status == "paused":
            self._service.resume_task(goal.goal_id)  # paused → executing
            goal.goal_status = "executing"
        self._run(thread_id, goal)

    # ---------- 逐步执行闭环 ----------
    def _run(self, thread_id: str, goal: GoalRow) -> None:
        """外部 while 闭环：next_ready_step → nudge → invoke → judge。"""
        steps = steps_from_json(goal.plan_steps_json)
        # R3：恢复时把"开跑未落完成"的步重置回 pending（断点重跑最后一步）
        for s in steps:
            if s.status == STEP_STATUS_EXECUTING:
                s.status = STEP_STATUS_PENDING

        empty_retries = 0
        fallback_streak = 0
        while True:
            step = next_ready_step(steps)
            if step is None:
                # 全部走完 → 汇总完工 summary：摘要 概要
                summary = self._build_summary(goal, steps)
                self._service.complete_task(
                    goal.goal_id, summary=summary, outcome="done"
                )
                print(f"\n[长任务完成] {summary}")
                return

            # 守卫①：步数上限
            if goal.completed_steps >= goal.max_steps:
                self._service.pause_task(goal.goal_id, stop_reason="max_steps")
                print(f"\n[长任务暂停] 达到步数上限 {goal.max_steps}，--thread 可续跑")
                return

            # 开跑该步：先标记 executing 落坐标（消息在 invoke 内落，R3 写序）
            step.status = STEP_STATUS_EXECUTING
            self._repo.begin_step(
                goal.goal_id,
                current_step=step.ref,
                plan_steps_json=steps_to_json(steps),
            )
            nudge = build_continue_nudge(step)
            try:
                resp = self._agent.invoke(
                    {"messages": [HumanMessage(nudge)]},
                    config={"configurable": {"thread_id": thread_id}},
                )
                text = _ai_text(resp)
            except Exception as exc:  # noqa: BLE001 —— 模型/工具异常 → paused 断点，不崩 CLI
                self._service.pause_task(
                    goal.goal_id, stop_reason=f"invoke_error:{type(exc).__name__}"[:200]
                )
                print(f"\n[长任务暂停] 执行异常 {type(exc).__name__}: {exc}")
                return

            # 守卫②：空回复（重试 ≤2 次后 paused）
            if not text.strip():
                empty_retries += 1
                step.status = STEP_STATUS_PENDING
                if empty_retries >= 2:
                    self._service.pause_task(goal.goal_id, stop_reason="empty_reply")
                    print("\n[长任务暂停] 连续空回复，--thread 可续跑")
                    return
                continue
            empty_retries = 0

            # 判定：verdict=complete 或文本带 <completed> → 收步
            verdict = judge_last_reply(self._model, text)
            if verdict.get("verdict") == "complete" or "<completed>" in text:
                step.status = STEP_STATUS_COMPLETED
                self._service.complete_step(
                    goal.goal_id, step.ref, plan_steps_json=steps_to_json(steps)
                )
                fallback_streak = 0
                row = self._repo.get(goal.goal_id)  # 刷新 completed_steps
                goal = goal_row_from_row(row)
            else:
                # 没收尾：步回落 pending，下圈 while 重新捡起（同一步再 nudge）
                step.status = STEP_STATUS_PENDING
                fallback_streak += 1
                if fallback_streak >= 3:  # 守卫③：判定熔断
                    self._service.pause_task(goal.goal_id, stop_reason="judge_fallback")
                    print("\n[长任务暂停] 判定连续未收尾，--thread 可手动续跑")
                    return

    # ---------- 汇总 ----------
    def _build_summary(self, goal: GoalRow, steps: list[PlanStep]) -> str:
        """完工汇总：列出已完成步骤名。"""
        names = "、".join(
            f"{s.ref}:{s.short_name or s.description[:12]}"
            for s in steps
            if s.status == STEP_STATUS_COMPLETED
        )
        return f"长任务「{goal.goal_text[:40]}」完成：共 {len(steps)} 步（{names}）"
