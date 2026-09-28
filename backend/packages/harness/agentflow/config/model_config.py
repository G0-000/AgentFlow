# ============================================================================
# AgentFlow · config/model_config.py —— 模型配置类型
# ----------------------------------------------------------------------------
# 文件: backend/packages/harness/agentflow/config/model_config.py
# 仿原: evoflow/config/model_config.py（原版字段很多：use/params/vendor 专属；
#       M1 只保留"连接一个对话模型"必需的字段）
# 里程碑: M1
# ----------------------------------------------------------------------------
# 结构图:
# ┌──────────────────────────────────────────────┐
# │ ModelConfig                                  │
# │   └── chat: ChatModelConfig                  │
# │         provider  : 供应商类型（分发依据）     │
# │         base_url  : API 地址                  │
# │         model     : 模型名                    │
# │         api_key   : 密钥（支持 ${ENV}）       │
# │         temperature: 采样温度                 │
# └──────────────────────────────────────────────┘
# ============================================================================
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ChatModelConfig:
    """对话模型配置。

    设计说明: 所有供应商（DeepSeek / 智谱 GLM / Ollama / LM Studio）
    都走 OpenAI 兼容协议，因此同一套字段即可覆盖全部——
    factory.py 只按 provider 分发，代码不用为每家供应商单独写配置类。
    """

    provider: str = "openai-compatible"  # 供应商类型；factory 按它分发
    base_url: str = ""                   # API 地址，如 https://api.deepseek.com/v1
    model: str = ""                      # 模型名，如 deepseek-chat / glm-4.7-flash
    api_key: str = ""                    # 密钥；支持 ${ENV} 占位（models_yaml 展开）
    temperature: float = 0.3             # 采样温度：越低越确定，越高越发散


@dataclass
class ModelConfig:
    """模型配置集合（M1 只有对话模型；M3 会加 embedding）。"""

    chat: ChatModelConfig = field(default_factory=ChatModelConfig)
