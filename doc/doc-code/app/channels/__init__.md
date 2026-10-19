# channels/__init__.py —— IM 渠道包入口

> **文件路径**: `backend/app/channels/__init__.py`
> **目录位置**: channels → __init__.py
> **职责**: 渠道包统一导出，外部 `from app.channels import Channel, InboundMessage, MessageBus, ChannelManager, FeishuChannel, ...`

## 📋 基础信息

- **里程碑**: M7（IM 渠道：飞书先发；2026-10-18 对齐原版导出面）
- **子文件**: `base.py`（Channel ABC + InboundMessage re-export）、`message_bus.py`（消息契约 + MessageBus）、`manager.py`（ChannelManager 注册 + 路由）、`feishu.py`（飞书渠道）

## 🧩 模块结构图

```text
┌───────────────────────────────────────────────────────────┐
│ channels/                                                 │
│   base.py        Channel ABC（+ InboundMessage re-export） │
│   message_bus.py MessageBus：Inbound/Outbound + 队列/订阅   │
│   manager.py     ChannelManager：渠道注册 + 入站路由       │
│   feishu.py      飞书渠道（challenge/去重/跑Agent/回发）    │
└───────────────────────────────────────────────────────────┘
```

## 📤 对外导出

```python
from app.channels import (
    Channel, InboundMessage, OutboundMessage, MessageBus, ChannelManager,
    FeishuChannel, handle_challenge, parse_inbound, feishu_outbound_text,
)
```

## 💡 设计思想

- 包入口只做转发，**不在此处 `import lark_oapi`**——保持包导入轻量。lark SDK 仅在 `feishu.serve()` 内延迟加载，这样测试 `import app.channels` 不依赖 lark 是否安装。
- **导出面对齐原版**：原版 `channels/__init__.py` 导出 `Channel/InboundMessage/MessageBus/OutboundMessage/FeishuChannel` 等——AgentFlow 对齐该面并加 `ChannelManager`。

## 🎯 目标

- 给外部一个稳定的渠道 API 表面；后续新增企微/Slack 渠道时在这里追加导出（WecomChannel…）。

## 📊 流程图

```text
外部模块 import app.channels
│
▼
__init__ 转发 base/message_bus/manager/feishu 的公共符号   ← 顶层不碰 lark_oapi
│
▼
拿到 Channel / MessageBus / ChannelManager / FeishuChannel / ...
```

## ❓ Q&A

### 1. 为什么入口不直接 import lark_oapi？

**一句话**：测试和文档脚本 import 渠道包时不该强制要求 lark SDK 可用。把重依赖延迟到 `serve()` 里，模块导入即轻量、离线可测。

### 2. 为什么 InboundMessage 的 import 路径从 base 换到 message_bus？

**一句话**：2026-10-18 对齐原版归属——定义迁至 message_bus.py，包入口直接从 message_bus 导入（base.py 仍 re-export 保旧路径）。外部统一用 `from app.channels import InboundMessage`，不关心定义在哪个文件。

## ⚠️ 风险点

1. 勿在 `__init__.py` 顶层加 `import lark_oapi`——会让「离线 import 本包」也强依赖 SDK，破坏可测试性。
2. 导出面新增符号（MessageBus/ChannelManager/OutboundMessage）要同步更新 `__all__`，否则 `from app.channels import *` 拿不全。

> 页脚：2026-10-18 · M7 IM 渠道 · 对齐 `evoflow/app/channels/__init__.py`（导出面）
