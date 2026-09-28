# ============================================================================
# AgentFlow · config/models_yaml.py —— yaml models 段解析
# ----------------------------------------------------------------------------
# 文件: backend/packages/harness/agentflow/config/models_yaml.py
# 仿原: evoflow/config/models_yaml.py（原版支持"yaml 模型 → SQLite 迁移"，
#       M1 只做最简解析 + ${ENV} 占位展开）
# 里程碑: M1
# ----------------------------------------------------------------------------
# 结构图:
# ┌──────────────────────────────────────────────────┐
# │ load_models_from_yaml(raw dict)                  │
# │   raw = { "chat": { provider/base_url/model/...}}│
# │   ① 无 raw → 返回 None                          │
# │   ② chat 段字段逐项读取（缺省走默认）            │
# │   ③ api_key 经 _resolve_env 展开 ${ENV}          │
# │   ④ 返回 ModelConfig(chat=...)                  │
# └──────────────────────────────────────────────────┘
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
