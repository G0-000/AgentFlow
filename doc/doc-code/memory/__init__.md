# memory/__init__.py — __init__.py

> **文件路径**: `backend/packages/harness/agentflow/memory/__init__.py`
> **目录位置**: memory → __init__.py
> **职责**: memory 包入口

## 📋 结构图

```text
（无复杂调用图）
```

包内模块：

```text
agentflow.memory
├── facade.py       ← MemoryFacade（remember/recall/count，对外门面）
└── consolidate.py  ← extract_facts / consolidate_message（规则事实提取 + 落库）
```

## 📤 关键导出

（无顶层导出，见结构图）

## 💡 设计思想

1. 只做包声明，不承载业务逻辑——本文件仅一行注释 `# AgentFlow · memory 包（M3：记忆沉淀 + 召回）`，无任何 re-export。
2. 对外入口收敛在 `facade.MemoryFacade`（见 facade 文档），本 `__init__` 不把它再往外暴露一层。

## 🎯 实用场景

1. 记忆装配场景：`cli/main.py` 直接 `from agentflow.memory.facade import MemoryFacade` 取门面。
2. 沉淀/召回扩展：加能力改 `consolidate.py`（提取规则）或 `facade.py`（门面动作），不动包入口。

## ⚠️ 风险点

1. 勿在此放业务逻辑（保持包入口纯净）
2. 上游 import 走子模块（`from agentflow.memory.facade import ...`），勿假设本包 re-export 了符号

---
_2026-09-30 新建：M3 包入口索引。_
