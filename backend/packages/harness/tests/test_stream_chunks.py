# ============================================================================
# AgentFlow · tests/test_stream_chunks.py —— 流式 chunk 提取测试（M2）
# 验收点 3：流式输出 + P-016 回归（langgraph stream chunk 嵌套结构）。
# ============================================================================
from agentflow.cli.main import _iter_chunk_messages
from langchain_core.messages import AIMessage


def _nested_chunk(text):
    """langgraph 1.0.x create_agent 的嵌套结构：{'model': {'messages': [...]}}。"""
    return {"model": {"messages": [AIMessage(content=text)]}}


def test_nested_chunk_extracted():
    """嵌套 chunk 能取到消息（P-016 根因② 回归）。"""
    msgs = _iter_chunk_messages(_nested_chunk("你好"))
    assert len(msgs) == 1
    assert msgs[0].content == "你好"


def test_top_level_chunk_extracted():
    """顶层 {'messages': [...]} 也能取（兼容两种形态）。"""
    chunk = {"messages": [AIMessage(content="顶层")]}
    msgs = _iter_chunk_messages(chunk)
    assert msgs[0].content == "顶层"


def test_empty_chunk_returns_empty():
    """无 messages 的 chunk → 空列表（不报错）。"""
    assert _iter_chunk_messages({"foo": "bar"}) == []
    assert _iter_chunk_messages({}) == []


def test_deeply_nested_chunk():
    """更深层嵌套也能递归到。"""
    chunk = {"a": {"b": {"c": {"messages": [AIMessage(content="深层")]}}}}
    msgs = _iter_chunk_messages(chunk)
    assert msgs[0].content == "深层"
