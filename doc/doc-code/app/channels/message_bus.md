# channels/message_bus.py — message_bus.py

> **文件路径**: `backend/app/channels/message_bus.py`
> **目录位置**: app/channels → message_bus.py
> **职责**: IM 消息总线——Inbound/OutboundMessage 数据契约 + MessageBus（inbound 队列 + outbound 订阅发布），解耦「收消息 ↔ 跑 Agent ↔ 回发」

## 📑 目录

- [📋 结构图 / 思维图](#📋-结构图--思维图)
- [📤 关键导出](#📤-关键导出)
- [💡 设计思想](#💡-设计思想)
- [🎯 实用场景](#🎯-实用场景)
- [🧩 顺序执行链](#🧩-顺序执行链)
- [🧩 代码解析](#🧩-代码解析)
- [❓ Q&A](#❓-qa)
- [⚠️ 风险点](#⚠️-风险点)

## 📋 结构图 / 思维图

```text
message_bus.py（对齐原版 295 行的最小骨架）
  InboundMessageType(StrEnum)    CHAT / COMMAND
  InboundMessage(dataclass)      channel_name/chat_id/user_id/text/msg_type/
                                 thread_ts/topic_id/files/metadata/account_id/created_at
  OutboundMessage(dataclass)     channel_name/chat_id/thread_id/text/artifacts/
                                 attachments/is_final/thread_ts/topic_id/metadata/account_id/created_at
  ResolvedAttachment(dataclass)  附件解析结果（纯数据结构，M7 无使用场景）
  MessageBus
    publish_inbound(msg)     → 入站入队（渠道 → dispatcher）
    get_inbound(timeout?)    → 出队消费
    subscribe_outbound(cb, channel_name?, account_id="")
                             → (channel, account) 键控槽位 / 无键监听者
    unsubscribe_outbound(cb?, channel_name?, account_id="")
    publish_outbound(msg)    → 槽位回调 + 监听者广播
    is_registered(channel, account) → 槽位存在性
```

## 📤 关键导出

**MessageBus** / **InboundMessage** / **OutboundMessage** / **InboundMessageType** / **ResolvedAttachment**（均经 `app.channels` 再导出）

## 💡 设计思想

1. **对齐原版归属（2026-10-18 补位）**：`InboundMessage` 定义从 base.py 迁回 message_bus.py（原版就在这）；base.py 只留 Channel ABC + re-export，旧 `from app.channels.base import InboundMessage` 路径不变。
2. **解耦三环节**：渠道 publish_inbound 入队 → dispatcher get_inbound 消费 → dispatcher publish_outbound → 渠道按槽位回调回发。「收/跑/发」三方互不直接持有对方。
3. **account_id 键控**：多账号同渠道（主机器人 + 员工机器人同名 "wecom"）各占 `(channel_name, account_id)` 槽位——重启一个实例只替换自己的槽，不覆盖兄弟实例（对齐原版注释语义）。
4. **裁剪**：`ResolvedAttachment` 保留纯数据结构对齐形状；文件上传/日志钩子（channel_io_log）不搬——M8.1 多渠道实装时按原版补。

## 🎯 实用场景

1. 接第 2 个 IM 平台（企微/Slack…）：多个渠道 publish_inbound 进同一总线，dispatcher 统一消费，回复按渠道路由回发
2. 测试/debug：`subscribe_outbound(tap)` 无键监听收所有出站，用于断言渠道行为
3. 多账号机器人：同一渠道多个实例，`account_id` 区分路由，重启互不干扰

## 🧩 顺序执行链

**入站方向（渠道 → dispatcher）**：

```text
渠道收到 IM 事件
   ▼  归一化为 InboundMessage（channel_name/chat_id/text/...）
   ▼  await bus.publish_inbound(msg)      ← 入队（inbound_queue）
   ▼  dispatcher await bus.get_inbound()  ← 出队消费（可带 timeout）
   ▼  跑 Agent → 产出 OutboundMessage
```

**出站方向（dispatcher → 渠道）**：

```text
dispatcher 构造 OutboundMessage（channel_name/chat_id/thread_id/text/account_id）
   ▼  await bus.publish_outbound(msg)
   ▼  查 (channel_name, account_id) 槽位回调   ← 有则调用（回发）
   ▼  广播给全部无键监听者（listeners）        ← 测试/debug tap
```

## 🧩 代码解析

### 数据契约（Inbound/OutboundMessage）

```python
@dataclass
class InboundMessage:
    channel_name: str          # 来源渠道名（"feishu"/"wecom"…）
    chat_id: str               # 平台会话/群 id
    user_id: str               # 平台用户 id
    text: str                  # 消息文本
    msg_type: InboundMessageType = InboundMessageType.CHAT
    thread_ts: str | None = None     # 平台线程标识
    topic_id: str | None = None      # 会话主题（共享则复用同一 EvoFlow thread）
    files: list[dict] = ...           # 附件（平台 dict）
    metadata: dict = ...              # 扩展字段
    account_id: str = ""              # 实例标识（"" = 主机器人）
    created_at: float = ...           # Unix 时间戳
```

**关键点**：

- **字段集严格对齐原版**：M7 早期自造的 `msg_id/reply_to` 字段已移除——那是飞书平台专用概念，现在归 feishu.py 自己的 `ParsedInbound`（平台层归一化），总线契约保持平台无关。
- **`topic_id` 语义**：同一 chat_id 下共享 topic_id 的消息复用同一 thread；None 时只按 `channel_name:chat_id` 映射单线程。
- **`account_id` 贯穿 Inbound→Outbound**：入站带什么实例 id，出站原样带回，总线据此把回复送回同一个实例。

### MessageBus 核心

```python
async def publish_inbound(self, msg: InboundMessage) -> None:
    await self._inbound_queue.put(msg)          # 入队即返回（异步队列）

async def get_inbound(self, timeout=None):
    if timeout is None:
        return await self._inbound_queue.get()
    return await asyncio.wait_for(self._inbound_queue.get(), timeout)

def subscribe_outbound(self, callback, *, channel_name=None, account_id=""):
    if channel_name:
        self._outbound_by_account[(channel_name, account_id)] = callback
        return
    self._outbound_listeners.append(callback)   # 无键监听：收所有出站
```

**关键点**：

- **`asyncio.Queue` 天然异步解耦**：publish 不阻塞（入队即返回），消费方可以阻塞在 get_inbound 上等消息——渠道线程与 dispatcher 线程无需握手。
- **`subscribe_outbound` 两模式**：带 channel_name 走键控槽位（生产回发），不带走监听列表（测试 tap）——两种模式共存，互不影响。
- **`publish_outbound` 先槽位后广播**：生产回发优先精确路由，监听者随后收同一份消息做观测，顺序稳定。

## ❓ Q&A

**Q: MessageBus 现在有用吗？feishu 不是还走内联路径？**
A: 代码已就位但**尚未接线**——当前 FeishuChannel 仍走 parse_inbound → 去重 → 回发内联路径（M7 验收行为不变）。MessageBus 是「架构位置先行」：M8.1 多渠道实装时渠道 publish_inbound → dispatcher 消费 → publish_outbound 回发，不用重构。

**Q: 为什么 InboundMessage 的 msg_id/reply_to 被移走了？**
A: 对齐原版字段集（原版 InboundMessage 没有这两个字段）。它们是飞书平台专用概念，保留在 feishu.py 的 `ParsedInbound`（平台层归一化输出）——总线契约保持平台无关，才能容纳企微/Slack 各自的消息结构。

**Q: account_id 有什么用？单渠道需要吗？**
A: 单渠道默认 ""（主机器人）够用。多账号场景（如"员工专属机器人"）同一渠道名有多个实例，回复必须回给"收到消息的那个实例"——按 (channel, account) 键控槽位保证这一点，重启一个实例不覆盖兄弟。

**Q: 为什么 publish_outbound 先发槽位再广播？**
A: 槽位是生产路由（回复必须到正确渠道实例），监听者是观测（测试/调试 tap）。先路由后广播保证生产语义优先且稳定，观测方总能拿到同一份消息。

## ⚠️ 风险点

1. **未接线**：总线代码存在但 feishu 未强制走它——多渠道前是"备而不用"，别误以为已生效（见 test_channel_bus_manager.py 契约验证的是总线自身）
2. `get_inbound` 无 timeout 会永久阻塞：生产用要配合 dispatcher 任务生命周期（asyncio.Task.cancel 或 timeout）
3. 键控槽位是**覆盖式**（dict 赋值）：同名 (channel, account) 重复注册会静默覆盖旧回调——启动装配要保证实例唯一
4. 纯内存队列：消息不持久化，进程重启丢队内消息（对齐原版；持久化属 store/数据库层）

> 页脚：2026-10-18 · M7 架构对齐补位 · 对齐 `evoflow/app/channels/message_bus.py`（最小骨架）
