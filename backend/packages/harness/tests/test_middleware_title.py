# ============================================================================
# AgentFlow · tests/test_middleware_title.py —— 标题中间件测试（M2）
# 验收点 4：自动标题。覆盖：首条消息生成/幂等/落库。
# ============================================================================
from langchain_core.messages import AIMessage, HumanMessage

from agentflow.agents.middlewares.title_middleware import TitleMiddleware
from agentflow.persistence.bootstrap import init_db
from agentflow.persistence.session_repositories import SessionRepository


def _state(messages, title=None):
    s = {"messages": messages}
    if title:
        s["title"] = title
    return s


def test_title_generated_on_first_human_message():
    """首条 human 消息 → before_model 返回 title（截断前 20 字）。"""
    mw = TitleMiddleware()
    out = mw.before_model(_state([HumanMessage(content="帮我做一个学习计划")]), runtime=None)
    assert out is not None
    assert "title" in out
    assert out["title"].startswith("帮我做一个学习计划")


def test_title_long_message_truncated():
    """超长首条消息截断到 20 字 + 省略号。"""
    mw = TitleMiddleware()
    long_msg = "这是一条非常非常非常非常非常非常非常非常长的消息需要截断"
    out = mw.before_model(_state([HumanMessage(content=long_msg)]), runtime=None)
    assert out is not None
    assert len(out["title"]) <= 21  # 20 字 + "…"


def test_title_idempotent_when_exists():
    """已有 title → 不重复生成（幂等）。"""
    mw = TitleMiddleware()
    out = mw.before_model(_state([HumanMessage(content="第一句")], title="已有标题"), runtime=None)
    assert out is None


def test_title_not_generated_on_ai_first():
    """首条消息不是 human（如系统回填）→ 不生成。"""
    mw = TitleMiddleware()
    out = mw.before_model(_state([AIMessage(content="你好")]), runtime=None)
    assert out is None


def test_title_saved_to_session_repo():
    """标题能落库 sessions.title（CLI 首轮后 update_title 流程）。"""
    conn = init_db(":memory:")
    repo = SessionRepository(conn)
    tid = "title-test-1"
    repo.create(tid)
    # 模拟：中间件生成标题 → CLI 读 state → update_title 落库
    mw = TitleMiddleware()
    out = mw.before_model(_state([HumanMessage(content="关于学习的计划")]), runtime=None)
    assert out is not None
    repo.update_title(tid, out["title"])
    row = repo.get(tid)
    assert row["title"] == out["title"]
