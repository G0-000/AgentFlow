# ============================================================================
# AgentFlow · tests/test_channel_feishu.py —— 飞书 IM 渠道测试（M7 验收点 5）
# 全部离线：mock lark SDK 事件对象（SimpleNamespace），不连网、不真调模型。
# 覆盖：challenge 校验 / 入站去重（id 窗口 + 内容 hash 窗口）/
#       事件解析（机器人过滤/楼中楼 reply_to）/ 收消息→Agent→回复管线 / 回复格式化。
# 对齐原版 test_feishu_inbound_dedup.py 的裁剪思路。
# ============================================================================
import json
import time
from types import SimpleNamespace as NS

from agentflow.persistence.bootstrap import init_db
from agentflow.persistence.session_repositories import SessionRepository

from app.channels.feishu import (
    FeishuChannel,
    _FeishuInboundDeduper,
    feishu_outbound_text,
    handle_challenge,
    parse_inbound,
)


# ----------------------------------------------------------------------------
# 测试辅助：构造一个假的 lark P2 im.message.receive_v1 事件对象
# ----------------------------------------------------------------------------
def make_event(
    *,
    chat_id: str = "oc_123",
    msg_id: str = "om_1",
    text: str = "你好",
    sender_type: str = "user",
    root_id: str | None = None,
    open_id: str = "ou_x",
) -> NS:
    """用 SimpleNamespace 模拟 lark SDK 事件对象（event.event.message / .sender）。"""
    message = NS(
        chat_id=chat_id,
        message_id=msg_id,
        root_id=root_id,
        content=json.dumps({"text": text}),
        chat_type="p2p",
    )
    sender = NS(sender_type=sender_type, sender_id=NS(open_id=open_id))
    return NS(event=NS(message=message, sender=sender))


# ----------------------------------------------------------------------------
# 1. 事件订阅 URL 校验（challenge 应答）
# ----------------------------------------------------------------------------
def test_handle_challenge_echo():
    body = {"type": "url_verification", "challenge": "abc-123", "token": "t"}
    assert handle_challenge(body) == {"challenge": "abc-123"}


def test_handle_challenge_ignores_normal_event():
    """普通消息回调不是 url_verification → 返回 None，交给消息分发。"""
    assert handle_challenge({"event": {"message": {}}}) is None
    assert handle_challenge({"type": "event_callback"}) is None


def test_handle_challenge_non_dict():
    assert handle_challenge("not-a-dict") is None  # type: ignore[arg-type]


# ----------------------------------------------------------------------------
# 2. 入站去重：msg_id 窗口
# ----------------------------------------------------------------------------
def test_deduper_msg_id_window_blocks_repeat():
    d = _FeishuInboundDeduper()
    # 首次登记 → 不重复
    assert d.is_duplicate(msg_id="om_1", chat_id="c1", text="你好") is False
    # 同一 msg_id 窗口内再来 → 重复
    assert d.is_duplicate(msg_id="om_1", chat_id="c1", text="你好") is True


def test_deduper_msg_id_window_expires():
    d = _FeishuInboundDeduper()
    assert d.is_duplicate(msg_id="om_1", chat_id="c1", text="你好") is False
    # 手动把登记时间拨到过去（超过 id_ttl=120s）→ 窗口失效
    d._by_msg_id["om_1"] = time.time() - 1000
    assert d.is_duplicate(msg_id="om_1", chat_id="c1", text="新内容") is False


# ----------------------------------------------------------------------------
# 3. 入站去重：内容 hash 窗口（同 chat + 归一化正文，即便 msg_id 不同）
# ----------------------------------------------------------------------------
def test_deduper_content_window_blocks_new_msgid_same_body():
    d = _FeishuInboundDeduper()
    assert d.is_duplicate(msg_id="m1", chat_id="c1", text="相同正文") is False
    # 新 msg_id，但同 chat + 相同归一化正文 → 内容窗口判重
    assert d.is_duplicate(msg_id="m2", chat_id="c1", text="相同正文") is True


def test_deduper_content_window_diff_chat_not_duplicate():
    d = _FeishuInboundDeduper()
    assert d.is_duplicate(msg_id="m1", chat_id="c1", text="相同正文") is False
    # 同正文但不同 chat → 不判重（别的用户正常消息）
    assert d.is_duplicate(msg_id="m3", chat_id="c2", text="相同正文") is False


def test_deduper_normalizes_whitespace_and_at_placeholder():
    """归一化折叠空白、去掉 @_user_N 占位后再算内容 hash。"""
    d = _FeishuInboundDeduper()
    assert d.is_duplicate(msg_id="m1", chat_id="c1", text="你好  世界") is False
    # 空白数量不同 + 带 @_user_1 占位 → 归一化后应判重
    assert d.is_duplicate(msg_id="m2", chat_id="c1", text="@_user_1 你好 世界") is True


