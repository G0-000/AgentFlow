# ============================================================================
# AgentFlow · channels/manager.py —— 渠道注册 + 入站路由（M7 架构对齐补位）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/app/channels/manager.py
# 对标来源: evoflow/app/channels/manager.py（2712 行：ChannelManager +
#   IM 快捷命令/会话索引/transcript/诊断等全家桶）
# 里程碑: M7（补位：2026-10-18 对齐原版架构——只留「注册 + 入站路由」最小核心）
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────┐
# │ ChannelManager                                │
# │   register(name, channel)   → 注册渠道实例      │
# │   unregister(name)          → 注销             │
# │   get(name)                 → 取渠道            │
# │   route_inbound(msg)        → 按 channel_name  │
# │                               路由到对应渠道    │
# │   start_all()/stop_all()    → 批量启停          │
# └────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 对齐原版位置：渠道注册表 + 入站路由由 manager 承担；M7 实际裁剪成内联
#    （feishu serve 直接跑 FeishuChannel），本文件补位后——多渠道时
#    「serve_all → ChannelManager.start_all」统一装配，不再各自启动。
# 2. 裁剪：原版 2712 行的 IM 快捷命令、会话索引、transcript 持久化、诊断
#    大部不在 M7 范围（纠偏 4 原最小 scope 即「注册 + 入站路由」）。
# 3. 入站路由语义：msg.channel_name → get(name) → channel.on_message/处理；
#    未注册渠道仅告警不抛出（单渠道误发不炸整进程）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出】
# ✅ ChannelManager
# ----------------------------------------------------------------------------
# ⚠️ 【五、风险点】
# 1. route_inbound 是同步分发（对齐 M7 渠道 on_message 同步回调）；
#    原版 manager 与 bus 是 async 协奏，M8+ 多渠道实装时再按原版异步化。
# 2. ChannelManager 不持有 MessageBus——总线由装配层传入渠道，保持最小耦合。
# ============================================================================

from __future__ import annotations

import logging

from app.channels.base import Channel
from app.channels.message_bus import InboundMessage

logger = logging.getLogger(__name__)


class ChannelManager:
    """渠道注册表 + 入站路由（最小版，对齐原版 ChannelManager 位置）。"""

    def __init__(self) -> None:
        self._channels: dict[str, Channel] = {}

    # -- 注册 ----------------------------------------------------------

    def register(self, name: str, channel: Channel) -> None:
        """注册渠道实例；同名重复注册以新覆盖旧（告警不抛出）。"""
        if name in self._channels:
            logger.warning("[Manager] channel %r re-registered (overwrite)", name)
        self._channels[name] = channel

    def unregister(self, name: str) -> None:
        """注销渠道。"""
        self._channels.pop(name, None)

    def get(self, name: str) -> Channel | None:
        """取已注册渠道。"""
        return self._channels.get(name)

    def registered(self) -> list[str]:
        """已注册渠道名列表。"""
        return list(self._channels)

    # -- 入站路由 --------------------------------------------------------

    def route_inbound(self, msg: InboundMessage) -> bool:
        """按 msg.channel_name 路由到对应渠道实例。

        Returns:
            True=已分发；False=无此渠道（仅告警）。
        """
        channel = self._channels.get(msg.channel_name)
        if channel is None:
            logger.warning("[Manager] no channel registered for %r", msg.channel_name)
            return False
        on_message = getattr(channel, "on_message", None)
        if on_message is None:
            logger.warning(
                "[Manager] channel %r has no on_message handler", msg.channel_name
            )
            return False
        on_message(msg)
        return True

    # -- 批量启停 --------------------------------------------------------

    def start_all(self) -> None:
        """启动全部渠道（多渠道统一装配入口）。"""
        for name, channel in self._channels.items():
            try:
                channel.start()
                logger.info("[Manager] channel %r started", name)
            except Exception:
                logger.exception("[Manager] channel %r start failed", name)

    def stop_all(self) -> None:
        """停止全部渠道。"""
        for name, channel in self._channels.items():
            try:
                channel.stop()
            except Exception:
                logger.exception("[Manager] channel %r stop failed", name)

    # -- 便捷：单渠道装载 ----------------------------------------------------

    @staticmethod
    def build(channels: dict[str, Channel]) -> ChannelManager:
        """从 {name: channel} 批量注册（装配层一行建好注册表）。"""
        mgr = ChannelManager()
        for name, channel in channels.items():
            mgr.register(name, channel)
        return mgr
