# observability/__init__.py — __init__.py

> **文件路径**: `backend/packages/harness/agentflow/observability/__init__.py`
> **目录位置**: observability → __init__.py
> **职责**: 可观测域包入口（run 根记录 + span 链路，M6）

## 📋 结构图

```text
（无复杂调用图）
```

## 📤 关键导出

（无顶层导出，见各子模块）

- `observability/tables.py` → `ObservabilityTable`（表名常量）
- `observability/store.py` → `ObsTraceStore`（SQLite 链路存储）
- `observability/recorder.py` → `ObservabilityRecorder` / `new_run_id`（fire-and-forget 记录器）

## 💡 设计思想

1. 只做统一导出/包声明，不承载业务逻辑。
2. 包内分三层：tables（表名常量）→ store（怎么落 SQLite）→ recorder（何时记 + 异步发）。

## 🎯 实用场景

1. 对话开始/各 span 埋点：经 recorder 异步写 obs.db
2. 排障/查链路：store.get_run + query_events 按 run_id 还原完整时序

## ⚠️ 风险点

1. 勿在此放业务逻辑（保持包入口纯净）
2. 观测写是 fire-and-forget，事件可能丢；排障看 warning 日志

---
_2026-10-05 M6 新增：目录 + 结构图 + 流程图 + 成块代码解析（参数逐条表）+ Q&A。_
