# persistence/bootstrap.py — bootstrap.py

> **文件路径**: `backend/packages/harness/agentflow/persistence/bootstrap.py`
> **目录位置**: persistence → bootstrap.py
> **职责**: 幂等建表

## 📋 结构图

```text
┌──────────────────────────────────────────────┐
│ init_db(db_path)                             │
│   ① connect(db_path)  （db.py 统一配置）      │
│   ② executescript(SCHEMA_SQL) 建表           │
│   ③ commit                                   │
│   ④ return conn（调用方可继续使用）           │
│   └── 幂等: CREATE TABLE IF NOT EXISTS       │
│       重复调用不会报错                        │
└──────────────────────────────────────────────┘
```

## 📤 关键导出

**函数**

- `init_db()`

## 💡 设计思想

1. 建表集中一处（schema.py），bootstrap 只负责执行 + 提交。
2. 幂等设计：启动/测试多次调用不报错（IF NOT EXISTS）。
3. init_db(":memory:") 内存库跑测试（无文件污染）。

## 🎯 实用场景

1. 启动建表：sessions/session_messages + checkpoint 表，幂等（已存在跳过）
2. 测试便利：init_db(":memory:") 内存库跑测试

## ⚠️ 风险点

1. 改 schema.py 的表结构后，旧库不自动迁移（M 后期补 migration）
2. 返回的 conn 由调用方负责 close（CLI 进程退出自动释放）

---
_自动生成于 doc-code 规范落地（2026-09-28）。来源：bootstrap.py 头部注释 + 顶层符号。_
