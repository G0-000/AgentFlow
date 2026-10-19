# ============================================================================
# AgentFlow · channels/__init__.py —— IM 渠道包入口（M7）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/app/channels/__init__.py
# 里程碑: M7（IM 渠道：飞书先发；2026-10-18 对齐原版导出面，补 MessageBus/Manager）
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌───────────────────────────────────────────────────────────┐
# │ channels/                                                 │
# │   base.py        Channel ABC（+ InboundMessage re-export） │
# │   message_bus.py MessageBus：Inbound/Outbound + 队列/订阅   │
# │   manager.py     ChannelManager：渠道注册 + 入站路由       │
# │   feishu.py      飞书渠道（challenge/去重/跑Agent/回发）    │
# └───────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 📤 【四、对外导出】
# ✅ Channel / InboundMessage / OutboundMessage / MessageBus / ChannelManager /
#    FeishuChannel / handle_challenge / parse_inbound / feishu_outbound_text
# ----------------------------------------------------------------------------
# ⚠️ 【五、风险点】
# 1. 不在此处 import lark_oapi——保持包导入轻量，lark 仅 serve() 内延迟加载
# 2. InboundMessage 现定义于 message_bus.py（对齐原版归属）；base.py re-export，
#    旧 import 路径（from app.channels.base import InboundMessage）仍可用
# ============================================================================

from __future__ import annotations

from app.channels.base import Channel
from app.channels.feishu import (
    FeishuChannel,
    feishu_outbound_text,
    handle_challenge,
    parse_inbound,
)
from app.channels.manager import ChannelManager
from app.channels.message_bus import InboundMessage, MessageBus, OutboundMessage

__all__ = [
    "Channel",
    "ChannelManager",
    "FeishuChannel",
    "InboundMessage",
    "MessageBus",
    "OutboundMessage",
    "feishu_outbound_text",
    "handle_challenge",
    "parse_inbound",
]
