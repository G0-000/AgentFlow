# ============================================================================
# AgentFlow · models/factory.py —— 模型工厂
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/models/factory.py
# 对标来源: evoflow/models/factory.py
#   原版按 use 字段"包.模块:类"动态加载任意模型类；
#   M1 简化为按 provider 分发，use 机制留到 M6 多供应商时再学。
# 里程碑: M1
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────┐
# │ create_chat_model(ChatModelConfig)           │
# │   │                                         │
# │   ├─ provider = openai-compatible → ChatOpenAI│
# │   ├─ provider = openai           → ChatOpenAI│
# │   ├─ provider = zhipu           → ChatOpenAI│
# │   └─ 其他 → raise ValueError                 │
# └──────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 工厂模式：配置 → 模型实例，调用方不关心具体供应商。
# 2. 全走 OpenAI 兼容协议（zhipu/deepseek/openai 都是），
#    ChatOpenAI 换 base_url + api_key 即可（Q: 为什么都走 OpenAI 兼容）。
# 3. 测试注入点：测试可传 mock 模型，不真调 API。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. create_chat_model: 按配置创建对话模型
# 🔒 内部私有函数
# 无
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. provider 白名单外直接 raise ValueError（宁可失败不静默换供应商）
# 2. 新增供应商 = 加一个分支 + config.yaml 注释说明，勿破坏现有分支
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
