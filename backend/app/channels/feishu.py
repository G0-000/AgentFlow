# ============================================================================
# AgentFlow · channels/feishu.py —— 飞书 IM 渠道（裁剪自 EvoFlow feishu.py）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/app/channels/feishu.py
# 对标来源: evoflow/app/channels/feishu.py（原版 3232 行）+
#           feishu_message_format.py（发消息文本格式化）
# 里程碑: M7（验收点 5：飞书发消息给机器人 → 收到 Agent 回复）
#   裁剪决策: 原版是「WebSocket 长连接 + 事件回调 + MessageBus + 流式卡片补丁 +
#   审批/评审卡片 + 多账号 + 反应表情」的大集成。M7 只搬核心链路：
#     事件订阅 challenge 校验 → 入站解析 → 去重(msg_id 窗口 + 内容 hash 窗口) →
#     chat_id↔thread_id 映射 → 跑 Agent(可注入 runner) → 回复文本格式化 → 回发。
#   长连接用 lark-oapi WebSocket（无需公网 IP）；同时提供 handle_challenge 兼容
#   「事件订阅（Webhook 回调）」模式的 URL 校验。
#   合规: 仅用授权的飞书自建应用凭证，遵守飞书开放平台协议。
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────────────────┐
# │ _FeishuInboundDeduper   两级去重（msg_id 窗口 + 内容 hash 窗口）│
# │ handle_challenge(body)  事件订阅 URL 校验 → {"challenge": ...} │
# │ parse_inbound(event)    lark 事件对象 → ParsedInbound | None  │
# │ feishu_outbound_text(t) 回复文本格式化（澄清 JSON→Markdown）   │
# │                                                                │
# │ FeishuChannel(Channel)                                        │
# │   on_message(event)      ← lark P2 回调入口（收→去重→跑→回发）│
# │   thread_id_for(chat_id)  chat_id ↔ LangGraph thread_id 映射   │
# │   start()/stop()          生命周期（生产用 serve()）           │
# │                                                                │
# │ serve(app_id, app_secret)  渠道独立运行入口（装配 Agent + WS）  │
# └────────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 依赖注入解耦测试: agent_runner / sender / session_repo 全部注入——
#    生产由 serve() 装配真实 make_lead_agent + lark 回发客户端；
#    单测注入 fake runner + 列表式 sender，全程离线、不真调模型。
# 2. 延迟 import lark_oapi: 模块顶层不 import SDK，测试 import 本模块不依赖 lark；
#    serve()/start_ws 内才 import（与原版 start() 内 import 一致）。
# 3. 去重两级窗口: ① msg_id 在 id_ttl(120s) 内只处理一次（防 WS 重连重投）；
#    ② 同 chat + 归一化正文在 content_ttl(20s) 内只处理一次（兜住带新 msg_id
#       的罕见重投）。对齐原版 _FeishuInboundDeduper。
# 4. chat_id ↔ thread_id: 同一飞书会话稳定映射成 feishu:<chat_id> 这一个
#    LangGraph thread，checkpointer 据此恢复多轮上下文。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. FeishuChannel: 飞书渠道（on_message 回调 + serve 装配）
# 2. handle_challenge: 事件订阅 URL 校验（challenge 应答）
# 3. parse_inbound: lark 事件 → ParsedInbound
# 4. feishu_outbound_text: 回复文本格式化
# 🔒 内部私有函数
# 1. _FeishuInboundDeduper: 入站去重（msg_id/内容两级窗口）
# 2. _extract_text / _is_bot_sender / _get: 事件解析辅助
# 3. ParsedInbound: 解析结果 dataclass
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. lark 事件对象属性路径(event.event.message.*)勿写死成 dict——测试用
#    SimpleNamespace、真实 SDK 用对象，_get 同时兼容 getattr/dict。
# 2. sender 抛错只记日志不崩进程（lark 回调线程不能因单次失败退出）。
# 3. reply_to: 楼中楼消息必须用 root_id 回复（原版实测 230002 错误教训）。
# 4. 去重窗口内正常「用户连发两条相同消息」也会被吞——这是刻意取舍，
#    20s 窗口短，可接受；不要把 content_ttl 调大。
# ============================================================================

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.channels.base import Channel

logger = logging.getLogger(__name__)

# 去重窗口（对齐原版 _INBOUND_DEDUP_TTL_SECONDS / _INBOUND_CONTENT_DEDUP_TTL_SECONDS）
_INBOUND_ID_TTL = 120.0
_INBOUND_CONTENT_TTL = 20.0

# 回复空内容兜底（飞书不允许空文本消息）
_EMPTY_REPLY = "（空回复）"

