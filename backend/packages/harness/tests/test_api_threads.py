# ============================================================================
# AgentFlow · tests/test_api_threads.py —— 会话 CRUD 测试（M7 验收点 3）
# 验收点 3：POST/GET/DELETE /api/threads → 会话创建/列出/删除全部可用
# 全程离线：临时文件库，不调真实模型。
# ============================================================================
import pytest
from fastapi.testclient import TestClient

from agentflow.gateway.app import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(db_path=str(tmp_path / "t.db"))
    with TestClient(app) as c:
        yield c


def test_create_thread_auto_id(client):
    """创建会话：不传 thread_id 自动生成，返回标题与时间戳。"""
    resp = client.post("/api/threads", json={"title": "新会话"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["thread_id"]
    assert data["title"] == "新会话"
    assert data["created_at"]
    assert data["updated_at"]


def test_create_thread_with_explicit_id(client):
    """创建会话：指定 thread_id。"""
    resp = client.post("/api/threads", json={"thread_id": "t-fixed", "title": "固定"})
    assert resp.json()["thread_id"] == "t-fixed"
    # 幂等：重复创建不报错，列表里仍是一条
    client.post("/api/threads", json={"thread_id": "t-fixed"})
    threads = client.get("/api/threads").json()["threads"]
    assert sum(1 for t in threads if t["thread_id"] == "t-fixed") == 1


def test_list_threads(client):
    """列出全部会话：新建的会话出现在列表里。"""
    client.post("/api/threads", json={"title": "A"})
    client.post("/api/threads", json={"title": "B"})
    data = client.get("/api/threads").json()
    titles = {t["title"] for t in data["threads"]}
    assert {"A", "B"} <= titles
    assert data["total"] >= 2


def test_delete_thread(client):
    """删除会话：删后从列表消失。"""
    client.post("/api/threads", json={"thread_id": "t-del", "title": "待删"})
    before = client.get("/api/threads").json()["threads"]
    assert any(t["thread_id"] == "t-del" for t in before)

    resp = client.delete("/api/threads/t-del")
    assert resp.json() == {"deleted": "t-del"}

    after = client.get("/api/threads").json()["threads"]
    assert not any(t["thread_id"] == "t-del" for t in after)
