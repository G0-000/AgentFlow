# ============================================================================
# AgentFlow · models/patched_openai.py —— OpenAI 兼容供应商适配
# ----------------------------------------------------------------------------
# 文件: backend/packages/harness/agentflow/models/patched_openai.py
# 仿原: evoflow/models/patched_openai.py
#       （原版为什么要 patch：不同供应商在 extra body / 参数别名 / 流式格式
#        上有细微差异，需要一个收敛层统一处理。M1 直接返回标准 ChatOpenAI，
#        先留出扩展点；M6 做多供应商时再补 patch）
# 里程碑: M1
# ----------------------------------------------------------------------------
# 结构图:
# ┌──────────────────────────────────────────────┐
# │ create_openai_compatible_chat(ChatModelConfig)│
# │   → ChatOpenAI(                              │
# │       api_key=cfg.api_key,                   │
# │       base_url=cfg.base_url,                 │
# │       model=cfg.model,                       │
# │       temperature=cfg.temperature,           │
# │     )                                        │
# └──────────────────────────────────────────────┘
# ============================================================================
from __future__ import annotations

# ChatOpenAI: LangChain 对 OpenAI 协议的封装
# 它向 base_url 发 /chat/completions 请求——DeepSeek/GLM/Ollama/LM Studio 都兼容
from langchain_openai import ChatOpenAI

from agentflow.config.model_config import ChatModelConfig


def create_openai_compatible_chat(cfg: ChatModelConfig) -> ChatOpenAI:
    """创建 OpenAI 兼容协议的对话模型（DeepSeek / GLM / 本地服务通用）。

    参数:
        cfg: ChatModelConfig（base_url 指向对应供应商的 OpenAI 兼容端点）

    返回:
        ChatOpenAI: 已配置好地址/模型/密钥的实例
    """
    # 供应商专属请求参数（patch 层职责：不同供应商在 extra body 上有细微差异）
    extra_body: dict = {}
    if cfg.provider == "zhipu":
        # 智谱 thinking 模型默认开启思维链 → 流式时内容在 delta.reasoning_content，
        # langchain-openai 只解析 delta.content → 全空（CLI 打字不出内容，见 P-016）。
        # 关闭思考模式：内容走标准 content 字段（对话场景不需要思维链）。
        extra_body["thinking"] = {"type": "disabled"}

    return ChatOpenAI(
        api_key=cfg.api_key,        # 密钥（构造时就校验，为空会抛 Missing credentials）
        base_url=cfg.base_url,      # API 地址（如 https://api.deepseek.com/v1）
        model=cfg.model,            # 模型名（如 deepseek-chat）
        temperature=cfg.temperature,  # 采样温度
        timeout=60,                 # 请求超时兜底（秒）：免费模型高峰可能"挂起"不返回
        #   —— 60s 无响应抛 APITimeoutError，由 CLI 容错打印友好提示，不会无限等
        #   —— 实测：智谱 GLM-4.7-Flash 高峰 code 1305 限流（见问题日志 P-015）
        **({"extra_body": extra_body} if extra_body else {}),
    )
