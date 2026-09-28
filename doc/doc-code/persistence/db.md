# persistence/db.py — db.py

> **文件路径**: `backend/packages/harness/agentflow/persistence/db.py`
> **目录位置**: persistence → db.py
> **职责**: SQLite 连接管理

## 📋 结构图

```text
┌──────────────────────────────────────────────┐
│ connect(db_path) → sqlite3.Connection        │
│   ① 自动创建父目录（mkdir parents=True）      │
│   ② row_factory = Row（行可按列名取值）       │
│   ③ PRAGMA journal_mode=WAL（读写不互斥）     │
│   ④ PRAGMA foreign_keys=ON（外键约束生效）    │
└──────────────────────────────────────────────┘
```

## 📤 关键导出

**函数**

- `connect()`

## 💡 设计思想

1. SQLite 唯一属主 = persistence/：所有连接都走这里，
   统一配置（Row/WAL/外键），避免各模块各自开连接配置漂移。
2. WAL 模式：读写并发不互斥，未来 gateway 多连接友好。

## 🎯 实用场景

1. 数据库连接管理：SQLite 连接创建/复用

## ⚠️ 风险点

1. WAL 会产生 -wal/-shm 文件（git 需忽略；数据库目录勿手动删）
2. 外键约束默认 OFF，本文件显式开启——其他连接方式会丢约束

---
_自动生成于 doc-code 规范落地（2026-09-28）。来源：db.py 头部注释 + 顶层符号。_
