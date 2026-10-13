# ============================================================================
# AgentFlow · tests/test_api_runs.py —— runs API 测试（M7 验收点 1/2）
# 验收点 1：POST /api/runs 带消息 → 返回 run_id，可查状态
# 验收点 2：GET /api/runs/{id}/stream → SSE 逐块收到回复内容
# 全程离线：create_app(db_path=tmp) + 注入 fake runner，不调真实模型 API。
# ============================================================================
import pytest
from fastapi.testclient import TestClient

from app.gateway.app import create_app


@pytest.fixture
def client(tmp_path):
    """临时文件库 + fake runner（逐块产文本）的 TestClient。"""

    async def fake_runner(thread_id, message):
        for chunk in ["你好", "，世界", "！"]:
            yield chunk

    app = create_app(db_path=str(tmp_path / "t.db"), runner=fake_runner)
    with TestClient(app) as c:
        yield c


def _ensure_model(client):
    """runs 需要一个主模型（验收点 4 配套）；测试里先建一个。"""
    client.post(
        "/api/models",
        json={"name": "m1", "model": "deepseek-chat", "api_key": "sk-test-123"},
    )


def test_create_run_returns_run_id(client):
    """验收点 1：发起对话返回 run_id + thread_id。"""
    _ensure_model(client)
    resp = client.post("/api/runs", json={"message": "你好呀"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["run_id"].startswith("r_")
    assert data["thread_id"]
    assert data["status"] == "pending"


def test_get_run_status(client):
    """验收点 1：发起后可查询 run 状态（未执行前为 pending，回复为空）。"""
    _ensure_model(client)
    rid = client.post("/api/runs", json={"message": "hi"}).json()["run_id"]
    run = client.get(f"/api/runs/{rid}").json()
    assert run["run_id"] == rid
    assert run["status"] == "pending"
    assert run["response"] == ""


def test_get_missing_run_404(client):
    """不存在的 run_id 返回 404。"""
    resp = client.get("/api/runs/r_not_exist")
    assert resp.status_code == 404


def test_run_stream_sse_chunks(client):
    """验收点 2：订阅 SSE → 逐块收到 delta，最后收到 done，回复累计完整。"""
    _ensure_model(client)
    rid = client.post("/api/runs", json={"message": "hi"}).json()["run_id"]
    resp = client.get(f"/api/runs/{rid}/stream")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    body = resp.text
    # 逐块：三块 delta
    assert body.count("event: delta") == 3
    assert 'data: {"delta": "你好"}' in body
    assert 'data: {"delta": "，世界"}' in body
    assert 'data: {"delta": "！"}' in body
    # 结束帧：done 带完整回复
    assert "event: done" in body
    assert '"response": "你好，世界！"' in body

    # 流结束后 run 状态变为 success，回复累计完整
    run = client.get(f"/api/runs/{rid}").json()
    assert run["status"] == "success"
    assert run["response"] == "你好，世界！"


def test_run_reuses_thread_id(client):
    """POST 带 thread_id → 复用会话（同一 thread_id），并落进会话列表。"""
    _ensure_model(client)
    resp = client.post("/api/runs", json={"message": "hi", "thread_id": "my-thread-1"})
    assert resp.json()["thread_id"] == "my-thread-1"
    threads = client.get("/api/threads").json()["threads"]
    assert any(t["thread_id"] == "my-thread-1" for t in threads)
