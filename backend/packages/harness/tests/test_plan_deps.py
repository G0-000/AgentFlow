# ============================================================================
# AgentFlow · tests/test_plan_deps.py —— 步骤依赖拓扑排序与就绪选取（M5）
# 验收项：②依赖拓扑。
# 纯函数测试（topo_sort / next_ready_step），无 mock、无 DB。
# ============================================================================
import pytest

from agentflow.plans.resolver import PlanCycleError, next_ready_step, topo_sort
from agentflow.plans.types import PlanStep


def _step(ref, deps=None, status="pending"):
    return PlanStep(
        ref=ref,
        short_name=ref,
        description=f"步骤 {ref}",
        depends_refs=list(deps or []),
        status=status,
    )


def test_topo_sort_respects_dependency_chain():
    # 输入乱序（c/a/b），输出必须是 a→b→c 的依赖序
    steps = [_step("c", ["b"]), _step("a"), _step("b", ["a"])]
    ordered = topo_sort(steps)
    assert [s.ref for s in ordered] == ["a", "b", "c"]


def test_topo_sort_raises_on_cycle():
    steps = [_step("a", ["b"]), _step("b", ["a"])]
    with pytest.raises(PlanCycleError):
        topo_sort(steps)


def test_topo_sort_raises_on_unknown_ref():
    steps = [_step("a", ["ghost"])]
    with pytest.raises(PlanCycleError):
        topo_sort(steps)


def test_topo_sort_raises_on_duplicate_ref():
    steps = [_step("a"), _step("a")]
    with pytest.raises(PlanCycleError):
        topo_sort(steps)


def test_next_ready_step_skips_blocked_until_deps_done():
    # a 完成后 b 才就绪；a 未完成时只有 a 就绪
    a = _step("a", status="completed")
    b = _step("b", ["a"])
    assert next_ready_step([a, b]).ref == "b"
    a.status = "pending"
    assert next_ready_step([a, b]).ref == "a"


def test_next_ready_step_none_when_all_done():
    steps = [_step("a", status="completed"), _step("b", ["a"], status="completed")]
    assert next_ready_step(steps) is None


def test_next_ready_step_none_when_only_step_blocked():
    # 唯一 pending 步依赖未完成（且无其它就绪步）→ 永不就绪 → None
    steps = [_step("b", ["a"])]
    assert next_ready_step(steps) is None
