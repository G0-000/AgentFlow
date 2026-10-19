# channels/base.py — IM 渠道抽象基类

> **文件路径**: `backend/app/channels/base.py`
> **目录位置**: channels → base.py
> **职责**: 定义所有 IM 渠道的抽象基类 `Channel`；`InboundMessage` 定义已迁至 `message_bus.py`（此处 re-export 保旧 import 兼容）（裁剪自 EvoFlow `app/channels/base.py`）

## 📋 基础信息

- **对标来源**: `evoflow/app/channels/base.py`（原版 181 行，带 MessageBus / 文件上传 / 流式卡片补丁 / 多账号）
- **里程碑**: M7（IM 渠道：飞书先发，验收点 5）
- **裁剪决策**: 原版靠 `MessageBus` 解耦「收消息 ↔ 跑 Agent ↔ 回发」，并支持文件上传、流式卡片补丁、多账号。M7 只做「单轮：收 → 跑 Agent → 回发」，故去掉 Bus / 上传 / 流式，只留 `Channel` ABC。
- **2026-10-18 归属对齐**: `InboundMessage` 定义迁回 `message_bus.py`（对齐原版归属），base.py 只留 `Channel` + re-export——旧 `from app.channels.base import InboundMessage` 路径不变。

## 🧩 模块结构图

```text
┌───────────────────────────────────────────────────────┐
│ Channel(ABC)                                          │
│   name: str = "channel"                              │
│   start() / stop()            ← 抽象生命周期         │
│                                                       │
│ InboundMessage（re-export）  ← 定义在 message_bus.py  │
│   归一化入站消息（channel_name/chat_id/user_id/text…）│
└───────────────────────────────────────────────────────┘
```

## 💡 设计思想

1. **归一化**：各 IM 平台事件结构不同（飞书 / 企微 / Slack…），统一折叠成 `InboundMessage`（定义见 `message_bus.py`），下游「跑 Agent → 回发」逻辑与具体平台解耦。
2. **最小抽象**：原版 `Channel` 还挂 `bus.send_file` / `_on_outbound` 等；M7 暂不需要，需要时再按本基类扩展（不一次性搬全原版）。
3. **re-export 兼容层**：迁移 InboundMessage 后保留旧 import 路径，新代码建议直接从 `app.channels.message_bus` 或 `app.channels` 包入口导入。

## 📤 对外导出

**类**
- `Channel`：IM 渠道抽象基类（抽象方法 `start` / `stop`）
- `InboundMessage`：re-export（自 `app.channels.message_bus`；字段集对齐原版：`channel_name/chat_id/user_id/text/msg_type/thread_ts/topic_id/files/metadata/account_id/created_at`）

## 🎯 目标

- 给后续接企微 / Slack 等渠道一个统一骨架；新增渠道只需实现 `start` / `stop` + 自己的事件解析与回发。
- 把「平台事件结构」隔离在各渠道子类内，业务编排（去重、跑 Agent、落库）尽量复用。
- MessageBus / ChannelManager 已按原版位置就位（message_bus.py / manager.py）——多渠道装配点存在，接第 2 个平台只填实现不重构。

## 📊 流程图（顺序执行链）

```text
外部 IM 平台发来一条消息
│
▼
子类把平台 SDK 事件折叠成 InboundMessage        ← 定义在 message_bus.py
│
▼
Channel 编排（去重 → AgentRunner → 回发）        ← 见 feishu.on_message（当前内联路径）
│
▼
回发层（飞书 im.v1.message.reply）              ← 平台专用字段在 ParsedInbound
```

## 🧩 代码解析（成块对照 base.py）

### 块 1：`InboundMessage` —— 已迁至 message_bus.py（re-export）

```python
from app.channels.message_bus import InboundMessage  # noqa: F401  (re-export)
```

**关键点**：

- **定义在 message_bus.py（对齐原版归属）**：InboundMessage 是「消息契约」而非「渠道抽象」，放总线文件更合理——原版就在 message_bus.py。
- **re-export 保兼容**：M7 早期代码/文档用 `from app.channels.base import InboundMessage`，re-export 让迁移零成本。
- **字段集已对齐原版**：M7 早期自造的 `channel/msg_id/reply_to` 移除——那是飞书平台专用概念，保留在 feishu.py 的 `ParsedInbound`（平台层归一化输出）；总线契约保持平台无关。

### 块 2：`Channel` —— 抽象基类与"契约即注释"

```python
class Channel(ABC):
    """所有 IM 渠道的抽象基类。

    职责（M7 裁剪版）：
        1. 接收外部平台消息 → 归一化为 InboundMessage；
        2. 去重 → 用 AgentRunner 跑 Agent；
        3. 把回复发回平台。
    """

    name: str = "channel"

    @abstractmethod
    def start(self) -> None:
        """开始监听外部平台消息（阻塞或起后台线程，按渠道实现）。"""

    @abstractmethod
    def stop(self) -> None:
        """优雅停止渠道。"""
```

