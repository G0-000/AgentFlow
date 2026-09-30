# ============================================================================
# AgentFlow · knowledge/embedding/registry.py —— 向量模型注册与公共 API
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/knowledge/embedding/registry.py
# 对标来源: evoflow/knowledge/embedding/registry.py
#   原版规则（照搬思想）:
#     - vendor == "local" → 本地 provider（LM Studio/Ollama）
#     - 模型 id 含 "/" 且无 base_url（HF repo 形态）→ 本地 provider
#     - 否则 → 云端 provider（OpenAI 兼容 /embeddings）
#   原版异步；M3 简化成同步（CLI 是同步入口）。
# 里程碑: M3
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────┐
# │ CloudEmbeddingProvider(EmbeddingProvider)          │
# │   embed_batch(texts) → POST {base_url}/embeddings  │
# │   请求体: {"model":..., "input": texts}            │
# │   （OpenAI 兼容协议，智谱/DeepSeek/本地都认）       │
# │                                                    │
# │ LocalEmbeddingProvider(EmbeddingProvider)          │
# │   同上协议（base_url 指向 LM Studio / Ollama）      │
# │                                                    │
# │ get_embedding(text, cfg) → list[float]             │
# │ get_embeddings(texts, cfg) → list[list[float]]     │
# │   （LRU 缓存：同文本同模型不重复调后端）            │
# │                                                    │
# │ known_embedding_dim(model_id) → int | None         │
# │ detect_embedding_dim(cfg, fallback) → int          │
# │   已知表 → 探针调用 → 兜底                          │
# └────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 配置驱动切换：云端/本地只改 config.yaml 的 embedding 段，
#    代码零改动（验收点 4）。判定规则照原版。
# 2. 全走 OpenAI 兼容协议：一个实现通吃所有供应商。
# 3. LRU 缓存：同一段文本不重复向量化（省 token/时间）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. get_embedding / get_embeddings: 向量化公共 API
# 2. known_embedding_dim / detect_embedding_dim: 维度探测
# 3. CloudEmbeddingProvider / LocalEmbeddingProvider: 两个后端
# 🔒 内部私有函数
# 1. _is_local_config: 判断是否走本地（vendor/模型形态）
# 2. _resolve_provider: 按配置选 provider
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. 维度一致性是检索正确性的前提：建库与查询必须同一模型同一维度
# 2. 缓存 key = (文本, 模型名)；换模型后缓存自动失效（key 变）
# 3. 后端失败抛 EmbeddingError；调用方（service/CLI）负责友好提示
# ============================================================================

from __future__ import annotations

from functools import lru_cache

from agentflow.config.model_config import ChatModelConfig
from agentflow.knowledge.embedding.base import (
    DEFAULT_EMBEDDING_DIM,
    DEFAULT_EMBEDDING_MODEL,
    EmbeddingError,
    EmbeddingProvider,
)

# 已知模型 → 维度表（照原版；新模型在此追加，避免探针调用）
_KNOWN_DIMS: dict[str, int] = {
    # 云端（OpenAI 兼容）
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
    # 智谱
    "embedding-3": 2048,
    "embedding-2": 1024,
    # 本地（BGE 系列）
    "baai/bge-small-zh-v1.5": 512,
    "baai/bge-base-zh-v1.5": 768,
    "baai/bge-large-zh-v1.5": 1024,
    "baai/bge-m3": 1024,
    "bge-small-zh-v1.5": 512,
    "bge-base-zh-v1.5": 768,
    "bge-large-zh-v1.5": 1024,
    "bge-m3": 1024,
}


def known_embedding_dim(model_id: str) -> int | None:
    """查已知维度表（大小写不敏感）；未知返回 None。"""
    if not model_id:
        return None
    return _KNOWN_DIMS.get(model_id.strip().lower())


def _is_local_config(cfg: ChatModelConfig) -> bool:
    """判断该配置是否走本地 provider（照原版规则）。"""
    vendor = (cfg.provider or "").strip().lower()
    if vendor == "local":
        return True
    model_id = (cfg.model or "").strip()
    base_url = (cfg.base_url or "").strip()
    # HF repo 形态（org/name 且无 base_url）→ 本地
    return "/" in model_id and not base_url and not model_id.startswith(("http://", "https://"))


