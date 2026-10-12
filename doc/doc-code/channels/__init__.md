# channels/__init__.py —— IM 渠道包入口

> **文件路径**: `backend/packages/harness/agentflow/channels/__init__.py`
> **目录位置**: channels → __init__.py
> **职责**: 渠道包统一导出，外部 `from agentflow.channels import FeishuChannel, handle_challenge, ...`

## 📋 基础信息

- **里程碑**: M7（IM 渠道：飞书先发）
- **子文件**: `base.py`（Channel ABC + InboundMessage）、`feishu.py`（飞书渠道）

## 🧩 模块结构图

```text
┌───────────────────────────────────────────────┐
│ channels/                                     │
│   base.py     Channel ABC + InboundMessage    │
│   feishu.py   飞书渠道（challenge/去重/跑Agent/回发）│
└───────────────────────────────────────────────┘
```

## 📤 对外导出

```python
from agentflow.channels import (
    Channel, InboundMessage,
    FeishuChannel, handle_challenge, parse_inbound, feishu_outbound_text,
)
```

## 💡 设计思想

- 包入口只做转发，**不在此处 `import lark_oapi`**——保持包导入轻量。lark SDK 仅在 `feishu.serve()` 内延迟加载，这样测试 `import agentflow.channels` 不依赖 lark 是否安装。

## 🎯 目标

- 给外部一个稳定的渠道 API 表面；后续新增企微/Slack 渠道时在这里追加导出。

## 📊 流程图

```text
外部模块 import agentflow.channels
│
▼
__init__ 转发 base.py / feishu.py 的公共符号   ← 顶层不碰 lark_oapi
│
▼
拿到 FeishuChannel / handle_challenge / ...
```

## ❓ Q&A

### 1. 为什么入口不直接 import lark_oapi？

**一句话**：测试和文档脚本 import 渠道包时不该强制要求 lark SDK 可用。把重依赖延迟到 `serve()` 里，模块导入即轻量、离线可测。

## ⚠️ 风险点

1. 勿在 `__init__.py` 顶层加 `import lark_oapi`——会让「离线 import 本包」也强依赖 SDK，破坏可测试性。
