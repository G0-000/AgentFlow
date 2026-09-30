# ============================================================================
# AgentFlow · memory/consolidate.py —— 记忆沉淀（事实提取）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/memory/consolidate.py
# 对标来源: evoflow/memory/consolidate.py
#   原版：L2-L4 分层记忆 + 相似度合并/衰减/GC（复杂）；M3 简化成
#   【规则事实提取】——从用户话里抽"我叫X/我喜欢X"类事实落库。
# 里程碑: M3
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────┐
# │ extract_facts(text) → list[str]                │
# │   规则匹配（中文优先）:                         │
# │     我叫/我是/我喜欢/我爱/我住在/我来自/        │
# │     我在/我会/我擅长/我是做…的/…              │
# │   命中 → 整理成"用户X"标准句（去重）            │
# │                                                │
# │ consolidate_message(thread_id, role, content,  │
# │                     repo) → int                │
# │   只处理 user 消息 → extract_facts → 落库       │
# │   返回本次沉淀条数（CLI 可显示"已记住"）        │
# └────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 记忆 ≠ 对话全文：只沉淀"可复用的事实"（跨会话才有意义）。
# 2. 规则提取 100% 稳定（不调模型）：M3 验收不依赖模型/限流；
#    后续想换 LLM 抽取只需替换 extract_facts 内部实现。
# 3. 中文优先：用户是中文对话，规则按中文句式写（原版是英文 token）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. extract_facts: 从文本提取事实列表
# 2. consolidate_message: 单条消息沉淀（提取 + 落库）
# 🔒 内部私有函数
# 1. _norm: 事实标准化（去多余空格/引号）
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. 规则命中不了的事实（自由表述）M3 不沉淀——可接受（最小闭环）
# 2. 同内容重复落库由 _dedup（会话内去重）缓解；跨会话全库去重 M5 再学
# 3. 只沉淀 user 消息：assistant 回复是模型话术，不是用户事实
# ============================================================================

from __future__ import annotations

import re
from typing import Protocol

# 事实提取规则：pattern → 标准化模板（{} 内是捕获的用户信息）
_FACT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"我叫([\u4e00-\u9fff\w·]{1,20})"), "用户叫{0}"),
    (re.compile(r"我是([\u4e00-\u9fff\w·]{1,20})"), "用户是{0}"),
    # 主语"我"可省略（"喜欢爬虫"与"我喜欢爬虫"都是事实）
    (re.compile(r"(?:我喜欢|喜欢)([^，。！？\n]{1,30})"), "用户喜欢{0}"),
    (re.compile(r"(?:我爱|爱)([^，。！？\n]{1,30})"), "用户爱{0}"),
    (re.compile(r"(?:我住在|住在)([^，。！？\n]{1,30})"), "用户住在{0}"),
    (re.compile(r"(?:我来自|来自)([^，。！？\n]{1,30})"), "用户来自{0}"),
    (re.compile(r"我在([^，。！？\n]{1,30})"), "用户在{0}"),
    (re.compile(r"(?:我擅长|擅长)([^，。！？\n]{1,30})"), "用户擅长{0}"),
    (re.compile(r"我会([^，。！？\n]{1,30})"), "用户会{0}"),
    (re.compile(r"我是做([^，。！？\n]{1,30})"), "用户是做{0}"),
]


class MemoryRepoLike(Protocol):
    """consolidate 只依赖 repo 的 create（便于测试注入 mock）。"""

    def create(self, thread_id: str, content: str, source_role: str = "user") -> None: ...


# 疑问词：捕获到这些词说明是提问而非陈述事实（如"我叫什么"），跳过
_QUESTION_WORDS = ("什么", "怎么", "哪", "为什么", "吗", "呢", "如何")


def _norm(fact: str) -> str:
    """标准化事实：压空白 + 去首尾空格。"""
    return re.sub(r"\s+", " ", fact).strip()


def extract_facts(text: str) -> list[str]:
    """从一句话里提取用户事实（规则匹配，中文句式优先）。

    例: "我叫小王，喜欢爬虫" → ["用户叫小王", "用户喜欢爬虫"]
    疑问句（"我叫什么"）会被过滤——那不是事实。
    """
    if not text:
        return []
    facts: list[str] = []
    seen: set[str] = set()
    for pat, template in _FACT_PATTERNS:
        for m in pat.finditer(text):
            val = _norm(m.group(1))
            if not val:
                continue
            if any(w in val for w in _QUESTION_WORDS):
                continue  # 提问而非陈述，跳过
            fact = template.format(val)
            if fact not in seen:
                seen.add(fact)
                facts.append(fact)
    return facts


def consolidate_message(thread_id: str, role: str, content: str, repo: MemoryRepoLike) -> int:
    """把一条消息里的用户事实沉淀入库（只处理 user 消息）。

    返回: 本次沉淀的条数（0 = 没提取到事实）。
    """
    if role != "user" or not content:
        return 0
    facts = extract_facts(content)
    for f in facts:
        repo.create(thread_id, f, source_role="user")
    return len(facts)
