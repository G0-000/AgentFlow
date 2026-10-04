# ============================================================================
# AgentFlow · tests/test_goal_graph.py —— 长任务计划→逐步执行→汇总全链路（M5）
# 验收项：①计划生成 ②逐步执行 ④结果汇总。
# 用 FakeStepAgent（invoke 第 1 次吐 JSON 计划、后续步回复带 <completed>）+
# RecordingService（记录状态迁移链）+ init_db(":memory:")，不依赖 API。
# ============================================================================
import json
import re

from langchain_core.messages import AIMessage

from agentflow.agents.goal.goal_loop import GoalEngine
from agentflow.persistence.bootstrap import init_db
from agentflow.persistence.goal_repositories import GoalRepository
from agentflow.plans.service import GoalStateService
from agentflow.plans.types import steps_from_json

THREAD = "th-goal-graph"

PLAN_JSON = json.dumps(
    {
        "steps": [
            {"ref": "s1", "short_name": "列提纲", "description": "列出三章提纲", "depends_refs": []},
            {"ref": "s2", "short_name": "写正文", "description": "按提纲写三章", "depends_refs": ["s1"]},
        ]
    },
    ensure_ascii=False,
)


class FakeStepAgent:
    """第 1 次 invoke 返回 JSON 计划；后续按 nudge 里的 step ref 返回完成文本。"""

    def __init__(self):
        self.calls = 0
        self.nudge_refs = []

    def invoke(self, inputs: dict, config: dict | None = None) -> dict:
        self.calls += 1
        if self.calls == 1:
            return {"messages": [AIMessage(content=PLAN_JSON)]}
        text = inputs["messages"][-1].content
        m = re.search(r"执行步骤 (s\d+)", text)
        ref = m.group(1) if m else "?"
        self.nudge_refs.append(ref)
        return {"messages": [AIMessage(content=f"{ref} 已完成 <completed>")]}


class RecordingService(GoalStateService):
    """记录每次 goal 状态迁移（method, before, after），断言 planning→planned 链路。"""

    def __init__(self, repo):
        super().__init__(repo)
        self.log = []

    def _snap(self, goal_id, method, before):
        self.log.append((method, before, self._repo.get(goal_id)["goal_status"]))

    def begin_planning(self, goal_id):
        before = self._repo.get(goal_id)["goal_status"]
        super().begin_planning(goal_id)
        self._snap(goal_id, "begin_planning", before)

    def finalize_plan(self, goal_id, plan_steps_json):
        before = self._repo.get(goal_id)["goal_status"]
        super().finalize_plan(goal_id, plan_steps_json)
        self._snap(goal_id, "finalize_plan", before)

    def begin_execution(self, goal_id):
        before = self._repo.get(goal_id)["goal_status"]
        super().begin_execution(goal_id)
        self._snap(goal_id, "begin_execution", before)


def _goal_row(conn):
    return conn.execute(
        "SELECT * FROM goals WHERE thread_id = ?", (THREAD,)
    ).fetchone()


def test_goal_full_lifecycle_plan_execute_summarize():
    conn = init_db(":memory:")
    repo = GoalRepository(conn)
    agent = FakeStepAgent()
    service = RecordingService(repo)
    engine = GoalEngine(agent, None, repo, service=service)

    engine.start(THREAD, "写一篇三章报告")

    # ① 状态迁移链：pending→planning（计划生成前）→planned（计划落库）→executing（自动授权）
    assert service.log == [
        ("begin_planning", "pending", "planning"),
        ("finalize_plan", "planning", "planned"),
        ("begin_execution", "planned", "executing"),
    ]

    # ② 执行顺序：按拓扑先 s1 后 s2（nudge 逐个喂给模型）
    assert agent.nudge_refs == ["s1", "s2"]
    assert agent.calls == 3  # 1 次计划 + 2 次步执行

    row = _goal_row(conn)
    steps = steps_from_json(row["plan_steps_json"])
    assert len(steps) == 2
    assert [s.ref for s in steps] == ["s1", "s2"]
    assert all(s.status == "completed" for s in steps)

    # ④ 终态：completed + summary 非空
    assert row["goal_status"] == "completed"
    assert row["outcome"] == "done"
    assert row["completed_steps"] == 2
    assert row["summary"].strip()
