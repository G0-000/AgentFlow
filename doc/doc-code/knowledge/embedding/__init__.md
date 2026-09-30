# knowledge/embedding/__init__.py — __init__.py

> **文件路径**: `backend/packages/harness/agentflow/knowledge/embedding/__init__.py`
> **目录位置**: knowledge → embedding → __init__.py
> **职责**: knowledge.embedding 包入口（M3：向量模型云端/本地注册）

## 📋 结构图

```text
（无复杂调用图）

knowledge/embedding/
├── base.py        抽象基类 EmbeddingProvider + 常量 + 异常
└── registry.py    Cloud/Local provider 实现 + get_embedding(s) + 维度探测
```

## 📤 关键导出

（无顶层导出，见结构图；符号从子模块直接 import，如 service.py 用 `from agentflow.knowledge.embedding.registry import get_embedding, get_embeddings`）

## 💡 设计思想

1. 只做包声明，不 re-export——base 定义接口、registry 提供实现与选择，外部精确从 registry import 公共 API。

## 🎯 实用场景

1. 向量化场景：service.py 建库用 `get_embeddings`、查询用 `get_embedding`，均从本包 registry 取。
2. 云端/本地切换：改 config.yaml 的 embedding 段即切换，代码零改动（判定在 registry._is_local_config）。

## ⚠️ 风险点

1. 勿在此放业务逻辑或 re-export（保持包入口纯净）。

---
_2026-09-30 新建：M3 包入口索引。_
