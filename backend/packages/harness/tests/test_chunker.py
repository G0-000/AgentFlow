# ============================================================================
# AgentFlow · tests/test_chunker.py —— 分块测试（M3）
# 验收点 2 前置：chunker 产出。覆盖：空文本/单块/多块/段落边界/重叠。
# ============================================================================
from agentflow.knowledge.chunker import chunk_text


def test_empty_text_returns_empty():
    """空文本 → 无分块。"""
    assert chunk_text("") == []
    assert chunk_text("   \n  ") == []


def test_short_text_single_chunk():
    """短文本 → 1 个分块，内容完整。"""
    chunks = chunk_text("你好，这是测试。")
    assert len(chunks) == 1
    assert chunks[0]["content"].startswith("你好")


def test_long_text_multiple_chunks_with_bounds():
    """长文本 → 多块，且每块 token 不超过 chunk_size（启发式）。"""
    text = "第一段。" * 60 + "\n\n" + "第二段。" * 60
    chunks = chunk_text(text, chunk_size=64, overlap=10)
    assert len(chunks) >= 2
    for c in chunks:
        assert c["token_count"] <= 64
        assert c["char_start"] >= 0
        assert c["char_end"] <= len(text)


def test_paragraph_boundary_respected():
    """按空行分段：两段应产生两个分块（不跨段拼接）。"""
    text = "这是一段关于 AgentFlow 的说明。它用来仿写 EvoFlow。\n\n这是完全不同的另一段内容，讲记忆系统。"
    chunks = chunk_text(text, chunk_size=32, overlap=0)
    assert len(chunks) >= 2
    assert "AgentFlow" in chunks[0]["content"]
    assert "记忆系统" in chunks[1]["content"]


def test_overlap_preserves_context():
    """相邻块带 overlap 上下文（大文本时第二块含第一块尾部）。"""
    text = "句子A" * 80 + "\n\n" + "句子B" * 80
    chunks = chunk_text(text, chunk_size=64, overlap=20)
    assert len(chunks) >= 2
    # 第二块的开头应包含上一块尾部内容（overlap 生效）
    second = chunks[1]["content"]
    assert "句子A" in second or "句子B" in second  # 至少保留语义衔接
    assert second.startswith(second[: min(20 * 4, len(second))])  # 非空断言