**关键点**：

- **`ABC` + `@abstractmethod` 只有两个生命周期方法**：`start`（开始监听）/`stop`（优雅停止）。子类不实现这两个方法就无法实例化（`TypeError: Can't instantiate abstract class`）——**把"必须实现"的契约写进类型系统**。
- **`name: str = "channel"` 是类属性**：每个渠道子类覆盖（`feishu.py` 里 `name = "feishu"`），用于日志/注册表标识。
- **注释里写清"三职责"**：接收 → 归一化 → 去重+跑 Agent → 回发。M7 裁剪后 `Channel` 本身不提供编排方法（原版挂 `MessageBus`/`_on_outbound`），编排逻辑在 `feishu.on_message` 内聚——"先最小抽象，需要再扩展"是 M7 的刻意取舍。
- **`start` 是同步签名**：注释说明"阻塞或起后台线程，按渠道实现"——飞书用 WebSocket 长连接（`serve` 内 `start_ws`），企微可能用轮询，签名统一为同步启动。

## ❓ Q&A / 知识点

### 1. 为什么要有 InboundMessage 这层归一化，不直接用平台 SDK 对象？

**一句话**：平台 SDK 对象是「平台耦合」的，飞书的 `event.event.message` 和企微的结构完全不同。折叠成统一 `InboundMessage` 后，「去重、跑 Agent、落库、回发」这套编排逻辑就能在各渠道间复用，而不是每个平台重写一遍。

**展开**：如果直接用飞书 SDK 对象，那么 `on_message` 里的去重逻辑就得写 `event.event.message.message_id`；换企微就得改字段路径。`InboundMessage` 把"平台字段路径"收敛到 `parse_inbound` 一个函数里——**变点隔离**：接新平台只写新 `parse_inbound` + 新渠道类，编排逻辑零改动。

### 2. InboundMessage 的 `reply_to` 和 LangGraph 的 `thread_id` 是一回事吗？

**一句话**：不是。`reply_to`（飞书平台概念，现保留在 `ParsedInbound`）是**平台侧**「要回复的那条消息 id」（飞书 `im.v1.message.reply` 的入参）；`thread_id` 是 **LangGraph 侧**恢复多轮上下文的维度。飞书渠道里 `thread_id = feishu:<chat_id>`，二者是两套映射。

### 3. 为什么 `start/stop` 用抽象方法，而不是普通方法 + 文档约定？

**一句话**：抽象方法把"子类必须实现"写进类型系统——漏实现会**在实例化时**报错，而不是运行时才发现"start 是空实现"。这比文档约定可靠一个量级：IDE 也会在子类缺失方法时直接标红。

### 4. 为什么 InboundMessage 要从 base.py 迁到 message_bus.py？

**一句话**：对齐原版归属——原版 InboundMessage 就在 message_bus.py。`InboundMessage` 是「消息契约」不是「渠道抽象」，放总线文件让包内职责清晰：base.py = 渠道生命周期抽象，message_bus.py = 消息契约 + 总线。base.py 保留 re-export 让旧 import 路径不破。

### 5. 2026-10-18 补位后，接第 2 个平台（如企微）需要几步？

**一句话**：三步——① 新建 `wecom.py` 实现 `WecomChannel(Channel)`（parse_inbound + on_message + start/stop）；② 装配处 `ChannelManager.build({"feishu": ch1, "wecom": ch2}).start_all()`；③ 若需统一编排，把渠道接入 MessageBus（publish_inbound → dispatcher → publish_outbound）。前两步已有骨架，第三步是"接线"而非"造结构"。

## ⚠️ 风险点

1. `Channel.start/stop` 是抽象方法：子类不实现直接实例化报错（ABC 机制），勿删 `@abstractmethod`。
2. `InboundMessage` 定义在 message_bus.py：改字段要动 message_bus.py，base.py 只是 re-export 转发。
3. `metadata` 必须用 `default_factory=dict`，勿改成 `default={}`（可变默认值共享陷阱）。
4. `text` 的清洗（去 @/BOM/零宽字符）在解析层完成——编排层不要再做二次清洗，否则两处清洗逻辑漂移。
5. re-export 是兼容层：新代码优先从 `app.channels.message_bus` / `app.channels` 导入，避免依赖 re-export 路径。

> 页脚：2026-10-18 · M7 IM 渠道 · 对齐 `evoflow/app/channels/base.py`（裁剪 + InboundMessage 归属对齐）
