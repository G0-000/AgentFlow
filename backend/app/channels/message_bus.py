# ============================================================================
# AgentFlow · channels/message_bus.py —— IM 消息总线（M7 架构对齐补位）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/app/channels/message_bus.py
# 对标来源: evoflow/app/channels/message_bus.py（295 行：InboundMessageType /
#   InboundMessage / ResolvedAttachment / OutboundMessage / MessageBus）
# 里程碑: M7（补位：2026-10-18 对齐原版架构——文件位置先行，供 M8+ 多渠道使用）
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────────────────────┐
# │ InboundMessageType(StrEnum)   CHAT / COMMAND                 │
# │ InboundMessage(dataclass)     channel_name/chat_id/user_id/ │
# │                               text/msg_type/thread_ts/      │
# │                               topic_id/files/metadata/      │
# │                               account_id/created_at         │
# │ OutboundMessage(dataclass)    channel_name/chat_id/thread_id│
# │                               text/artifacts/is_final/...   │
# │ MessageBus                   inbound 队列 + outbound 订阅    │
# │   publish_inbound() → 入站入队                               │
# │   get_inbound()     → 出队（dispatcher 消费）                │
# │   subscribe_outbound()/unsubscribe_outbound()               │
# └──────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 对齐原版归属：InboundMessage 从 base.py 迁回 message_bus.py（原版就在这）；
#    base.py 只留 Channel ABC，re-export 保持旧 import 兼容。
# 2. 解耦「收消息 ↔ 跑 Agent ↔ 回发」：渠道 publish_inbound，dispatcher 消费；
#    dispatcher publish outbound，渠道经 (channel_name, account_id) 键控回调收。
# 3. account_id 键控：多账号同渠道（如主机器人 + 员工机器人同名 "wecom"）
#    各自拥有回调槽位，重启一个实例不覆盖兄弟实例（对齐原版注释语义）。
# 4. 裁剪：ResolvedAttachment 保留纯数据结构（对齐原版形状）；文件上传/日志
#    钩子（channel_io_log）不搬——M8+ 多渠道实装时按原版补。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出】
# ✅ InboundMessageType / InboundMessage / OutboundMessage / ResolvedAttachment /
#    MessageBus
# ----------------------------------------------------------------------------
# ⚠️ 【五、风险点】
# 1. 当前飞书（FeishuChannel）仍走内联路径（parse_inbound → 去重 → 回发），
#    未强制改走总线——M7 验收行为不变；M8+ 多渠道时在 serve 装配里接线总线。
# 2. 模块 import 零副作用：无第三方依赖（纯 asyncio/dataclasses）。
# ============================================================================

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class InboundMessageType(StrEnum):
    """从 IM 渠道到达的消息类型。"""

    CHAT = "chat"
    COMMAND = "command"


@dataclass
class InboundMessage:
    """从 IM 渠道到达、走向 agent dispatcher 的一条入站消息（对齐原版字段）。

    Attributes:
        channel_name: 来源渠道名（如 "feishu" / "wecom"）。
        chat_id: 平台侧会话/群 id。
        user_id: 平台侧用户 id。
        text: 消息文本。
        msg_type: 普通聊天 or 命令。
        thread_ts: 平台线程标识（threaded replies 用）。
        topic_id: 会话主题 id——同一 chat_id 下共享 topic_id 的消息复用同一
            EvoFlow thread；None 时只按 channel_name:chat_id 映射单线程。
        files: 附件列表（平台 dict）。
        metadata: 扩展字段。
        account_id: 实例标识（"" = 主机器人；"customer-service" = 员工机器人）。
            原样带到 OutboundMessage，总线按 (channel_name, account_id) 回路由。
        created_at: Unix 时间戳。
    """

    channel_name: str
    chat_id: str
    user_id: str
    text: str
    msg_type: InboundMessageType = InboundMessageType.CHAT
    thread_ts: str | None = None
    topic_id: str | None = None
    files: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    account_id: str = ""
    created_at: float = field(default_factory=time.time)


