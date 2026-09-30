# ============================================================================
# AgentFlow · knowledge/service.py —— 知识库总入口
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/knowledge/service.py
# 对标来源: evoflow/knowledge/service.py（原版服务复杂：索引/解析/多库）
#   M3 简化成最小闭环: 建库（导入 → 分块 → 向量化 → 落库）
#   + 检索（query → 向量化 → 余弦相似度 → 格式化命中）。
# 里程碑: M3
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────┐
# │ cosine(a, b) → float                               │
# │   余弦相似度（向量检索的打分函数）                  │
# │                                                    │
# │ KnowledgeService                                  │
# │   __init__(repo, embedding_cfg)                    │
# │   create_doc(title, text, source="") → doc_id      │
# │     text → chunk_text() → get_embeddings()         │
# │     → repo.create_doc + repo.add_chunk             │
# │   search(query, top_k=3) → list[dict]              │
# │     query → get_embedding() → 余弦全库 → 取 top_k  │
# │   list_docs() → 文档列表（工具 list 用）            │
# │   get_doc(doc_id) → 单文档（工具 read 用）          │
# └────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 知识库 = 分块 → 向量 → 相似度检索，三步闭环（M3 验收点 2/3）。
# 2. 维度一致性：建库/查询用同一个 embedding_cfg，否则相似度无意义。
# 3. 检索失败（如 embedding 不可用）给友好提示，不抛崩。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. KnowledgeService: 知识库总入口（建库/检索/列表）
# 🔒 内部私有函数
# 1. cosine: 余弦相似度
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. 建库/查询必须同一 embedding 模型同一维度（验收排查表第一项）
# 2. 全库线性扫描 M3 够用；M5 接向量库（faiss）时只换检索实现
# 3. embedding 失败时 create_doc 抛 EmbeddingError，CLI 负责提示
# ============================================================================

from __future__ import annotations

import json
import math

from agentflow.config.model_config import ChatModelConfig
from agentflow.knowledge.chunker import chunk_text
from agentflow.knowledge.embedding.registry import (
    get_embedding,
    get_embeddings,
)
from agentflow.persistence.knowledge_repositories import KnowledgeRepository


def cosine(a: list[float], b: list[float]) -> float:
    """余弦相似度（向量检索打分；维度不一致返回 0）。"""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class KnowledgeService:
    """知识库总入口：建库 + 检索（M3 最小闭环）。"""

    def __init__(self, repo: KnowledgeRepository, embedding_cfg: ChatModelConfig) -> None:
        self.repo = repo
        self.embedding_cfg = embedding_cfg

    def create_doc(self, title: str, text: str, source: str = "") -> int:
        """导入文档：分块 → 向量化 → 落库，返回 doc_id。

        异常: 向量化失败抛 EmbeddingError（由调用方友好提示）。
        """
        chunks = chunk_text(text)
        if not chunks:
            raise ValueError("文档内容为空，无法建库")
        doc_id = self.repo.create_doc(title, source)
        texts = [c["content"] for c in chunks]
        vecs = get_embeddings(texts, self.embedding_cfg)
        for c, v in zip(chunks, vecs):
            self.repo.add_chunk(doc_id, c["content"], json.dumps(v))
        return doc_id

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """检索：query → 向量 → 余弦相似度 → top_k 命中（格式化）。"""
        try:
            qv = get_embedding(query, self.embedding_cfg)
        except Exception as exc:  # noqa: BLE001 —— 向量化失败返回友好提示
            return [{"title": "（检索失败）", "score": 0.0, "content": f"向量化失败: {type(exc).__name__}: {str(exc)[:120]}"}]

        rows = self.repo.all_chunks()
        scored = []
        for r in rows:
            try:
                vec = json.loads(r["embedding"] or "[]")
            except ValueError:
                continue
            scored.append((cosine(qv, vec), r))
        scored.sort(key=lambda t: t[0], reverse=True)
        hits = []
        for score, r in scored[:top_k]:
            hits.append(
                {
                    "title": r["doc_title"] or f"文档{r['doc_id']}",
                    "score": score,
                    "content": (r["content"] or "")[:400],
                    "doc_id": r["doc_id"],
                }
            )
        return hits

    def list_docs(self) -> list:
        """文档列表（knowledge 工具 list 动作用）。"""
        return self.repo.list_docs()

    def get_doc(self, doc_id: int):
        """单文档（knowledge 工具 read 动作用）。"""
        return self.repo.get_doc(doc_id)