# AgentRunner: (thread_id, 用户文本) -> 助手回复文本
AgentRunner = Callable[[str, str], str]
# ReplySender: (chat_id, reply_to_message_id, text) -> None
ReplySender = Callable[[str, str, str], None]


# ----------------------------------------------------------------------------
# 入站去重（对齐原版 _FeishuInboundDeduper）
# ----------------------------------------------------------------------------
class _FeishuInboundDeduper:
    """丢弃飞书 WebSocket 重连重投 / 同一消息的重复投递。

    两级窗口：
        1. msg_id 窗口：同一 message_id 在 id_ttl 内只处理一次；
        2. 内容 hash 窗口：同一 chat + 归一化正文 在 content_ttl 内只处理一次
           （兜住极少数带着新 message_id 重投的消息）。
    """

    def __init__(
        self,
        *,
        id_ttl: float = _INBOUND_ID_TTL,
        content_ttl: float = _INBOUND_CONTENT_TTL,
    ) -> None:
        self._id_ttl = id_ttl
        self._content_ttl = content_ttl
        self._by_msg_id: dict[str, float] = {}
        self._by_content: dict[str, float] = {}

    @staticmethod
    def _cleanup(store: dict[str, float], now: float, ttl: float) -> None:
        cutoff = now - ttl
        for key in [k for k, ts in store.items() if ts < cutoff]:
            store.pop(key, None)

    def is_duplicate(self, *, msg_id: str, chat_id: str, text: str) -> bool:
        """登记并判断本条入站是否重复（首次登记时返回 False）。"""
        now = time.time()
        self._cleanup(self._by_msg_id, now, self._id_ttl)
        self._cleanup(self._by_content, now, self._content_ttl)

        mid = str(msg_id or "").strip()
        if mid:
            if mid in self._by_msg_id:
                return True
            self._by_msg_id[mid] = now

        # 归一化正文：折叠空白、去掉 @_user_N 占位
        body = re.sub(r"\s+", " ", str(text or "").strip())
        body = re.sub(r"@_user_\d+\s*", "", body).strip()
        if body:
            content_key = (
                f"{chat_id}:{hashlib.sha1(body.encode('utf-8')).hexdigest()[:16]}"
            )
            if content_key in self._by_content:
                return True
            self._by_content[content_key] = now
        return False


# ----------------------------------------------------------------------------
# 事件订阅 URL 校验（challenge 应答）
# ----------------------------------------------------------------------------
def handle_challenge(body: dict[str, Any]) -> dict[str, Any] | None:
    """飞书事件订阅（Webhook 回调）的 URL 校验。

    飞书配置回调地址时会 POST 一个 {"type":"url_verification","challenge":"..."}，
    服务端必须原样回 {"challenge":"..."} 才算校验通过。
    非校验事件（普通消息回调）返回 None，交由消息分发处理。
    """
    if not isinstance(body, dict):
        return None
    if body.get("type") == "url_verification" and body.get("challenge"):
        return {"challenge": body["challenge"]}
    return None


# ----------------------------------------------------------------------------
# lark 事件对象解析（兼容 SDK 对象与 dict / 测试 SimpleNamespace）
# ----------------------------------------------------------------------------
def _get(obj: Any, path: tuple[str, ...], default: Any = None) -> Any:
    """按属性路径取值，每段既支持 getattr（SDK 对象）也支持 dict[key]。"""
    cur = obj
    for part in path:
        if cur is None:
            return default
        cur = cur.get(part) if isinstance(cur, dict) else getattr(cur, part, None)
    return cur if cur is not None else default


def _is_bot_sender(event: Any) -> bool:
    """入站发送者是机器人/应用？（忽略 echo 和别的机器人）。"""
    st = str(_get(event, ("event", "sender", "sender_type"), "") or "").strip().lower()
    return st in {"app", "bot", "application"}


def _extract_text(content_raw: Any) -> str:
    """从 message.content（JSON 字符串）解析出纯文本（含富文本 post）。"""
    if not content_raw:
        return ""
    if isinstance(content_raw, dict):
        content = content_raw
    else:
        try:
            content = json.loads(str(content_raw))
        except (json.JSONDecodeError, TypeError, ValueError):
            return str(content_raw).strip()
    if not isinstance(content, dict):
        return ""
    # 纯文本消息
    if "text" in content:
        return str(content["text"])
    # 富文本 post：content 是 [[{tag:text/at, text:...}, ...], ...]
    inner = content.get("content")
    if isinstance(inner, list):
        paragraphs: list[str] = []
        for para in inner:
            if isinstance(para, list):
                parts = [
                    el.get("text", "")
                    for el in para
                    if isinstance(el, dict)
                    and el.get("tag") in ("text", "at")
                    and el.get("text")
                ]
                if parts:
                    paragraphs.append(" ".join(parts))
        return "\n\n".join(paragraphs)
    return ""


