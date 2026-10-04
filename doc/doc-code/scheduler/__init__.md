# scheduler/__init__.py — __init__.py

> **文件路径**: `backend/packages/harness/agentflow/scheduler/__init__.py`
> **目录位置**: scheduler → __init__.py
> **职责**: 定时调度域包入口（统一导出 cron + loop）

## 📋 结构图

```text
（无复杂调用图）

scheduler/
  ├─ cron.py   手写 5 字段 cron 匹配（无第三方依赖）
  └─ loop.py   AutomationScheduler（daemon tick 线程，只入队不碰模型）
```

## 📤 关键导出

- `normalize_schedule` / `cron_matches_at`（来自 cron.py）
- `AutomationScheduler`（来自 loop.py）

## 💡 设计思想

1. tick 线程只"扫库 + 入队"，绝不建 agent / 不碰模型（执行权在 REPL 主线程，R4/R6）。
2. cron 匹配纯 stdlib 手写，不引 croniter/rrule 第三方库。
3. 包入口统一 re-export，调用方 `from agentflow.scheduler import ...` 即可。

## 🎯 实用场景

1. 定时任务触发场景：CLI 装配 AutomationScheduler，REPL drain 队列执行
2. 调度表达式归一化场景：建任务前 normalize_schedule 兜底非法写法

## ⚠️ 风险点

1. 勿在此放业务逻辑（保持包入口纯净）
2. daemon tick 线程只入队，任何"在线程里直接 invoke 模型"的改动都违反 R4

---
_2026-10-02 新建：M5 文档（目录 + 流程图 + 成块代码解析 + Q&A）。_
