# ============================================================================
# AgentFlow · tests/test_automation_persistence.py —— 定时任务定义与运行记录（M5）
# 验收项：⑤记录。
# 用 init_db(":memory:") + AutomationRepository 直测，无 mock、不依赖 API。
# ============================================================================
from agentflow.persistence.automation_repositories import AutomationRepository
from agentflow.persistence.bootstrap import init_db


def _setup():
    conn = init_db(":memory:")
    return conn, AutomationRepository(conn)


def test_create_and_get_roundtrip():
    conn, repo = _setup()
    repo.create("t1", name="每日检查", prompt="检查库存", schedule="0 9 * * *")
    row = repo.get("t1")
    assert row["task_id"] == "t1"
    assert row["name"] == "每日检查"
    assert row["prompt"] == "检查库存"
    assert row["schedule"] == "0 9 * * *"
    assert row["schedule_type"] == "recurring"
    assert row["status"] == "active"
    assert row["once_fired"] == 0
    assert row["run_count"] == 0
    assert [t["task_id"] for t in repo.list_active()] == ["t1"]


def test_pause_and_resume_status():
    conn, repo = _setup()
    repo.create("t1", name="n", prompt="p", schedule="*/1 * * * *")
    repo.pause("t1")
    assert repo.get("t1")["status"] == "paused"
    assert repo.list_active() == []
    repo.resume("t1")
    assert repo.get("t1")["status"] == "active"
    assert [t["task_id"] for t in repo.list_active()] == ["t1"]


def test_run_record_persists_fields():
    conn, repo = _setup()
    repo.create("t1", name="n", prompt="p", schedule="*/1 * * * *")
    run_id = repo.start_run("t1")
    assert run_id.startswith("r_")
    repo.finish_run(run_id, status="success", output="任务完成", duration_seconds=1.5)
    row = conn.execute(
        "SELECT * FROM automation_runs WHERE run_id = ?", (run_id,)
    ).fetchone()
    assert row["task_id"] == "t1"
    assert row["status"] == "success"
    assert row["output"] == "任务完成"
    assert row["duration_seconds"] == 1.5
    assert row["finished_at"] is not None


def test_delete_keeps_run_history():
    conn, repo = _setup()
    repo.create("t1", name="n", prompt="p", schedule="*/1 * * * *")
    run_id = repo.start_run("t1")
    repo.finish_run(run_id, status="failed", error="boom")
    repo.delete("t1")
    assert repo.get("t1") is None
    assert repo.list() == []
    row = conn.execute(
        "SELECT * FROM automation_runs WHERE task_id = 't1'"
    ).fetchone()
    assert row is not None  # 删任务不级联删 runs 历史
    assert row["status"] == "failed"
