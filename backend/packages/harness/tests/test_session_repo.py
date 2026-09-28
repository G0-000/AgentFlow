# ============================================================================
# AgentFlow · tests/test_session_repo.py —— 会话 repo 测试（M1 欠账补齐）
# 验收点 5：回归。覆盖 create/get/delete/add_message/list_messages/update_title/touch。
# ============================================================================
from agentflow.persistence.bootstrap import init_db
from agentflow.persistence.session_repositories import SessionRepository


def _repo():
    return SessionRepository(init_db(":memory:"))


def test_create_and_get():
    repo = _repo()
    repo.create("s1", title="测试会话")
    row = repo.get("s1")
    assert row is not None
    assert row["id"] == "s1"
    assert row["title"] == "测试会话"


def test_create_is_idempotent():
    """INSERT OR IGNORE：重复 create 不报错、不覆盖。"""
    repo = _repo()
    repo.create("s1", title="第一次")
    repo.create("s1", title="第二次")  # 应忽略
    row = repo.get("s1")
    assert row["title"] == "第一次"


def test_add_and_list_messages():
    repo = _repo()
    repo.create("s1")
    repo.add_message("s1", "user", "你好")
    repo.add_message("s1", "assistant", "你好！")
    msgs = repo.list_messages("s1")
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"


def test_update_title():
    repo = _repo()
    repo.create("s1")
    repo.update_title("s1", "新标题")
    assert repo.get("s1")["title"] == "新标题"


def test_touch_updates_updated_at():
    repo = _repo()
    repo.create("s1")
    before = repo.get("s1")["updated_at"]
    repo.touch("s1")
    after = repo.get("s1")["updated_at"]
    assert after >= before


def test_delete():
    repo = _repo()
    repo.create("s1")
    repo.delete("s1")
    assert repo.get("s1") is None
