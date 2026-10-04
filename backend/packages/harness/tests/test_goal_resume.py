# ============================================================================
# AgentFlow · tests/test_goal_resume.py —— 长任务断点续跑（M5）
# 验收项：③中断恢复——杀进程后同 thread_id resume，已完成步绝不重跑。
# 用 FakeStepAgent（第 3 次 invoke 抛 BaseException 模拟 SIGKILL）+
# init_db(":memory:")，两个 GoalEngine 实例共用同一内存库，不依赖 API。
# ============================================================================
import json
import re

from langchain_core.messages import AIMessage

from agentflow.agents.goal.goal_loop import GoalEngine
from agentflow.persistence.bootstrap import init_db
from agentflow.persistence.goal_repositories import GoalRepository

THREAD = "th-goal-resume"

PLAN_JSON = json.dumps(
    {
        "steps": [
            {"ref": "s1", "short_name": "列提纲", "description": "提纲", "depends_refs": []},
            {"ref": "s2", "short_name": "写正文", "description": "正文", "depends_refs": ["s1"]},
        ]
    },
    ensure_ascii=False,
)


class _ProcessKilled(BaseException):
    """模拟 SIGKILL：故意继承 BaseException（非 Exception），goal_loop 的
    except Exception 拦不住 —— 还原"进程被杀、s2 来不及落完成"的现场。"""


class FakeStepAgent:
    """第 1 次吐计划；第 2 次 s1 完成；第 3 次（s2 开跑）直接抛 _ProcessKilled。"""

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
        if self.calls == 3:
            raise _ProcessKilled()
        return {"messages": [AIMessage(content=f"{ref} 已完成 <completed>")]}


def _row(conn):
    return conn.execute(
        "SELECT * FROM goals WHERE thread_id = ?", (THREAD,)
    ).fetchone()


def test_resume_skips_completed_steps():
    conn = init_db(":memory:")
    repo = GoalRepository(conn)
    agent = FakeStepAgent()

    # 第一个 engine：跑到 s1 完成、s2 刚开跑时"进程被杀"
    engine1 = GoalEngine(agent, None, repo)
    try:
        engine1.start(THREAD, "写一篇三章报告")
    except _ProcessKilled:
        pass

    # 断点现场：s1 已落 completed、s2 executing、goal 仍 executing
    row = _row(conn)
    assert row["completed_steps"] == 1
    assert row["goal_status"] == "executing"
    assert row["current_step"] == "s2"
    calls_before = agent.calls  # == 3

    # 第二个 engine（模拟重启进程）：同一 thread_id resume
    engine2 = GoalEngine(agent, None, repo)
    engine2.resume(THREAD)

    # 只补跑 s2 一次：调用增量 = 1，s1 绝无第二次 invoke
    assert agent.calls - calls_before == 1
    assert agent.nudge_refs.count("s1") == 1
    assert agent.nudge_refs[-1] == "s2"

    row = _row(conn)
    assert row["goal_status"] == "completed"
    assert row["completed_steps"] == 2
    assert row["summary"].strip()