# ----------------------------------------------------------------------------
# 4. 事件解析 parse_inbound
# ----------------------------------------------------------------------------
def test_parse_inbound_normal_text():
    p = parse_inbound(make_event(chat_id="oc_a", msg_id="om_9", text="你好"))
    assert p is not None
    assert p.chat_id == "oc_a"
    assert p.msg_id == "om_9"
    assert p.text == "你好"
    assert p.reply_to == "om_9"  # 非楼中楼 → reply_to = msg_id


def test_parse_inbound_ignores_bot_sender():
    """机器人自发/别的机器人消息 → None（不回复自己的 echo）。"""
    assert parse_inbound(make_event(sender_type="app")) is None
    assert parse_inbound(make_event(sender_type="bot")) is None


def test_parse_inbound_thread_reply_uses_root_id():
    """楼中楼消息：root_id≠msg_id → reply_to 必须用 root_id（飞书 230002 教训）。"""
    p = parse_inbound(
        make_event(msg_id="om_leaf", root_id="om_root", text="楼中楼回复")
    )
    assert p is not None
    assert p.reply_to == "om_root"


def test_parse_inbound_empty_text_returns_none():
    assert parse_inbound(make_event(text="   ")) is None


# ----------------------------------------------------------------------------
# 5. 收消息 → Agent → 回复 管线（fake runner，不真调模型）
# ----------------------------------------------------------------------------
def test_on_message_runs_agent_and_sends_reply():
    sent: list[tuple[str, str, str]] = []
    runner_calls: list[tuple[str, str]] = []

    def runner(thread_id: str, text: str) -> str:
        runner_calls.append((thread_id, text))
        return f"echo:{text}"

    repo = SessionRepository(init_db(":memory:"))
    ch = FeishuChannel(
        agent_runner=runner,
        sender=lambda cid, rid, txt: sent.append((cid, rid, txt)),
        session_repo=repo,
    )

    ch.on_message(make_event(chat_id="oc_a", msg_id="om_1", text="你好"))

    # Agent 收到的 thread_id = chat_id 稳定映射
    assert runner_calls == [("feishu:oc_a", "你好")]
    # 回复经 sender 发出
    assert sent == [("oc_a", "om_1", "echo:你好")]
    # 会话与消息落库
    assert repo.get("feishu:oc_a") is not None
    msgs = repo.list_messages("feishu:oc_a")
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[0]["content"] == "你好"
    assert msgs[1]["content"] == "echo:你好"


def test_on_message_dedups_repeated_event():
    """同一事件投递两次 → Agent 只跑一次（去重在管线内生效）。"""
    runner_calls: list[str] = []

    def runner(thread_id: str, text: str) -> str:
        runner_calls.append(text)
        return "ok"

    ch = FeishuChannel(
        agent_runner=runner,
        sender=lambda *a: None,
    )
    ev = make_event(msg_id="om_dup", text="重复消息")
    ch.on_message(ev)
    ch.on_message(ev)  # 重投 → 应被去重吞掉
    assert runner_calls == ["重复消息"]


def test_on_message_agent_failure_fallback_reply():
    """Agent 抛异常 → 回发友好兜底文案，不崩回调线程。"""
    sent: list[tuple] = []

    def bad_runner(thread_id: str, text: str) -> str:
        raise RuntimeError("boom")

    ch = FeishuChannel(agent_runner=bad_runner, sender=lambda *a: sent.append(a))
    ch.on_message(make_event(msg_id="om_1"))
    assert sent and sent[0][2] == "(Agent 调用失败，请稍后再试)"


def test_on_message_sender_failure_does_not_crash():
    """回发失败只记日志，不抛到 lark 回调线程。"""

    def exploding_sender(*a):
        raise RuntimeError("network down")

    ch = FeishuChannel(agent_runner=lambda t, x: "ok", sender=exploding_sender)
    ch.on_message(make_event(msg_id="om_1"))  # 不应抛异常


def test_thread_id_mapping_stable():
    assert FeishuChannel.thread_id_for("oc_abc") == "feishu:oc_abc"


# ----------------------------------------------------------------------------
# 6. 回复文本格式化
# ----------------------------------------------------------------------------
def test_outbound_text_plain_passthrough():
    assert feishu_outbound_text("普通回复内容") == "普通回复内容"


def test_outbound_text_clarification_json_to_markdown():
    clar = json.dumps({"question": "选哪个方案？", "options": ["A", "B"]})
    out = feishu_outbound_text(clar)
    assert "需要您确认" in out
    assert "选哪个方案？" in out
    assert "A" in out and "B" in out


def test_outbound_text_non_clarification_json_unchanged():
    """不含澄清特征键的 JSON 原样返回（不误改写）。"""
    raw = '{"foo": 1, "bar": "x"}'
    assert feishu_outbound_text(raw) == raw
