# knowledge/__init__.py — __init__.py

> **文件路径**: `backend/packages/harness/agentflow/knowledge/__init__.py`
> **目录位置**: knowledge → __init__.py
> **职责**: knowledge 包入口（M3：分块 / 向量化 / 检索）

## 📋 结构图

```text
（无复杂调用图）

knowledge/
├── chunker.py                 文本分块（chunk_text）
├── service.py                  知识库总入口（KnowledgeService）
└── embedding/
    ├── base.py                 抽象基类 + 常量 + 异常
    └── registry.py             云端/本地 provider 选择 + 向量化公共 API
```

## 📤 关键导出

（无顶层导出，见结构图；符号从子模块直接 import，如 `from agentflow.knowledge.service import KnowledgeService`）

## 💡 设计思想

1. 只做包声明，不承载业务逻辑，也不做 re-export——外部按子模块路径精确 import（cli/main.py 即 `from agentflow.knowledge.service import KnowledgeService`）。

## 🎯 实用场景

1. 知识库装配场景：cli/main.py 在此包内组装 KnowledgeService（repo + embedding_cfg），再注入 knowledge 工具。
2. 建库/检索：chunker 切块 → registry 向量化 → service 编排，三者在包内闭环。

## ⚠️ 风险点

1. 勿在此放业务逻辑或 re-export（保持包入口纯净；外部按子模块 import）。

---
_2026-09-30 新建：M3 包入口索引。_
