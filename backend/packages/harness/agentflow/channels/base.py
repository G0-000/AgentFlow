# ============================================================================
# AgentFlow · channels/base.py —— IM 渠道抽象基类（裁剪自 EvoFlow）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/channels/base.py
# 对标来源: evoflow/app/channels/base.py（原版 181 行，含 MessageBus/文件上传/流式补丁）
# 里程碑: M7（IM 渠道：飞书先发）
#   裁剪决策: 原版靠 MessageBus 解耦「收消息 ↔ 跑 Agent ↔ 回发」，
#   并支持文件上传、流式卡片补丁、多账号。M7 只做「单轮：收→跑 Agent→回发」，
#   故去掉 Bus/上传/流式，只留 Channel ABC + 归一化入站消息 InboundMessage。
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌───────────────────────────────────────────────────────┐
# │ InboundMessage(dataclass)  归一化入站消息              │
# │   channel / chat_id / user_id / text / msg_id /       │
# │   reply_to / metadata                                 │
# │                                                       │
# │ Channel(ABC)                                          │
# │   name: str = "channel"                              │
# │   start() / stop()            ← 抽象生命周期           │
# └───────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 归一化: 各 IM 平台事件结构不同（飞书/企微/Slack…），统一折叠成 InboundMessage，
#    下游「跑 Agent → 回发」逻辑与具体平台解耦。
# 2. 最小抽象: 原版 Channel 还挂 bus.send_file/_on_outbound 等；M7 暂不需要，
#    需要时再按本基类扩展（不要一次性搬全原版）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. InboundMessage: 归一化入站消息 dataclass
# 2. Channel: IM 渠道抽象基类
# 🔒 内部私有函数
# 无
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. Channel.start/stop 是抽象方法：子类不实现直接实例化报错（ABC 机制）
# 2. InboundMessage.reply_to 语义 = 平台侧「要回复的那条消息 id」
#    （飞书 im.v1.message.reply 用它），不是 LangGraph thread_id
# ============================================================================

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class InboundMessage:
    """一条外部 IM 收到、已归一化的入站消息。

    把各平台 SDK 的事件对象折叠成平台无关的字段；下游渠道逻辑只认它。
    """

    channel: str
    """来源渠道名（如 "feishu"）。"""

    chat_id: str
    """平台侧会话/群 id（用于映射 LangGraph thread_id）。"""

    user_id: str
    """发送者 id（平台 open_id 等，审计/限流用）。"""

    text: str
    """归一化后的纯文本（已去 @、去 BOM/零宽字符）。"""

    msg_id: str = ""
    """平台侧消息 id（去重主键之一）。"""

    reply_to: str = ""
    """回发时要 reply 的那条消息 id（楼中楼取 root_id，否则取 msg_id）。"""

    metadata: dict[str, Any] = field(default_factory=dict)
    """扩展字段（chat_type / root_id 等调试信息）。"""


class Channel(ABC):
    """所有 IM 渠道的抽象基类。

    职责（M7 裁剪版）：
        1. 接收外部平台消息 → 归一化为 InboundMessage；
        2. 去重 → 用 AgentRunner 跑 Agent；
        3. 把回复发回平台。

    子类只需实现 start / stop；具体平台的事件解析与回发在子类内聚。
    """

    name: str = "channel"

    @abstractmethod
    def start(self) -> None:
        """开始监听外部平台消息（阻塞或起后台线程，按渠道实现）。"""

    @abstractmethod
    def stop(self) -> None:
        """优雅停止渠道。"""
