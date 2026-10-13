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

## ❓ Q&A / 知识点

### 1. 为什么这里要单独定义 InboundMessage，不直接用平台 SDK 对象？

**一句话**：平台 SDK 对象是「平台耦合」的，飞书的 `event.event.message` 和企微的结构完全不同。折叠成统一 `InboundMessage` 后，「去重、跑 Agent、落库、回发」这套编排逻辑就能在各渠道间复用，而不是每个平台重写一遍。

### 2. `reply_to` 和 `thread_id` 是一回事吗？

**一句话**：不是。`reply_to` 是**平台侧**「要回复的那条消息 id」（飞书 `im.v1.message.reply` 的入参）；`thread_id` 是 **LangGraph 侧**恢复多轮上下文的维度。飞书渠道里 `thread_id = feishu:<chat_id>`，二者是两套映射。

## ⚠️ 风险点

1. `Channel.start/stop` 是抽象方法：子类不实现直接实例化报错（ABC 机制），勿删 `@abstractmethod`。
2. `InboundMessage.reply_to` 语义是「平台侧回复锚点」，勿误当 LangGraph `thread_id` 用。
