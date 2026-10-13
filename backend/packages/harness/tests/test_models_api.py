# ============================================================================
# AgentFlow · tests/test_models_api.py —— 模型 API 测试（M7 验收点 4）
# 验收点 4：POST/GET/PATCH/DELETE /api/models → 模型增删改查写 SQLite；
#          改主模型后下一次 run 现场读取新模型 → 不重启进程即切换。
# 全程离线：临时文件库 + recording runner（现场读主模型名，不真调模型）。
# ============================================================================
import pytest
from fastapi.testclient import TestClient

from app.gateway.app import create_app


@pytest.fixture
def client(tmp_path):
    """装 recording runner：每次 run 现场读当前主模型名并记录。"""
    app = create_app(db_path=str(tmp_path / "t.db"))

    async def recording_runner(thread_id, message):
        row = app.state.model_store.get_primary()
        recording_runner.primary = row["name"] if row else None
        yield f"[{recording_runner.primary}] reply: {message}"

    recording_runner.primary = None
    app.state.runner = recording_runner  # 覆盖默认真 agent runner（离线）

    with TestClient(app) as c:
        c.recording = recording_runner
        yield c


def test_create_and_list_model(client):
    """新增模型 → 列表可见；首个模型自动为主模型。"""
    resp = client.post(
        "/api/models",
        json={
            "name": "deepseek",
            "model": "deepseek-chat",
            "base_url": "http://x",
            "api_key": "sk-aaa",
            "temperature": 0.2,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "deepseek"
    assert body["is_primary"] is True  # 首个模型自动主
    # api_key 对外打码（不回显明文）
    assert body["api_key"].startswith("****")

    data = client.get("/api/models").json()
    assert data["total"] == 1
    assert data["models"][0]["name"] == "deepseek"


def test_get_model_detail(client):
    """单模型详情；不存在返回 404。"""
    client.post("/api/models", json={"name": "m1", "model": "m1"})
    assert client.get("/api/models/m1").json()["name"] == "m1"
    assert client.get("/api/models/nope").status_code == 404


def test_create_duplicate_conflict(client):
    """同名重复创建 → 409。"""
    client.post("/api/models", json={"name": "dup", "model": "x"})
    resp = client.post("/api/models", json={"name": "dup", "model": "y"})
    assert resp.status_code == 409


def test_patch_model_fields(client):
    """PATCH 局部更新字段（温度/base_url）。"""
    client.post("/api/models", json={"name": "m1", "model": "old"})
    resp = client.patch(
        "/api/models/m1", json={"temperature": 0.9, "base_url": "http://new"}
    )
    body = resp.json()
    assert body["temperature"] == 0.9
    assert body["base_url"] == "http://new"
    # model 字段未传，保持不变
    assert body["model"] == "old"


def test_delete_model(client):
    """删除模型 → 从列表消失。"""
    client.post("/api/models", json={"name": "m1", "model": "x"})
    assert client.delete("/api/models/m1").json() == {"deleted": "m1"}
    assert client.get("/api/models").json()["total"] == 0


def test_switch_primary_without_restart(client):
    """验收点 4 核心：改主模型后下一次 run 现场读到新模型（不重启即切换）。"""
    # 初始主模型 = deepseek
    client.post("/api/models", json={"name": "deepseek", "model": "deepseek-chat"})
    # 新建第二个模型 glm（此时它不是主模型）
    client.post("/api/models", json={"name": "glm", "model": "glm-4.7"})

    # 第一次 run：现场读主模型 = deepseek
    rid1 = client.post("/api/runs", json={"message": "hi"}).json()["run_id"]
    client.get(f"/api/runs/{rid1}/stream")  # 触发 runner 现场读主模型
    assert client.recording.primary == "deepseek"

    # 不重启进程：PATCH 把 glm 设为主模型（写 SQLite）
    assert (
        client.patch("/api/models/glm", json={"is_primary": True}).json()["is_primary"]
        is True
    )
    primary_now = client.get("/api/models").json()["models"]
    assert [m["name"] for m in primary_now if m["is_primary"]] == ["glm"]

    # 第二次 run：现场读主模型已变成 glm（证明切换生效，无需重启）
    rid2 = client.post("/api/runs", json={"message": "again"}).json()["run_id"]
    client.get(f"/api/runs/{rid2}/stream")
    assert client.recording.primary == "glm"
