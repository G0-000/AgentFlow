# cli/goal.md — 长任务入口（断点恢复 + --goal）

> 本文件由 cli/main.md 按功能拆分（2026-10-03）：长任务域详解。总览见 [main.md](main.md)。

## 📑 目录

- [③b 断点恢复 + `--goal` 入口（main 内片段）](#b-断点恢复--goal-入口main-内片段)
- [⚠️ 风险点](#️-风险点)

## 🧩 代码解析（成块对照 main.py）

### ③b 断点恢复 + `--goal` 入口（main 内片段，main.py:375-385）

```python
    # M5：断点恢复——该 thread 上有未完成长任务则从下一步续跑（已完成步不重跑）
    active_goal = goal_repo.get_active_by_thread(thread_id)
    if active_goal and active_goal["goal_status"] in (
        "planning",
        "planned",
        "executing",
        "paused",
    ):
        print(
            f"[恢复] 长任务继续：第 {active_goal['completed_steps'] + 1}/"
            f"{active_goal['max_steps']} 步"
        )
        engine.resume(thread_id)

    # M5：--goal 长任务入口：先跑 GoalEngine（计划→逐步→汇总），完成后再进 REPL
    if args.goal:
        engine.start(thread_id, args.goal)
```

**整块解析**：REPL 启动前先查该 thread 的未完成长任务——

1. `get_active_by_thread(thread_id)` 找可恢复态（planning/planned/executing/paused，OPEN 4 态）；

2. 命中则 `engine.resume(thread_id)`：从 `completed_steps + 1` 步续跑（已完成步不重跑，断点坐标 = SQL 业务坐标 + checkpointer 消息链）；

3. `args.goal` 非空则 `engine.start(thread_id, goal_text)`：新长任务（计划→逐步→汇总），完成后再进 REPL。


## ⚠️ 风险点

1. **断点恢复只认 OPEN 4 态**（不含 pending——pending 未规划无断点）；终态行不会被 resume。

2. resume 与 --goal 互斥语义：先恢复后新建，两者按顺序执行。


---
_2026-10-03 新建：从 cli/main.md 按功能拆分（长任务域）。_
