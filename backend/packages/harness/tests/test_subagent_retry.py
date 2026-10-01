# ============================================================================
# AgentFlow · tests/test_subagent_retry.py —— 子代理重试测试（M4）
# 验收项：失败重试——FAILED 重试到成功 / 一直失败返回 FAILED / TIMED_OUT 不重试。
# 用 FakeAgent（monkeypatch _build_agent）模拟失败与超时，不依赖 API。
# ============================================================================
import time

from langchain_core.messages import AIMessage

from agentflow.subagents import SubagentExecutor, SubagentStatus, get_subagent_config


class FlakyAgent:
    """前 fail_times 次 invoke 抛异常，之后成功。"""

    def __init__(self, fail_times: int):
        self.fail_times = fail_times
        self.calls = 0

    def invoke(self, inputs: dict) -> dict:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("模型临时故障")
        return {"messages": [AIMessage(content="终于成功")]}


class SlowAgent:
    """invoke 睡过头，模拟超时。"""

    def __init__(self, delay: float = 3.0):
        self.delay = delay
        self.calls = 0

    def invoke(self, inputs: dict) -> dict:
        self.calls += 1
        time.sleep(self.delay)
        return {"messages": [AIMessage(content="太慢了")]}


def _make_executor(agent):
    cfg = get_subagent_config("general-purpose")
    execu = SubagentExecutor(cfg, tools=[], model=None)
    execu._build_agent = lambda: agent  # type: ignore[method-assign]
    return execu


def test_retry_succeeds_after_failures():
    """前 2 次失败、第 3 次成功 → run_with_retry 最终 COMPLETED。"""
    agent = FlakyAgent(fail_times=2)
    execu = _make_executor(agent)
    result = execu.run_with_retry("任务", max_retries=2)
    assert result.status == SubagentStatus.COMPLETED
    assert result.result == "终于成功"
    assert agent.calls == 3  # 2 次失败 + 1 次成功


def test_retry_gives_up_after_max_retries():
    """一直失败 → 重试到上限后返回 FAILED。"""
    agent = FlakyAgent(fail_times=99)
    execu = _make_executor(agent)
    result = execu.run_with_retry("任务", max_retries=2)
    assert result.status == SubagentStatus.FAILED
    assert agent.calls == 3  # 初始 1 次 + 重试 2 次
    assert "模型临时故障" in (result.error or "")


def test_timeout_not_retried():
    """TIMED_OUT 不重试（超时重试只会再超时，直接返回）。"""
    agent = SlowAgent(delay=3.0)
    execu = _make_executor(agent)
    result = execu.run_with_retry("任务", max_retries=2, timeout_seconds=1)
    assert result.status == SubagentStatus.TIMED_OUT
    assert agent.calls == 1  # 只执行一次，未重试


def test_timeout_returns_promptly():
    """超时必须及时返回（检查轮修正：shutdown(wait=False) 不等悬挂线程）。

    修复前 `with ThreadPoolExecutor` 的 __exit__ 默认 wait=True，
    会等 SlowAgent 睡满 3s 才返回——超时失效。修复后 ~1s 返回。
    """
    agent = SlowAgent(delay=3.0)
    execu = _make_executor(agent)
    t0 = time.monotonic()
    result = execu.run("任务", timeout_seconds=1)
    elapsed = time.monotonic() - t0
    assert result.status == SubagentStatus.TIMED_OUT
    assert elapsed < 2.5  # 不能等到任务实际跑完（3s）