@dataclass
class ResolvedAttachment:
    """解析到宿主文件系统路径的附件（对齐原版形状；M7 无使用场景）。"""

    virtual_path: str
    actual_path: Path
    filename: str
    mime_type: str
    size: int
    is_image: bool


@dataclass
class OutboundMessage:
    """从 agent dispatcher 发回渠道的一条出站消息（对齐原版字段）。"""

    channel_name: str
    chat_id: str
    thread_id: str
    text: str
    artifacts: list[str] = field(default_factory=list)
    attachments: list[ResolvedAttachment] = field(default_factory=list)
    is_final: bool = True
    thread_ts: str | None = None
    topic_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    account_id: str = ""
    created_at: float = field(default_factory=time.time)


OutboundCallback = Callable[[OutboundMessage], Coroutine[Any, Any, None]]


class MessageBus:
    """异步 pub/sub 枢纽：解耦渠道与 agent dispatcher。

    渠道 publish_inbound 入队 → dispatcher get_inbound 消费；
    dispatcher 发布 OutboundMessage → 渠道经注册回调接收。
    """

    def __init__(self) -> None:
        self._inbound_queue: asyncio.Queue[InboundMessage] = asyncio.Queue()
        # (channel_name, account_id) → 回调：多账号同渠道各自占槽，不互相覆盖
        self._outbound_by_account: dict[tuple[str, str], OutboundCallback] = {}
        # 无键监听者（测试/debug tap）收所有出站消息
        self._outbound_listeners: list[OutboundCallback] = []

    # -- inbound ----------------------------------------------------------

    async def publish_inbound(self, msg: InboundMessage) -> None:
        """渠道入站 → 入队。"""
        await self._inbound_queue.put(msg)
        logger.info(
            "[Bus] inbound enqueued: channel=%s, chat_id=%s, type=%s, queue_size=%d",
            msg.channel_name,
            msg.chat_id,
            msg.msg_type.value,
            self._inbound_queue.qsize(),
        )

    async def get_inbound(self, timeout: float | None = None) -> InboundMessage:
        """阻塞取一条入站；timeout 内无消息抛 asyncio.TimeoutError。"""
        if timeout is None:
            return await self._inbound_queue.get()
        return await asyncio.wait_for(self._inbound_queue.get(), timeout)

    @property
    def inbound_queue(self) -> asyncio.Queue[InboundMessage]:
        return self._inbound_queue

    # -- outbound ---------------------------------------------------------

    def subscribe_outbound(
        self,
        callback: OutboundCallback,
        *,
        channel_name: str | None = None,
        account_id: str = "",
    ) -> None:
        """注册出站回调。

        带 channel_name → 键控 (channel_name, account_id) 槽位（多渠道实例各归其位）；
        不带 → 收所有出站（测试/debug tap）。
        """
        if channel_name:
            self._outbound_by_account[(channel_name, account_id)] = callback
            return
        self._outbound_listeners.append(callback)

    def unsubscribe_outbound(
        self,
        callback: OutboundCallback | None = None,
        *,
        channel_name: str | None = None,
        account_id: str = "",
    ) -> None:
        """移除键控回调或监听者。"""
        if channel_name:
            self._outbound_by_account.pop((channel_name, account_id), None)
            return
        if callback is not None and callback in self._outbound_listeners:
            self._outbound_listeners.remove(callback)

    async def publish_outbound(self, msg: OutboundMessage) -> None:
        """发布出站消息：先路由到 (channel_name, account_id) 槽位，再广播给监听者。"""
        cb = self._outbound_by_account.get((msg.channel_name, msg.account_id))
        if cb is not None:
            await cb(msg)
        for listener in list(self._outbound_listeners):
            await listener(msg)

    def is_registered(self, channel_name: str, account_id: str = "") -> bool:
        """是否已有该 (channel, account) 的出站槽位。"""
        return (channel_name, account_id) in self._outbound_by_account
