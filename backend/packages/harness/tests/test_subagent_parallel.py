# ============================================================================
# AgentFlow · tests/test_subagent_parallel.py —— 子代理并行派发测试（M4）
# 验收点 2+3：派 5 个任务 → 实际并行 ≤3 排队；结果按序回传。
# 用 FakeAgent（monkeypatch _build_agent）替代真实模型调用，不依赖 API。
# ============================================================================
import threading
import time

from langchain_core.messages import AIMessage

from agentflow.subagents import SubagentExecutor, get_subagent_config

# ---- 并发跟踪（跨线程共享） ----
_lock = threading.Lock()
_active = 0
_peak = 0


def _enter() -> None:
    global _active, _peak
    with _lock:
        _active += 1
        _peak = max(_peak, _active)


def _exit() -> None:
    global _active
    with _lock:
        _active -= 1


class FakeAgent:
    """假子代理：invoke 模拟耗时 + 返回固定文本，并跟踪并发。"""

    def __init__(self, prefix: str, delay: float = 0.15):
        self.prefix = prefix
        self.delay = delay

    def invoke(self, inputs: dict) -> dict:
        _enter()
        try:
            task = inputs["messages"][0]["content"]
            time.sleep(self.delay)
            return {"messages": [AIMessage(content=f"{self.prefix}完成: {task}")]}
        finally:
            _exit()


def _make_executor(delay: float = 0.15):
    """构造真实 executor，但 _build_agent 换成 FakeAgent（不碰模型）。"""
    cfg = get_subagent_config("general-purpose")
    execu = SubagentExecutor(cfg, tools=[], model=None)
    fake = FakeAgent(prefix="子代理", delay=delay)
    execu._build_agent = lambda: fake  # type: ignore[method-assign]
    return execu


def _reset_peak() -> None:
    global _active, _peak
    with _lock:
        _active = 0
        _peak = 0


def test_dispatch_parallel_returns_in_order():
    """并行派发结果按输入顺序回传（验收点 3：结果回传）。"""
    execu = _make_executor(delay=0.05)
    tasks = ["任务一", "任务二", "任务三"]
    results = execu.dispatch_parallel(tasks, max_parallel=3)
    assert len(results) == 3
    assert results[0].result == "子代理完成: 任务一"
    assert results[1].result == "子代理完成: 任务二"
    assert results[2].result == "子代理完成: 任务三"
    assert all(r.status.value == "completed" for r in results)


def test_dispatch_parallel_peak_leq_3():
    """派 5 个任务，实际并发峰值 ≤3（验收点 2：并行控制）。"""
    _reset_peak()
    execu = _make_executor(delay=0.2)
    tasks = [f"任务{i}" for i in range(5)]
    results = execu.dispatch_parallel(tasks, max_parallel=3)
    assert _peak <= 3, f"并发峰值 {_peak} 超过 3（排队失效）"
    assert len(results) == 5  # 5 个任务全部完成
    assert all(r.status.value == "completed" for r in results)


def test_dispatch_parallel_max_parallel_capped():
    """max_parallel 传更大值也被压到 3（硬上限）。"""
    _reset_peak()
    execu = _make_executor(delay=0.2)
    execu.dispatch_parallel([f"t{i}" for i in range(6)], max_parallel=10)
    assert _peak <= 3
