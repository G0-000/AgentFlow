# ============================================================================
# AgentFlow · persistence/knowledge_repositories.py —— 知识库数据访问
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/persistence/knowledge_repositories.py
# 对标来源: evoflow/persistence/xxx（原版知识库落 owned/vector 多库）
#   原版知识库有 vault/owned/vector 分层；M3 简化成
#   【knowledge_docs + knowledge_chunks 两张表】，向量以 JSON 存 BLOB。
# 里程碑: M3
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────┐
# │ KnowledgeRepository(BaseRepository)                │
# │   table_name → "knowledge_docs"                    │
# │   create_doc(title, source) → doc_id               │
# │   add_chunk(doc_id, content, embedding_json)       │
# │   list_docs() → 文档列表（标题/分块数/时间）        │
# │   get_doc(doc_id) → 单文档                        │
# │   all_chunks() → 全部分块（service 层算相似度）     │
# └────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 分块与向量同一张表：检索时一次取回，service 层算余弦相似度。
# 2. 向量用 json.dumps 存 TEXT（M3 规模小；M5 学原版上真正的
#    向量库/faiss 时再改存储，repo 接口不变）。
# 3. doc/chunk 拆两张表：文档元信息与分块内容分开，列表不拖向量。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. KnowledgeRepository: 知识库数据访问
# 🔒 内部私有函数
# 无
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. add_chunk 需先有 doc_id（外键）；先 create_doc 拿 id 再分块
# 2. embedding 参数是 JSON 字符串（service 层序列化），repo 不碰向量计算
# 3. M5 换向量库时：all_chunks 改为"向量库检索"，接口签名保持
# ============================================================================

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from agentflow.persistence.repositories import BaseRepository


class KnowledgeRepository(BaseRepository):
    """knowledge_docs / knowledge_chunks 两张表的数据访问。"""

    @property
    def table_name(self) -> str:
        return "knowledge_docs"

    def create(self, **kwargs) -> int:  # 兼容基类抽象：转 create_doc
        """建文档（兼容 BaseRepository 抽象签名）。"""
        title = str(kwargs.get("title") or "")
        source = str(kwargs.get("source") or "")
        return self.create_doc(title, source)

    def create_doc(self, title: str, source: str = "") -> int:
        """创建知识库文档，返回 doc_id（供 add_chunk 用）。"""
        now = datetime.now(UTC).isoformat()
        cur = self._execute(
            "INSERT INTO knowledge_docs (title, source, created_at) VALUES (?, ?, ?)",
            (title, source, now),
        )
        return int(cur.lastrowid)

    def add_chunk(self, doc_id: int, content: str, embedding_json: str) -> None:
        """为文档追加一个分块（含向量 JSON）。"""
        now = datetime.now(UTC).isoformat()
        self._execute(
            "INSERT INTO knowledge_chunks (doc_id, content, embedding, created_at) "
            "VALUES (?, ?, ?, ?)",
            (doc_id, content, embedding_json, now),
        )

    def list_docs(self) -> list[sqlite3.Row]:
        """列出全部文档（附带分块数，供 CLI 启动信息/知识工具 list）。"""
        return self._fetch_all(
            "SELECT d.id, d.title, d.source, d.created_at, "
            "       (SELECT COUNT(*) FROM knowledge_chunks c WHERE c.doc_id = d.id) AS chunk_count "
            "FROM knowledge_docs d ORDER BY d.created_at DESC"
        )

    def get_doc(self, doc_id: int) -> sqlite3.Row | None:
        """按 id 取单个文档。"""
        return self._fetch_one("SELECT * FROM knowledge_docs WHERE id = ?", (doc_id,))

    def all_chunks(self) -> list[sqlite3.Row]:
        """取回全部分块（含向量 JSON）；service 层负责算相似度。"""
        return self._fetch_all(
            "SELECT c.id, c.doc_id, c.content, c.embedding, d.title AS doc_title "
            "FROM knowledge_chunks c JOIN knowledge_docs d ON d.id = c.doc_id "
            "ORDER BY c.id"
        )

    def get(self, row_id: str) -> sqlite3.Row | None:  # pragma: no cover - 未用
        """按主键取文档（兼容基类抽象）。"""
        return self.get_doc(int(row_id))

    def delete(self, row_id: str) -> None:
        """删除文档（连同其分块——外键未级联，手动清）。"""
        doc_id = int(row_id)
        self._execute("DELETE FROM knowledge_chunks WHERE doc_id = ?", (doc_id,))
        self._execute("DELETE FROM knowledge_docs WHERE id = ?", (doc_id,))
