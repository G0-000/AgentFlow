# persistence/timestamps.py — timestamps.py

> **文件路径**: `backend/packages/harness/agentflow/persistence/timestamps.py`
> **目录位置**: persistence → timestamps.py
> **职责**: 统一时间戳

## 📋 结构图

```text
┌──────────────────────────────────────────────┐
│ now_utc_iso() → str                          │
│   datetime.now(timezone.utc)                 │
│     .isoformat() → "2026-09-28T15:00:00.123Z"│
└──────────────────────────────────────────────┘
```

## 📤 关键导出

**函数**

- `now_utc_iso()`

## 💡 设计思想

1. 全库统一 UTC ISO 字符串，避免各模块自己格式化（时区/格式漂移）。
2. 存 UTC，显示时由展示层转本地时区（M8 前端处理）。

## 🎯 实用场景

1. 统一时间戳：ISO 格式 + UTC，避免各文件各写各的

## ⚠️ 风险点

1. 一律 UTC：不要在函数里改回本地时间，显示层负责转换

---
_自动生成于 doc-code 规范落地（2026-09-28）。来源：timestamps.py 头部注释 + 顶层符号。_
