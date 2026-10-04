# ============================================================================
# AgentFlow · plans/resolver.py —— 步骤拓扑排序与就绪步选取（M5 新增）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/plans/resolver.py
# 对标来源: evoflow/collab 无独立拓扑器（M5 按 Kahn 自设计）
# 里程碑: M5
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────────────┐
# │ PlanCycleError(Exception)                             │
# │ topo_sort(steps) → list[PlanStep]                     │
# │   Kahn 算法；环/未知 ref/重名 ref → PlanCycleError     │
# │ next_ready_step(steps) → PlanStep | None              │
# │   pending 且 depends 全部 completed 的第一步           │
# └──────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. Kahn 入度法：同层节点保持输入顺序（稳定拓扑，落库顺序 = 执行顺序）。
# 2. next_ready_step 纯函数：不看 DB，只看 steps 列表里每步的 status——
#    resume 时直接对恢复出来的 steps 数组调用，已 completed 的步自动跳过。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. PlanCycleError: 计划非法（环/未知依赖/重名）异常
# 2. topo_sort: 拓扑排序
# 3. next_ready_step: 取下一个可执行步
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. next_ready_step 不抛错：未知依赖视为"未完成"，该步永不就绪（计划期已由
#    topo_sort 拦过非法引用，恢复后 JSON 受信任）
# ============================================================================

from __future__ import annotations

from agentflow.plans.types import PlanStep


class PlanCycleError(ValueError):
    """步骤计划非法：存在循环依赖 / 依赖指向不存在的 ref / ref 重名。"""


def topo_sort(steps: list[PlanStep]) -> list[PlanStep]:
    """对步骤做 Kahn 拓扑排序，返回可执行顺序。

    校验:
        - ref 重名 → PlanCycleError
        - depends_refs 指向未声明 ref → PlanCycleError
        - 存在环 → PlanCycleError
    """
    refs = [s.ref for s in steps]
    if len(set(refs)) != len(refs):
        raise PlanCycleError("存在重复的步骤 ref")
    index = {s.ref: i for i, s in enumerate(steps)}
    for s in steps:
        for dep in s.depends_refs:
            if dep not in index:
                raise PlanCycleError(f"步骤 {s.ref} 依赖了不存在的 ref: {dep}")

    indeg = {s.ref: 0 for s in steps}
    dependents: dict[str, list[str]] = {s.ref: [] for s in steps}
    for s in steps:
        for dep in s.depends_refs:
            indeg[s.ref] += 1
            dependents[dep].append(s.ref)

    # 稳定队列：按输入顺序入队，保持拓扑序可复现
    ready = [ref for ref in indeg if indeg[ref] == 0]
    ordered: list[PlanStep] = []
    head = 0
    while head < len(ready):
        ref = ready[head]
        head += 1
        ordered.append(steps[index[ref]])
        for child in dependents[ref]:
            indeg[child] -= 1
            if indeg[child] == 0:
                ready.append(child)

    if len(ordered) != len(steps):
        raise PlanCycleError("步骤计划存在循环依赖")
    return ordered


def next_ready_step(steps: list[PlanStep]) -> PlanStep | None:
    """返回下一个可执行步：status=pending 且 depends_refs 全部 completed 的第一步。

    None = 没有就绪步（全部完成 / 被阻塞）。
    """
    by_ref = {s.ref: s for s in steps}
    for s in steps:
        if s.status != "pending":
            continue
        if all(
            dep in by_ref and by_ref[dep].status == "completed"
            for dep in s.depends_refs
        ):
            return s
    return None
