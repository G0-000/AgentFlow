# ============================================================================
# AgentFlow · tests/test_channel_bus_manager.py —— MessageBus + ChannelManager 契约
# ============================================================================
# 对标: evoflow 原版 message_bus/manager 语义（M7 架构对齐补位的最小契约）
# 覆盖:
#   1) MessageBus inbound：publish → get 队列循环 + timeout
#   2) MessageBus outbound：subscribe 键控回调 + 无键监听广播 + unsubscribe
#   3) ChannelManager：register/get/registered/route_inbound 路由 + 未注册告警
#   4) ChannelManager.build 批量装载 + start_all/stop_all 不炸
# ============================================================================

from __future__ import annotations

import asyncio

import pytest

from app.channels.manager import ChannelManager
from app.channels.message_bus import (
    InboundMessage,
    InboundMessageType,
    MessageBus,
    OutboundMessage,
)

# ---------------------------------------------------------------------------
# MessageBus · inbound
# ---------------------------------------------------------------------------


def test_inbound_publish_get_roundtrip() -> None:
    """publish_inbound → get_inbound 回到同一消息（队列 FIFO）。"""

    async def scenario() -> None:
        bus = MessageBus()
        msg = InboundMessage(
            channel_name="feishu",
            chat_id="oc_1",
            user_id="u_1",
            text="你好",
            msg_type=InboundMessageType.CHAT,
        )
        await bus.publish_inbound(msg)
        got = await bus.get_inbound()
        assert got is msg
        assert got.channel_name == "feishu"
        assert got.text == "你好"

    asyncio.run(scenario())


def test_inbound_get_timeout_raises() -> None:
    """空队列 get_inbound(timeout=0.01) 抛 asyncio.TimeoutError。"""

    async def scenario() -> None:
        bus = MessageBus()
        with pytest.raises(asyncio.TimeoutError):
            await bus.get_inbound(timeout=0.01)

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# MessageBus · outbound
# ---------------------------------------------------------------------------


def test_outbound_subscribe_keyed_by_channel_account() -> None:
    """(channel, account) 键控回调：同渠道不同账号各归其位，互不覆盖。"""

    async def scenario() -> None:
        bus = MessageBus()
        received: list[str] = []

        async def primary_cb(msg: OutboundMessage) -> None:
            received.append(f"primary:{msg.chat_id}")

        async def service_cb(msg: OutboundMessage) -> None:
            received.append(f"service:{msg.chat_id}")

        bus.subscribe_outbound(primary_cb, channel_name="wecom", account_id="")
        bus.subscribe_outbound(service_cb, channel_name="wecom", account_id="cs")
        # 主账号槽位被覆盖
        bus.subscribe_outbound(primary_cb, channel_name="wecom", account_id="")

        await bus.publish_outbound(
            OutboundMessage(
                channel_name="wecom", chat_id="c1", thread_id="t1", text="a"
            )
        )
        await bus.publish_outbound(
            OutboundMessage(
                channel_name="wecom",
                chat_id="c2",
                thread_id="t2",
                text="b",
                account_id="cs",
            )
        )
        assert received == ["primary:c1", "service:c2"]

    asyncio.run(scenario())


def test_outbound_listener_receives_all() -> None:
    """无键监听者收所有出站消息。"""

    async def scenario() -> None:
        bus = MessageBus()
        seen: list[str] = []

        async def tap(msg: OutboundMessage) -> None:
            seen.append(msg.chat_id)

        bus.subscribe_outbound(tap)
        await bus.publish_outbound(
            OutboundMessage(channel_name="feishu", chat_id="c1", thread_id="t", text="x")
        )
        await bus.publish_outbound(
            OutboundMessage(channel_name="slack", chat_id="c2", thread_id="t", text="y")
        )
        assert seen == ["c1", "c2"]

        # unsubscribe 后不再收到
        bus.unsubscribe_outbound(tap)
        await bus.publish_outbound(
            OutboundMessage(channel_name="feishu", chat_id="c3", thread_id="t", text="z")
        )
        assert seen == ["c1", "c2"]

    asyncio.run(scenario())


def test_is_registered_flags_keyed_slots() -> None:
    """is_registered 只认 (channel, account) 精确槽位。"""

    async def scenario() -> None:
        bus = MessageBus()

        async def cb(msg: OutboundMessage) -> None:
            pass

        bus.subscribe_outbound(cb, channel_name="feishu", account_id="")
        assert bus.is_registered("feishu", "")
        assert not bus.is_registered("feishu", "cs")
        assert not bus.is_registered("slack", "")

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# ChannelManager
# ---------------------------------------------------------------------------


class _FakeChannel:
    """最小假渠道：记录 on_message 收到多少条入站。"""

    name = "fake"

    def __init__(self) -> None:
        self.received: list[InboundMessage] = []
        self.started = False
        self.stopped = False

    def on_message(self, msg: InboundMessage) -> None:
        self.received.append(msg)

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


def test_manager_register_route() -> None:
    """register/get/registered + route_inbound 按 channel_name 路由。"""
    mgr = ChannelManager()
    ch = _FakeChannel()
    mgr.register("feishu", ch)

    assert mgr.get("feishu") is ch
    assert mgr.registered() == ["feishu"]

    routed = mgr.route_inbound(
        InboundMessage(channel_name="feishu", chat_id="oc", user_id="u", text="hi")
    )
    assert routed is True
    assert len(ch.received) == 1
    assert ch.received[0].text == "hi"


def test_manager_route_unregistered_returns_false() -> None:
    """未注册渠道路由 → False（仅告警，不炸）。"""
    mgr = ChannelManager()
    routed = mgr.route_inbound(
        InboundMessage(channel_name="slack", chat_id="c", user_id="u", text="hi")
    )
    assert routed is False


def test_manager_build_start_stop() -> None:
    """build 批量装载 + start_all/stop_all 全渠道启停。"""
    a, b = _FakeChannel(), _FakeChannel()
    mgr = ChannelManager.build({"feishu": a, "wecom": b})

    mgr.start_all()
    assert a.started and b.started

    mgr.stop_all()
    assert a.stopped and b.stopped

    mgr.unregister("feishu")
    assert mgr.get("feishu") is None
    assert mgr.registered() == ["wecom"]
