# ============================================================================
# AgentFlow · channels/__init__.py —— IM 渠道包入口（M7）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/app/channels/__init__.py
# 里程碑: M7（IM 渠道：飞书先发）
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌───────────────────────────────────────────────┐
# │ channels/                                     │
# │   base.py     Channel ABC + InboundMessage    │
# │   feishu.py   飞书渠道（challenge/去重/跑Agent/回发）│
# └───────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 📤 【四、对外导出】
# ✅ Channel / InboundMessage / FeishuChannel / handle_challenge /
#    parse_inbound / feishu_outbound_text
# ----------------------------------------------------------------------------
# ⚠️ 【五、风险点】
# 1. 不在此处 import lark_oapi——保持包导入轻量，lark 仅 serve() 内延迟加载
# ============================================================================

from __future__ import annotations

from app.channels.base import Channel, InboundMessage
from app.channels.feishu import (
    FeishuChannel,
    feishu_outbound_text,
    handle_challenge,
    parse_inbound,
)

__all__ = [
    "Channel",
    "FeishuChannel",
    "InboundMessage",
    "feishu_outbound_text",
    "handle_challenge",
    "parse_inbound",
]
