# ============================================================================
# AgentFlow · tests/test_embedding_registry.py —— 向量模型注册测试（M3）
# 验收点 4：向量模型可切换。覆盖：已知维度表 / 本地判定规则 / 维度探测兜底。
# ============================================================================
import agentflow.knowledge.embedding.registry as reg
from agentflow.config.model_config import ChatModelConfig
from agentflow.knowledge.embedding.base import EmbeddingError
from agentflow.knowledge.embedding.registry import (
    CloudEmbeddingProvider,
    LocalEmbeddingProvider,
    _is_local_config,
    detect_embedding_dim,
    known_embedding_dim,
)


def test_known_embedding_dim_map():
    """已知模型维度表（大小写不敏感）。"""
    assert known_embedding_dim("bge-m3") == 1024
    assert known_embedding_dim("BAAI/bge-m3") == 1024
    assert known_embedding_dim("embedding-3") == 2048
    assert known_embedding_dim("text-embedding-3-small") == 1536
    assert known_embedding_dim("no-such-model") is None


def test_is_local_config_vendor_local():
    """vendor=local → 本地 provider（配置驱动切换的开关）。"""
    cfg = ChatModelConfig(provider="local", base_url="http://127.0.0.1:1234/v1", model="bge-m3")
    assert _is_local_config(cfg) is True


def test_is_local_config_hf_repo_without_base_url():
    """HF repo 形态（org/name 且无 base_url）→ 本地。"""
    cfg = ChatModelConfig(provider="openai", base_url="", model="baai/bge-small-zh-v1.5")
    assert _is_local_config(cfg) is True


def test_is_local_config_cloud():
    """云端配置（有 base_url + 非 local vendor）→ 非本地。"""
    cfg = ChatModelConfig(provider="zhipu", base_url="https://open.bigmodel.cn/api/paas/v4", model="embedding-3")
    assert _is_local_config(cfg) is False


def test_provider_resolution_kind():
    """解析出的 provider 类型与配置匹配。"""
    cloud = reg._resolve_provider(ChatModelConfig(provider="zhipu", model="embedding-3"))
    local = reg._resolve_provider(ChatModelConfig(provider="local", model="bge-m3"))
    assert isinstance(cloud, CloudEmbeddingProvider)
    assert isinstance(local, LocalEmbeddingProvider)


def test_detect_dim_known_fast_path():
    """已知模型直接返回维度（不调用探针）。"""
    cfg = ChatModelConfig(provider="zhipu", model="embedding-3")
    assert detect_embedding_dim(cfg) == 2048


def test_detect_dim_fallback_on_probe_failure(monkeypatch):
    """未知模型 + 探针失败 → 兜底维度（不崩）。"""
    def boom(*a, **k):
        raise EmbeddingError("backend down")

    monkeypatch.setattr(reg, "get_embedding", boom)
    cfg = ChatModelConfig(provider="openai", model="mystery-embedder")
    assert detect_embedding_dim(cfg, fallback=768) == 768
