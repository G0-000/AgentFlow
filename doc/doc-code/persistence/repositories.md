# persistence/repositories.py — repositories.py

> **文件路径**: `backend/packages/harness/agentflow/persistence/repositories.py`
> **目录位置**: persistence → repositories.py
> **职责**: Repository 基类

## 📋 结构图

```text
┌──────────────────────────────────────────────┐
│ BaseRepository（抽象基类）                    │
│   └─ 约束子类实现 4 个方法:                   │
│      table_name / create / get / delete      │
│   _execute(...) 统一执行 SQL + commit        │
│      （所有写操作都 commit，读操作不 commit） │
│   _fetch_one / _fetch_all 统一查询           │
│                                              │
│ 使用方: SessionRepository（session_          │
│         repositories.py）                    │
└──────────────────────────────────────────────┘
```

## 📤 关键导出

**类**

- `BaseRepository`

## 💡 设计思想

1. 基类收拢"执行 SQL + commit + 查询"样板，子类只写业务 SQL。
2. 写操作统一 commit：漏 commit 是 SQLite 最常见 bug，集中处理。

## 🎯 实用场景

1. 检查点/业务表 SQL 的底层封装（原版分层思想）

## ⚠️ 风险点

1. 抽象方法未实现时子类实例化报错（ABC 机制），勿删 abstractmethod
2. _execute 默认 commit；只读操作别用它（避免无谓写）

---
_自动生成于 doc-code 规范落地（2026-09-28）。来源：repositories.py 头部注释 + 顶层符号。_
