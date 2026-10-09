# persistence/__init__.py — __init__.py

> **文件路径**: `backend/packages/harness/agentflow/persistence/__init__.py`
> **目录位置**: persistence → __init__.py
> **职责**: 业务数据持久化域包入口（checkpoint 与 trace 库另有存储组件）

## 📋 结构图

```text
（无复杂调用图）
```

## 📤 关键导出

（无顶层导出，见结构图）

## 💡 设计思想

1. 只做统一导出/包声明，不承载业务逻辑。

## 🎯 实用场景

1. 数据落库与恢复场景：重启进程后会话/消息仍在
2. 会话隔离场景：多个 thread_id 互不干扰
3. 数据库迁移场景：改 schema.py 后重跑 bootstrap 幂等建表

## ⚠️ 风险点

1. 勿在此放业务逻辑（保持包入口纯净）

---
_自动生成于 doc-code 规范落地（2026-09-28）。来源：__init__.py 头部注释 + 顶层符号。_
