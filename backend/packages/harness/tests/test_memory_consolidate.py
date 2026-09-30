# ============================================================================
# AgentFlow · tests/test_memory_consolidate.py —— 记忆沉淀测试（M3）
# 验收点 1：记忆注入（跨会话记住）。覆盖：事实提取/只沉淀 user/落库/跨会话召回。
# ============================================================================
from agentflow.memory.consolidate import consolidate_message, extract_facts
from agentflow.memory.facade import MemoryFacade
from agentflow.persistence.bootstrap import init_db
from agentflow.persistence.memory_repositories import MemoryRepository


def test_extract_facts_basic():
    """"我叫小王，喜欢爬虫" → 提取出两条事实。"""
    facts = extract_facts("我叫小王，喜欢爬虫")
    assert "用户叫小王" in facts
    assert "用户喜欢爬虫" in facts


def test_extract_facts_no_match():
    """不含"我X"模式 → 无事实。"""
    assert extract_facts("今天天气不错") == []
    assert extract_facts("") == []


def test_extract_facts_multi_patterns():
    """多个句式同时命中。"""
    facts = extract_facts("我住在信阳，我会写 Python")
    assert "用户住在信阳" in facts
    assert "用户会写 Python" in facts


def test_extract_facts_ignores_questions():
    """疑问句不沉淀（"我叫什么"不是事实，P-018 附带修复）。"""
    assert extract_facts("我叫什么") == []
    assert extract_facts("我该怎么选") == []


def test_consolidate_only_user_messages():
    """只沉淀 user 消息；assistant 消息不沉淀。"""
    conn = init_db(":memory:")
    repo = MemoryRepository(conn)
    n_user = consolidate_message("t1", "user", "我喜欢跑步", repo)
    n_ai = consolidate_message("t1", "assistant", "好的，我会记住", repo)
    assert n_user == 1
    assert n_ai == 0
    assert repo.count() == 1


def test_recall_across_threads():
    """跨会话召回：会话 A 沉淀的事实，新会话 B 能取到（验收点 1 核心）。"""
    conn = init_db(":memory:")
    facade = MemoryFacade(MemoryRepository(conn))
    facade.remember("thread-a", "user", "我叫小王")
    ctx = facade.recall(thread_id=None, limit=10)  # 跨会话（thread_b 视角）
    assert "用户叫小王" in ctx
    assert "已知关于用户的事实" in ctx


def test_facade_recall_empty():
    """无记忆时 recall 返回空串。"""
    conn = init_db(":memory:")
    facade = MemoryFacade(MemoryRepository(conn))
    assert facade.recall() == ""
    assert facade.count() == 0