class CloudEmbeddingProvider(EmbeddingProvider):
    """云端向量化（OpenAI 兼容 /embeddings 协议）。"""

    def __init__(self, cfg: ChatModelConfig) -> None:
        self.cfg = cfg
        self.model_name = (cfg.model or DEFAULT_EMBEDDING_MODEL).strip() or DEFAULT_EMBEDDING_MODEL

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            import requests
        except ImportError as exc:
            raise EmbeddingError("requests 未安装，无法向量化") from exc

        url = f"{self.cfg.base_url.rstrip('/')}/embeddings"
        headers = {"Authorization": f"Bearer {self.cfg.api_key}"}
        try:
            resp = requests.post(
                url, headers=headers, json={"model": self.model_name, "input": texts}, timeout=60
            )
            resp.raise_for_status()
            data = resp.json().get("data") or []
            # 按 index 排序，保证与输入顺序一致
            ordered = sorted(data, key=lambda d: int(d.get("index", 0)))
            vecs = [d["embedding"] for d in ordered]
            if len(vecs) != len(texts):
                raise EmbeddingError(f"向量化返回 {len(vecs)} 条，期望 {len(texts)} 条")
            return vecs
        except EmbeddingError:
            raise
        except Exception as exc:  # 网络/鉴权/格式错误统一包装为 EmbeddingError
            raise EmbeddingError(f"云端向量化失败: {type(exc).__name__}: {str(exc)[:200]}") from exc


class LocalEmbeddingProvider(EmbeddingProvider):
    """本地向量化（LM Studio / Ollama，同一 OpenAI 兼容协议）。"""

    def __init__(self, cfg: ChatModelConfig) -> None:
        self.cfg = cfg
        self.model_name = (cfg.model or DEFAULT_EMBEDDING_MODEL).strip() or DEFAULT_EMBEDDING_MODEL

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        # 协议与云端完全一致，只换 base_url/api_key（api_key 本地通常随意填）
        return CloudEmbeddingProvider(self.cfg).embed_batch(texts)


def _resolve_provider(cfg: ChatModelConfig | None) -> EmbeddingProvider:
    """按配置选 provider（云端/本地）。"""
    mc = cfg or ChatModelConfig(
        provider="openai", model=DEFAULT_EMBEDDING_MODEL, base_url="", api_key=""
    )
    if _is_local_config(mc):
        return LocalEmbeddingProvider(mc)
    return CloudEmbeddingProvider(mc)


@lru_cache(maxsize=256)
def _embed_cached(text: str, model_name: str, base_url: str, api_key: str, provider_kind: str) -> tuple[float, ...]:
    """单条文本向量化（LRU 缓存：同文本同模型不重复调后端）。"""
    cfg = ChatModelConfig(
        provider="local" if provider_kind == "local" else "openai",
        base_url=base_url, model=model_name, api_key=api_key,
    )
    vec = _resolve_provider(cfg).embed_batch([text])[0]
    return tuple(vec)


def get_embeddings(texts: list[str], cfg: ChatModelConfig | None = None) -> list[list[float]]:
    """批量向量化（缓存感知：已缓存的文本不重复调用）。"""
    if not texts:
        return []
    mc = cfg or ChatModelConfig(
        provider="openai", model=DEFAULT_EMBEDDING_MODEL, base_url="", api_key=""
    )
    kind = "local" if _is_local_config(mc) else "cloud"
    out: list[list[float]] = []
    for t in texts:
        cached = _embed_cached(t, mc.model, mc.base_url, mc.api_key, kind)
        out.append(list(cached))
    return out


def get_embedding(text: str, cfg: ChatModelConfig | None = None) -> list[float]:
    """单条向量化（公共入口）。"""
    return get_embeddings([text], cfg)[0]


def detect_embedding_dim(
    cfg: ChatModelConfig | None = None,
    *,
    fallback: int = DEFAULT_EMBEDDING_DIM,
) -> int:
    """探测向量维度：已知表 → 探针调用 → 兜底（照原版）。"""
    mc = cfg or ChatModelConfig(
        provider="openai", model=DEFAULT_EMBEDDING_MODEL, base_url="", api_key=""
    )
    known = known_embedding_dim(mc.model)
    if known is not None:
        return known
    try:
        vec = get_embedding("dimension probe", mc)
        if vec:
            return len(vec)
    except EmbeddingError:
        pass
    return fallback
