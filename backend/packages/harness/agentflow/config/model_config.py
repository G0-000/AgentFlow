# ============================================================================
# AgentFlow · config/model_config.py —— 模型配置类型
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/config/model_config.py
# 对标来源: evoflow/config/model_config.py
#   原版字段很多（use/params/vendor 专属）；M1 只保留
#   【连接一个对话模型】必需的字段。
# 里程碑: M1
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────┐
# │ ModelConfig                                  │
# │   └── chat: ChatModelConfig                  │
# │         provider  : 供应商类型（分发依据）     │
# │         base_url  : API 地址                  │
# │         model     : 模型名                    │
# │         api_key   : 密钥（支持 ${ENV}）       │
# │         temperature: 采样温度                 │
# └──────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 配置先类型化再使用：防止散落 dict 魔法键（字段对齐原版）。
# 2. dataclass 足够（无需 pydantic 校验，M1 保持最简）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. ChatModelConfig: 对话模型配置数据类
# 2. ModelConfig: 模型配置容器（含 chat）
# 🔒 内部私有函数
# 无
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. api_key 走 ${ENV} 展开（models_yaml 处理），勿在 yaml 明文写密钥
# 2. 新增字段需同步 models_yaml.py 解析与 config.yaml 示例
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
