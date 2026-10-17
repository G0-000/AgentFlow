# channels/base.py — IM 渠道抽象基类

> **文件路径**: `backend/app/channels/base.py`
> **目录位置**: channels → base.py
> **职责**: 定义所有 IM 渠道的抽象基类 `Channel` + 归一化入站消息 `InboundMessage`（裁剪自 EvoFlow `app/channels/base.py`）

## 📋 基础信息

- **对标来源**: `evoflow/app/channels/base.py`（原版 181 行，带 MessageBus / 文件上传 / 流式卡片补丁 / 多账号）
- **里程碑**: M7（IM 渠道：飞书先发，验收点 5）
- **裁剪决策**: 原版靠 `MessageBus` 解耦「收消息 ↔ 跑 Agent ↔ 回发」，并支持文件上传、流式卡片补丁、多账号。M7 只做「单轮：收 → 跑 Agent → 回发」，故去掉 Bus / 上传 / 流式，只留 `Channel` ABC + `InboundMessage`。

## 🧩 模块结构图

```text
┌───────────────────────────────────────────────────────┐
│ InboundMessage(dataclass)  归一化入站消息              │
│   channel / chat_id / user_id / text / msg_id /       │
│   reply_to / metadata                                 │
│                                                       │
│ Channel(ABC)                                          │
│   name: str = "channel"                              │
│   start() / stop()            ← 抽象生命周期         │
└───────────────────────────────────────────────────────┘
```

## 💡 设计思想

1. **归一化**：各 IM 平台事件结构不同（飞书 / 企微 / Slack…），统一折叠成 `InboundMessage`，下游「跑 Agent → 回发」逻辑与具体平台解耦。
2. **最小抽象**：原版 `Channel` 还挂 `bus.send_file` / `_on_outbound` 等；M7 暂不需要，需要时再按本基类扩展（不一次性搬全原版）。

## 📤 对外导出

**类**
- `InboundMessage`：归一化入站消息 dataclass（`channel/chat_id/user_id/text/msg_id/reply_to/metadata`）
- `Channel`：IM 渠道抽象基类（抽象方法 `start` / `stop`）

## 🎯 目标

- 给后续接企微 / Slack 等渠道一个统一骨架；新增渠道只需实现 `start` / `stop` + 自己的事件解析与回发。
- 把「平台事件结构」隔离在各渠道子类内，业务编排（去重、跑 Agent、落库）尽量复用。

## 📊 流程图（顺序执行链）

```text
外部 IM 平台发来一条消息
│
▼
子类把平台 SDK 事件折叠成 InboundMessage        ← chat_id/user_id/text/msg_id/reply_to
│
▼
Channel 编排（去重 → AgentRunner → 回发）        ← 见 feishu.on_message
│
▼
reply_to 交回发层                                ← 飞书 im.v1.message.reply 用它
```

## 🧩 代码解析（成块对照 base.py）

### 块 1：`InboundMessage` —— 平台无关的入站消息契约

```python
@dataclass
class InboundMessage:
    """一条外部 IM 收到、已归一化的入站消息。"""

    channel: str    # 来源渠道名（如 "feishu"）
    chat_id: str    # 平台侧会话/群 id（用于映射 LangGraph thread_id）
    user_id: str    # 发送者 id（平台 open_id 等，审计/限流用）
    text: str       # 归一化后的纯文本（已去 @、去 BOM/零宽字符）
    msg_id: str = ""      # 平台侧消息 id（去重主键之一）
    reply_to: str = ""    # 回发时要 reply 的那条消息 id（楼中楼取 root_id，否则取 msg_id）
    metadata: dict[str, Any] = field(default_factory=dict)  # chat_type/root_id 等调试信息
```

**关键点**：

- **dataclass + 必填在前、可选在后**：`channel/chat_id/user_id/text` 是任何渠道都必须提供的"核心四元组"；`msg_id/reply_to/metadata` 有默认值，允许简单渠道（如测试桩）不填。
- **`text` 是"已归一化"的**：注释写明"已去 @、去 BOM/零宽字符"——**解析层**（各渠道子类的 `parse_inbound`）负责清洗，编排层拿到就是干净文本。清洗职责下沉到平台适配层。
- **`metadata: dict = field(default_factory=dict)`**：用 `default_factory` 而非 `default={}`——避免**可变默认值共享**（所有实例共享同一个 dict 的经典 Python 陷阱）。
- **字段注释即文档**：每个字段都标了"平台侧/映射用途"，防止后人把 `chat_id`（平台 id）和 `thread_id`（LangGraph id）混用。

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

### 1. 为什么这里要单独定义 InboundMessage，不直接用平台 SDK 对象？

**一句话**：平台 SDK 对象是「平台耦合」的，飞书的 `event.event.message` 和企微的结构完全不同。折叠成统一 `InboundMessage` 后，「去重、跑 Agent、落库、回发」这套编排逻辑就能在各渠道间复用，而不是每个平台重写一遍。

**展开**：如果直接用飞书 SDK 对象，那么 `on_message` 里的去重逻辑就得写 `event.event.message.message_id`；换企微就得改字段路径。`InboundMessage` 把"平台字段路径"收敛到 `parse_inbound` 一个函数里——**变点隔离**：接新平台只写新 `parse_inbound` + 新渠道类，编排逻辑零改动。

### 2. `reply_to` 和 `thread_id` 是一回事吗？

**一句话**：不是。`reply_to` 是**平台侧**「要回复的那条消息 id」（飞书 `im.v1.message.reply` 的入参）；`thread_id` 是 **LangGraph 侧**恢复多轮上下文的维度。飞书渠道里 `thread_id = feishu:<chat_id>`，二者是两套映射。

### 3. 为什么 `start/stop` 用抽象方法，而不是普通方法 + 文档约定？

**一句话**：抽象方法把"子类必须实现"写进类型系统——漏实现会**在实例化时**报错，而不是运行时才发现"start 是空实现"。这比文档约定可靠一个量级：IDE 也会在子类缺失方法时直接标红。

### 4. M7 的 Channel 比原版瘦这么多，后续要加功能怎么办？

**一句话**：按原版顺序加：先加 `MessageBus`（收/发解耦）→ 再加 `send_file`（文件上传）→ 再加流式卡片补丁。**每次只搬需要的**，不一次性搬全原版——这是"仿写学习"项目的节奏：每个里程碑只做验收点要求的。

## ⚠️ 风险点

1. `Channel.start/stop` 是抽象方法：子类不实现直接实例化报错（ABC 机制），勿删 `@abstractmethod`。
2. `InboundMessage.reply_to` 语义是「平台侧回复锚点」，勿误当 LangGraph `thread_id` 用。
3. `metadata` 必须用 `default_factory=dict`，勿改成 `default={}`（可变默认值共享陷阱）。
4. `text` 的清洗（去 @/BOM/零宽字符）在解析层完成——编排层不要再做二次清洗，否则两处清洗逻辑漂移。

> 页脚：2026-10-13 · M7 IM 渠道 · 对齐 `evoflow/app/channels/base.py`（裁剪）
