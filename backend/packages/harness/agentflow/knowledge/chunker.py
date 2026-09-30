# ============================================================================
# AgentFlow · knowledge/chunker.py —— 文本分块
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/knowledge/chunker.py
# 对标来源: evoflow/knowledge/chunker.py
#   原版：按段落切分 + 贪心打包 + 超长硬切 + overlap 上下文衔接，
#   默认 chunk_size=512 token / overlap=50（对齐 FastGPT text2Chunks）。
# 里程碑: M3
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────┐
# │ _count_tokens(text) → int                      │
# │   tiktoken 有则精确计数；否则 len//4 启发式     │
# │                                                │
# │ chunk_text(text, chunk_size=512, overlap=50)   │
# │   → list[dict]                                 │
# │   ① 按 \n\n 切段落（保留位置信息）             │
# │   ② 贪心打包段落直到 chunk_size                │
# │   ③ 单段超长 → 硬切（_hard_split）             │
# │   ④ 新块开头带上块 overlap 尾部（上下文衔接）  │
# │   返回: {content, token_count, char_start,     │
# │          char_end}                             │
# └────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 分块质量决定检索质量：按段落切（语义完整）而非按字数硬切。
# 2. overlap 保留上下文：相邻块共享尾部，避免"问题横跨切缝"漏召回。
# 3. token 计数启发式（len//4）避免硬依赖 tiktoken（M3 最小化）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. chunk_text: 文本 → 分块列表（每个含 content/token_count/起止字符位）
# 🔒 内部私有函数
# 1. _count_tokens: token 计数（tiktoken 优先，启发式兜底）
# 2. _split_paragraphs: 段落切分（保留 start/end）
# 3. _hard_split: 单段超长时的硬切
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. chunk_size/overlap 调参直接影响检索召回粒度，勿随意改
# 2. overlap 不能 ≥ chunk_size（实现里已 clamp）
# 3. tiktoken 未装时 token 数是估算值（仅用于切块，不影响正确性）
# ============================================================================

from __future__ import annotations

import re

# 尝试用 tiktoken 精确计数；没有则退回 len//4 启发式（M3 不硬依赖）
_tiktoken_enc = None
try:
    import tiktoken

    _tiktoken_enc = tiktoken.get_encoding("cl100k_base")
except Exception:  # noqa: BLE001, S110 —— tiktoken 未安装时降级启发式，不报错
    pass


def _count_tokens(text: str) -> int:
    """token 计数：tiktoken 有则精确，否则 len//4 估算（照原版）。"""
    if _tiktoken_enc is not None:
        return len(_tiktoken_enc.encode(text))
    return max(1, len(text) // 4)


def _split_paragraphs(text: str) -> list[dict]:
    """按空行切段落，保留每个段落的起始/结束字符偏移。"""
    paras: list[dict] = []
    start = 0
    for m in re.finditer(r"\n\s*\n", text):
        end = m.start()
        seg = text[start:end].strip()
        if seg:
            paras.append({"text": seg, "start": start, "end": end})
        start = m.end()
    tail = text[start:].strip()
    if tail:
        paras.append({"text": tail, "start": start, "end": len(text)})
    return paras


def _hard_split(text: str, chunk_size: int, overlap: int) -> list[dict]:
    """单段超 chunk_size 时按句子硬切（照原版思想）。"""
    sentences = re.split(r"(?<=[。！？.!?])\s*", text)
    chunks: list[dict] = []
    buf = ""
    start = 0
    for s in sentences:
        if not s:
            continue
        if _count_tokens(buf + s) > chunk_size and buf:
            chunks.append({"content": buf, "token_count": _count_tokens(buf), "char_start": start, "char_end": start + len(buf)})
            start += max(0, len(buf) - overlap * 4)
            buf = text[start : start + len(s)]
            continue
        buf += s
    if buf:
        chunks.append({"content": buf, "token_count": _count_tokens(buf), "char_start": start, "char_end": start + len(buf)})
    return chunks


def chunk_text(
    text: str,
    chunk_size: int = 512,
    overlap: int = 50,
) -> list[dict]:
    """把文本切成带重叠的分块（照原版：尊重段落边界）。

    返回每个分块含: content / token_count / char_start / char_end。
    """
    if not text or not text.strip():
        return []
    chunk_size = max(1, chunk_size)
    overlap = max(0, min(overlap, chunk_size - 1))

    paragraphs = _split_paragraphs(text)
    if not paragraphs:
        return []

    chunks: list[dict] = []
    current_parts: list[str] = []
    current_tokens = 0
    current_start = paragraphs[0]["start"]
    overlap_text = ""

    for para in paragraphs:
        para_text = para["text"]
        para_tokens = _count_tokens(para_text)

        # 单段超长：先冲刷当前缓冲，再硬切该段
        if para_tokens > chunk_size:
            if current_parts:
                chunks.append(
                    {"content": "\n".join(current_parts), "token_count": current_tokens,
                     "char_start": current_start, "char_end": para["start"]}
                )
                current_parts = []
                current_tokens = 0
                overlap_text = chunks[-1]["content"][-(overlap * 4):] if overlap > 0 else ""
            sub = _hard_split(para_text, chunk_size, overlap)
            chunks.extend(sub)  # 合并硬切出的分块（性能：一次性 extend）
            if chunks and overlap > 0:
                overlap_text = chunks[-1]["content"][-(overlap * 4):]
            continue

        # 加这段会超 chunk_size → 冲刷当前块，下一块带上 overlap
        if current_tokens + para_tokens > chunk_size and current_parts:
            chunks.append(
                {"content": "\n".join(current_parts), "token_count": current_tokens,
                 "char_start": current_start, "char_end": para["start"]}
            )
            current_parts = []
            current_tokens = 0
            if overlap > 0 and overlap_text:
                current_parts.append(overlap_text)
                current_tokens = _count_tokens(overlap_text)
            current_start = para["start"]

        current_parts.append(para_text)
        current_tokens += para_tokens

    # 收尾：冲刷剩余缓冲
    if current_parts:
        chunks.append(
            {"content": "\n".join(current_parts), "token_count": current_tokens,
             "char_start": current_start, "char_end": len(text)}
        )
    return chunks
