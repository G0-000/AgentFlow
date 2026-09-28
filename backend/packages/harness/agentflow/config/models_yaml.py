# ============================================================================
# AgentFlow · config/models_yaml.py —— yaml models 段解析
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/config/models_yaml.py
# 对标来源: evoflow/config/models_yaml.py
#   原版支持"yaml 模型 → SQLite 迁移"；M1 只做最简解析 + ${ENV} 展开。
# 里程碑: M1
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────────┐
# │ load_models_from_yaml(raw dict)                  │
# │   raw = { "chat": { provider/base_url/model/...}}│
# │   ① 无 raw → 返回 None                          │
# │   ② chat 段字段逐项读取（缺省走默认）            │
# │   ③ api_key 经 _resolve_env 展开 ${ENV}          │
# │   ④ 返回 ModelConfig(chat=...)                  │
# └──────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 密钥不落 yaml（安全）：${ENV} 由本层统一展开，读取 .env。
# 2. 提供"获取 config 数据"的对外方法：app_config 只调这一个函数，
#    其他模块不直接碰 yaml 细节。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. load_models_from_yaml: yaml models 段 → ModelConfig
# 🔒 内部私有函数
# 1. _resolve_env: ${ENV} 占位符展开（读环境变量）
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. ${ENV} 展开失败时返回原样字符串（调用方兜底，勿抛异常）
# 2. 字段缺省默认值与 model_config.py 的 dataclass 默认值需保持一致
# ============================================================================

from __future__ import annotations

import os

from agentflow.config.model_config import ChatModelConfig, ModelConfig


def _resolve_env(value: str) -> str:
    """展开 ${ENV_VAR} 占位符为环境变量值。

    设计动机: 密钥（api_key）不应明文写入 config.yaml（会进 git 泄露），
    所以配置里写 ${ZHIPU_API_KEY} 这类占位，运行时从环境/.env 取。
    非占位格式（普通字符串）原样返回。
    """
    if value.startswith("${") and value.endswith("}"):
        return os.environ.get(value[2:-1], "")
    return value


def load_models_from_yaml(raw: dict | None) -> ModelConfig | None:
    """从 config.yaml 的 models 段构建 ModelConfig。

    参数:
        raw: yaml 里的 models 段（dict），如 {"chat": {...}}；缺省传 None

    返回:
        ModelConfig | None —— 没有 models 段时返回 None（调用方需判空）
    """
    # ① 没有 models 段 → 返回 None（cli 据此提示"缺少模型配置"）
    if not raw:
        return None

    # ② 读取 chat 段（缺省给空 dict，字段再逐个兜底默认值）
    chat_raw = raw.get("chat") or {}

    # ③ 逐字段装配，api_key 走环境变量展开
    chat = ChatModelConfig(
        provider=chat_raw.get("provider", "openai-compatible"),
        base_url=chat_raw.get("base_url", ""),
        model=chat_raw.get("model", ""),
        api_key=_resolve_env(chat_raw.get("api_key", "")),
        temperature=float(chat_raw.get("temperature", 0.3)),
    )
    return ModelConfig(chat=chat)
