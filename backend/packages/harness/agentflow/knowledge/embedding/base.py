# ============================================================================
# AgentFlow · knowledge/embedding/base.py —— embedding 基类与常量
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/knowledge/embedding/base.py
# 对标来源: evoflow/knowledge/embedding/base.py
# 里程碑: M3
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────┐
# │ 常量:                                          │
# │   DEFAULT_EMBEDDING_MODEL / DEFAULT_EMBEDDING_DIM│
# │   MAX_BATCH_SIZE                               │
# │ 异常:                                          │
# │   EmbeddingError / EmbeddingDimensionError     │
# │ 抽象:                                          │
# │   EmbeddingProvider                            │
# │     model_name: str                            │
# │     embed_batch(texts) -> list[list[float]]    │
# └────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 抽象接口：云端/本地 provider 只实现 embed_batch，
#    上层（registry/service）不感知供应商差异。
# 2. 异常类型先行：维度不匹配等错误有专属异常，便于排查。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. EmbeddingProvider: 向量模型抽象基类
# 2. EmbeddingError / EmbeddingDimensionError: 异常
# 3. 常量（模型名/维度/批大小）
# 🔒 内部私有函数
# 无
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. embed_batch 必须保持输入顺序与输出一一对应（下游按 index 对齐）
# 2. 维度校验统一抛 EmbeddingDimensionError，勿静默截断
# ============================================================================

from __future__ import annotations

# 默认向量模型（OpenAI 兼容命名；M3 未配置时的兜底）
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_EMBEDDING_DIM = 1536

# 单次批量向量化最大条数（照原版）
MAX_BATCH_SIZE = 100


class EmbeddingError(Exception):
    """向量化后端错误（网络/鉴权/本地加载失败）。"""


class EmbeddingDimensionError(EmbeddingError):
    """向量维度与预期不符。"""


class EmbeddingProvider:
    """向量模型抽象基类（云端/本地各自实现 embed_batch）。"""

    model_name: str = DEFAULT_EMBEDDING_MODEL

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量向量化（顺序与输入一致）。

        返回: texts 等长的向量列表。
        """
        raise NotImplementedError