@dataclass
class ParsedInbound:
    """解析后的归一化入站消息。"""

    chat_id: str
    msg_id: str
    text: str
    sender_id: str
    reply_to: str  # 楼中楼取 root_id，否则取 msg_id


def parse_inbound(event: Any) -> ParsedInbound | None:
    """从 lark P2 im.message.receive_v1 事件对象解析出归一化入站。

    机器人自发消息、缺 chat_id、空文本返回 None（不该回复）。
    """
    if _is_bot_sender(event):
        return None
    message = _get(event, ("event", "message"))
    chat_id = str(_get(message, ("chat_id",), "") or "")
    msg_id = str(_get(message, ("message_id",), "") or "")
    root_id = _get(message, ("root_id",))
    sender_id = str(_get(event, ("event", "sender", "sender_id", "open_id"), "") or "")
    text = _extract_text(_get(message, ("content",)))
    # 去 BOM / 零宽字符
    text = text.strip().strip("﻿\u200b‌‍")
    if not chat_id or not text:
        return None
    root_id = str(root_id or "")
    # 楼中楼：root_id 与 msg_id 不同时，回复锚点用 root_id（否则飞书报 230002）
    reply_to = root_id if (root_id and root_id != msg_id) else msg_id
    return ParsedInbound(
        chat_id=chat_id,
        msg_id=msg_id,
        text=text,
        sender_id=sender_id,
        reply_to=reply_to,
    )


# ----------------------------------------------------------------------------
# 回复文本格式化（裁剪自原版 feishu_message_format.feishu_outbound_text）
# ----------------------------------------------------------------------------
def feishu_outbound_text(text: str) -> str:
    """回发文本格式化：普通文本原样返回；若回复是一坨 ask_clarification
    原始 JSON，转成简短 Markdown（飞书里不希望用户看到裸 JSON）。

    裁剪自原版 feishu_message_format.py——只保留澄清 JSON→Markdown 这一条主干。
    """
    raw = text or ""
    s = raw.strip()
    if len(s) < 2 or s[0] != "{":
        return raw
    try:
        obj = json.loads(s)
    except (json.JSONDecodeError, TypeError, ValueError):
        return raw
    if not isinstance(obj, dict):
        return raw
    # 启发式：长得像澄清 schema 才改写
    if not (set(obj) & {"question", "questions", "options", "title", "context"}):
        return raw

    lines = ["❔ **需要您确认**", ""]
    title = str(obj.get("title") or "").strip()
    if title:
        lines += [f"**{title}**", ""]
    question = str(obj.get("question") or "").strip()
    if question:
        lines += [question, ""]
    options = obj.get("options")
    if isinstance(options, list):
        for i, opt in enumerate(options, 1):
            if isinstance(opt, str):
                lab = opt
            elif isinstance(opt, dict):
                lab = str(opt.get("label") or opt.get("text") or "").strip()
            else:
                lab = ""
            if lab:
                lines.append(f"- {i}. {lab}")
    body = "\n".join(lines).strip()
    return body or raw


# ----------------------------------------------------------------------------
# 飞书渠道
# ----------------------------------------------------------------------------
def _default_sender(chat_id: str, reply_to: str, text: str) -> None:
    """未装配 sender 时的占位：生产由 serve() 注入真实 lark 回发。"""
    raise RuntimeError("飞书 sender 未装配：请通过 serve() 启动或注入 sender")


