# ============================================================================
# AgentFlow · models/factory.py —— 模型工厂
# ----------------------------------------------------------------------------
# 文件: backend/packages/harness/agentflow/models/factory.py
# 仿原: evoflow/models/factory.py
#       （原版按 `use` 字段 "包.模块:类" 动态加载任意模型类；
#        M1 简化为按 provider 分发，use 机制留到 M6 多供应商时再学）
# 里程碑: M1
# ----------------------------------------------------------------------------
# 结构图:
# ┌──────────────────────────────────────────────┐
# │ create_chat_model(ChatModelConfig)           │
# │   │                                         │
# │   ├─ provider = openai-compatible → ChatOpenAI│
# │   ├─ provider = openai           → ChatOpenAI│
# │   ├─ provider = zhipu           → ChatOpenAI│
# │   └─ 其他 → raise ValueError                 │
# └──────────────────────────────────────────────┘
# ============================================================================
from __future__ import annotations

# BaseChatModel: LangChain 模型统一接口（所有模型类的抽象基类）
from langchain_core.language_models import BaseChatModel

from agentflow.config.model_config import ChatModelConfig
from agentflow.models.patched_openai import create_openai_compatible_chat

# provider 白名单：当前支持的供应商类型（都走 OpenAI 兼容协议）
_SUPPORTED_PROVIDERS = ("openai-compatible", "openai", "zhipu")


def create_chat_model(cfg: ChatModelConfig) -> BaseChatModel:
    """按配置创建对话模型（工厂入口）。

    参数:
        cfg: ChatModelConfig（provider/base_url/model/api_key/temperature）

    返回:
        BaseChatModel: 可直接被 create_agent 使用的模型实例

    扩展点（M6）: 增加供应商只需:
        1. patched_xxx.py 加适配函数
        2. 本函数加一个 provider 分支
    配置驱动，Agent 层代码不动。
    """
    if cfg.provider in _SUPPORTED_PROVIDERS:
        return create_openai_compatible_chat(cfg)
    raise ValueError(f"不支持的 provider: {cfg.provider}")
