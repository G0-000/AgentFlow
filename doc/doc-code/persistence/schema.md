# persistence/schema.py — schema.py

> **文件路径**: `backend/packages/harness/agentflow/persistence/schema.py`
> **目录位置**: persistence → schema.py
> **职责**: 表结构定义

## 📋 结构图

```text
┌────────────────────────────────────────────────┐
│ SCHEMA_SQL（唯一表定义处）                     │
│   sessions         会话表                      │
│     id PK / created_at / updated_at / title    │
│   session_messages 消息表                      │
│     id PK / session_id FK→sessions             │
│     role / content / created_at               │
│   └── 为什么拆表: 会话元信息与消息分开，       │
│       未来查询各取所需（M7 前端会话列表）       │
└────────────────────────────────────────────────┘
```

## 📤 关键导出

**常量**

- `SCHEMA_SQL`

## 💡 设计思想

1. 表定义唯一权威来源：bootstrap 直接 executescript(SCHEMA_SQL)。
2. 拆表设计：会话元信息与消息分开，列表查询不拖消息内容。

## 🎯 实用场景

1. 表结构定义：sessions/session_messages 字段的唯一权威来源

## ⚠️ 风险点

1. 改表结构 = 破坏性变更：旧库不迁移，需手动重建或写 migration
2. session_messages.session_id 外键 → sessions.id（外键约束依赖 db.py 开启）

---
_自动生成于 doc-code 规范落地（2026-09-28）。来源：schema.py 头部注释 + 顶层符号。_
