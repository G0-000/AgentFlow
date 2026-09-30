# ============================================================================
# AgentFlow · tests/test_knowledge_search.py —— 知识库建库+检索测试（M3）
# 验收点 2/3：建库（分块+向量化）+ 检索召回。
# 说明：用确定性"bigram 哈希向量"替换真实 embedding——测试不碰网络，
#       只验证"分块 → 落库 → 相似度排序 → 召回"这条链路本身。
# ============================================================================
import agentflow.knowledge.service as svc_mod
from agentflow.knowledge.service import KnowledgeService
from agentflow.persistence.bootstrap import init_db
from agentflow.persistence.knowledge_repositories import KnowledgeRepository
from agentflow.config.model_config import ChatModelConfig


def _fake_vec(text: str) -> list[float]:
    """确定性向量：字符 bigram 计数（相似文本共享 bigram → 余弦高）。"""
    counts: dict[str, float] = {}
    s = text.replace(" ", "")
    for i in range(len(s) - 1):
        gram = s[i : i + 2]
        counts[gram] = counts.get(gram, 0) + 1
    if not counts:
        return [0.0]
    return [counts[k] for k in sorted(counts)]


def _fake_get_embeddings(texts, cfg=None):
    return [_fake_vec(t) for t in texts]


def _fake_get_embedding(text, cfg=None):
    return _fake_vec(text)


def _service(monkeypatch):
    """构造一个"假 embedding"的知识库服务（不碰网络）。"""
    monkeypatch.setattr(svc_mod, "get_embeddings", _fake_get_embeddings)
    monkeypatch.setattr(svc_mod, "get_embedding", _fake_get_embedding)
    conn = init_db(":memory:")
    repo = KnowledgeRepository(conn)
    cfg = ChatModelConfig(model="fake-embedder")
    return KnowledgeService(repo, cfg), repo


def test_create_doc_chunks_and_stores(monkeypatch):
    """建库：导入文本 → 分块 + 向量化 → 落库有分块。"""
    svc, repo = _service(monkeypatch)
    doc_id = svc.create_doc("宠物饲养指南", "狗需要每天遛。\n猫喜欢干净的环境。")
    assert doc_id > 0
    chunks = repo.all_chunks()
    assert len(chunks) >= 1
    assert chunks[0]["doc_id"] == doc_id


def test_search_recalls_similar_chunk(monkeypatch):
    """检索：问"猫怎么养"能召回含"猫"的块（bigram 相似）。"""
    svc, _ = _service(monkeypatch)
    svc.create_doc("宠物饲养指南", "狗需要每天遛。猫喜欢干净的环境，需要猫砂盆。")
    hits = svc.search("猫怎么养", top_k=3)
    assert hits, "应至少有一个命中"
    assert any("猫" in h["content"] for h in hits)


def test_search_empty_kb_returns_empty(monkeypatch):
    """空库检索 → 无命中（不是报错）。"""
    svc, _ = _service(monkeypatch)
    assert svc.search("随便问什么") == []


def test_list_docs_after_create(monkeypatch):
    """建库后 list_docs 可见（knowledge 工具 list 用）。"""
    svc, _ = _service(monkeypatch)
    svc.create_doc("测试文档", "这是第一段。\n\n这是第二段。")
    docs = svc.list_docs()
    assert len(docs) == 1
    assert docs[0]["title"] == "测试文档"
    assert docs[0]["chunk_count"] >= 1


def test_repo_thread_safe_with_db_path():
    """P-018 回归：db_path 模式下，后台线程能用 repo（SQLite 不跨线程报错）。"""
    import threading

    from agentflow.persistence.bootstrap import init_db
    from agentflow.persistence.knowledge_repositories import KnowledgeRepository

    init_db("/tmp/agentflow_thread_test.db")  # 确保表存在
    repo = KnowledgeRepository(db_path="/tmp/agentflow_thread_test.db")
    result: list = []
    errors: list = []

    def worker():
        try:
            result.append(repo.list_docs())  # 在子线程执行 SQL
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    assert not errors, f"子线程 SQL 报错: {errors}"
    assert result == [[]] or isinstance(result[0], list)
