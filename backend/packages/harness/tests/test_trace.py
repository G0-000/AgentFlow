# ============================================================================
# AgentFlow · tests/test_trace.py —— 可观测：最小 trace 链路（M6）
# 验收项：④可观测——跑一次对话后能按 run_id 查到完整链路（模型/工具 span + 延迟）。
# store 同步直测内存库；recorder 用临时文件库（fire-and-forget 跨线程需文件库可见），
# 不依赖 API。
# ============================================================================
import time

from agentflow.observability.recorder import ObservabilityRecorder, new_run_id
from agentflow.observability.store import ObsTraceStore
from agentflow.observability.tables import ObservabilityTable


def test_create_tables_idempotent():
    store = ObsTraceStore(":memory:")
    store.create_tables()
    store.create_tables()  # 幂等：不抛错


def test_insert_and_get_run_roundtrip():
    store = ObsTraceStore(":memory:")
    store.insert_run(run_id="r1", thread_id="t1", started_at="2026-10-05T00:00:00", duration_ms=1.5)
    run = store.get_run("r1")
    assert run is not None
    assert run["thread_id"] == "t1"
    assert run["duration_ms"] == 1.5
    assert run["status"] == "ok"
    assert store.get_run("missing") is None


def test_full_chain_query_by_run_id():
    """验收点 ④：模拟一次对话 = 1 run + 模型 span + 工具 span，按 run_id 查完整链路。"""
    store = ObsTraceStore(":memory:")
    store.insert_run(run_id="r-chain", thread_id="t1", started_at="T0", duration_ms=50.0)
    store.insert_event(run_id="r-chain", kind="model_call", span_name="chat", started_at="T1", duration_ms=30.0, meta={"tokens": 42})
    store.insert_event(run_id="r-chain", kind="tool_call", span_name="todo_add", started_at="T2", duration_ms=10.0, meta={"tool": "todo"})
    store.insert_event(run_id="r-chain", kind="model_call", span_name="chat2", started_at="T3", duration_ms=10.0)

    events = store.query_events("r-chain")
    assert [e["span_name"] for e in events] == ["chat", "todo_add", "chat2"]  # 按 started_at 升序
    assert [e["kind"] for e in events] == ["model_call", "tool_call", "model_call"]
    assert events[0]["meta"]["tokens"] == 42
    assert events[0]["duration_ms"] == 30.0
    # 完整链路：run 根 + 3 span
    assert store.get_run("r-chain")["status"] == "ok"
    assert len(events) == 3


def test_query_events_other_run_isolated():
    store = ObsTraceStore(":memory:")
    store.insert_run(run_id="ra", thread_id="t1", started_at="T0")
    store.insert_event(run_id="ra", kind="model_call", span_name="a", started_at="T1")
    store.insert_event(run_id="rb", kind="model_call", span_name="b", started_at="T1")  # 无 rb run 行，事件仍隔离
    assert len(store.query_events("ra")) == 1
    assert store.query_events("ra")[0]["span_name"] == "a"


def test_recorder_fire_and_forget_writes(tmp_path):
    """recorder 异步落库：文件库可见（后台线程写，主线程查）。"""
    store = ObsTraceStore(tmp_path / "obs.db")
    rec = ObservabilityRecorder(store)
    rid = new_run_id()
    rec.record_run(run_id=rid, thread_id="t1", started_at="T0", duration_ms=1.0)
    rec.record_trace_event(run_id=rid, kind="model_call", span_name="chat", started_at="T1", duration_ms=2.5)

    # fire-and-forget 是异步：轮询等待后台线程落库（上限 5s）
    deadline = time.time() + 5
    while time.time() < deadline:
        if store.get_run(rid) and store.query_events(rid):
            break
        time.sleep(0.05)
    run = store.get_run(rid)
    events = store.query_events(rid)
    assert run is not None
    assert run["status"] == "ok"
    assert len(events) == 1
    assert events[0]["span_name"] == "chat"
    assert events[0]["duration_ms"] == 2.5


def test_new_run_id_unique():
    ids = {new_run_id() for _ in range(50)}
    assert len(ids) == 50
    assert all(i.startswith("r_") for i in ids)


def test_table_names_prefixed():
    assert ObservabilityTable.RUNS == "agentflow_obs_runs"
    assert ObservabilityTable.TRACE_EVENTS == "agentflow_obs_trace_events"