class FeishuChannel(Channel):
    """飞书 IM 渠道：收消息 → 去重 → 跑 Agent → 回发。

    生产用 serve() 装配真实 Agent + lark 客户端；测试可直接构造本类并注入
    fake agent_runner / 列表式 sender / 内存 SessionRepository。
    """

    name = "feishu"

    def __init__(
        self,
        *,
        agent_runner: AgentRunner,
        sender: ReplySender = _default_sender,
        session_repo: Any = None,
        dedup: _FeishuInboundDeduper | None = None,
    ) -> None:
        self.agent_runner = agent_runner
        self.sender = sender
        self.session_repo = session_repo
        self.dedup = dedup or _FeishuInboundDeduper()
        self._running = False

    @staticmethod
    def thread_id_for(chat_id: str) -> str:
        """chat_id ↔ LangGraph thread_id 稳定映射。

        同一飞书会话始终映射到 feishu:<chat_id> 这一个 thread，
        checkpointer 据此恢复多轮对话上下文。
        """
        return f"feishu:{chat_id}"

    def on_message(self, event: Any) -> None:
        """lark P2 im.message.receive_v1 回调入口（跑在 lark 线程，同步）。

        顺序：解析 → 去重 → 建/取会话 → 跑 Agent → 格式化 → 回发 → 落库。
        任一步失败只记日志，不让 lark 回调线程退出。
        """
        parsed = parse_inbound(event)
        if parsed is None:
            return

        if self.dedup.is_duplicate(
            msg_id=parsed.msg_id, chat_id=parsed.chat_id, text=parsed.text
        ):
            logger.info(
                "[Feishu] skip duplicate inbound: msg_id=%s chat_id=%s",
                parsed.msg_id,
                parsed.chat_id,
            )
            return

        thread_id = self.thread_id_for(parsed.chat_id)
        if self.session_repo is not None:
            self.session_repo.create(thread_id)
            self.session_repo.add_message(thread_id, "user", parsed.text)

        try:
            reply = self.agent_runner(thread_id, parsed.text)
        except Exception:
            logger.exception("[Feishu] agent run failed: chat=%s", parsed.chat_id)
            reply = "(Agent 调用失败，请稍后再试)"

        reply = feishu_outbound_text(reply or "")
        if not reply.strip():
            reply = _EMPTY_REPLY

        try:
            self.sender(parsed.chat_id, parsed.reply_to, reply)
        except Exception:
            logger.exception("[Feishu] send reply failed: chat=%s", parsed.chat_id)
            return

        if self.session_repo is not None:
            self.session_repo.add_message(thread_id, "assistant", reply)
            self.session_repo.touch(thread_id)

    def start(self) -> None:
        """生产长连接启动见 serve()。此处仅满足 Channel ABC。"""
        raise NotImplementedError(
            "飞书渠道请用 serve(app_id, app_secret) 启动 WebSocket"
        )

    def stop(self) -> None:
        """停止渠道。"""
        self._running = False


# ----------------------------------------------------------------------------
# 生产装配入口（渠道独立运行，不挂 gateway app）
# ----------------------------------------------------------------------------
def serve(*, app_id: str, app_secret: str) -> None:
    """渠道独立运行入口：装配 Agent + WebSocket 长连接，阻塞监听飞书消息。

    装配与 cli/main.py 同源（load_config / create_sqlite_checkpointer /
    create_chat_model / make_lead_agent / SessionRepository），裁剪掉工具、
    中间件、记忆/知识等 M2-M5 横切能力，只保留「跑对话」最小集。
    """
    # 延迟 import lark：模块顶层不依赖 SDK（测试 import 本文件不需 lark）
    import lark_oapi as lark
    from agentflow.agents.checkpointer.provider import create_sqlite_checkpointer
    from agentflow.agents.lead_agent.agent import make_lead_agent
    from agentflow.config.app_config import load_config
    from agentflow.config.paths import PROJECT_ROOT, default_db_path
    from agentflow.models.factory import create_chat_model
    from agentflow.persistence.bootstrap import init_db
    from agentflow.persistence.session_repositories import SessionRepository
    from langchain_core.messages import HumanMessage

    cfg = load_config(str(PROJECT_ROOT / "config.yaml"))
    db_path = default_db_path()
    init_db(db_path)
    checkpointer = create_sqlite_checkpointer(db_path)
    model = create_chat_model(cfg.models.chat)
    agent = make_lead_agent(
        model=model, checkpointer=checkpointer, tools=[], middlewares=[]
    )
    sessions = SessionRepository(db_path=db_path)

    def agent_runner(thread_id: str, text: str) -> str:
        resp = agent.invoke(
            {"messages": [HumanMessage(text)]},
            config={"configurable": {"thread_id": thread_id}},
        )
        msgs = (
            resp.get("messages")
            if isinstance(resp, dict)
            else getattr(resp, "messages", [])
        )
        return str(msgs[-1].content) if msgs else ""

    client = lark.Client.builder().app_id(app_id).app_secret(app_secret).build()

    def sender(chat_id: str, reply_to: str, text: str) -> None:
        request = (
            lark.im.v1.ReplyMessageRequest.builder()
            .message_id(reply_to)
            .request_body(
                lark.im.v1.ReplyMessageRequestBody.builder()
                .msg_type("text")
                .content(json.dumps({"text": text}))
                .build()
            )
            .build()
        )
        client.im.v1.message.reply(request)

    channel = FeishuChannel(
        agent_runner=agent_runner, sender=sender, session_repo=sessions
    )

    event_handler = (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(channel.on_message)
        .build()
    )
    ws_client = lark.ws.Client(
        app_id=app_id,
        app_secret=app_secret,
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO,
    )
    channel._running = True
    logger.info("[Feishu] 渠道已启动（WebSocket 长连接，等待消息…）")
    ws_client.start()  # 阻塞
