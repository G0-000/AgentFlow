# cli/automation.md — automation 子命令族（list/create/pause/resume/delete）

> 本文件由 cli/main.md 按功能拆分（2026-10-03）：定时任务 CLI 子命令详解。总览见 [main.md](main.md)。

## 📑 目录

- [② `_handle_automation_command()`](#②-_handle_automation_command)
- [③ automation 分发入口（main 内）](#③-automation-分发入口main-内)
- [⚠️ 风险点](#️-风险点)

## 🧩 代码解析（成块对照 main.py）

**② automation 子命令族函数 `_handle_automation_command`（main.py:198-252）**：

```python
def _handle_automation_command(args: argparse.Namespace) -> None:
    """M5 automation 子命令族：list/create/pause/resume/delete。

    轻量装配（只建 db + AutomationRepository，不建模型/agent/checkpointer），
    执行完即返回退出，不进 REPL。
    """
    db_path = default_db_path()
    init_db(db_path)
    auto_repo = AutomationRepository(db_path=db_path)
    action = getattr(args, "auto_action", None)

    if action == "list":
        rows = auto_repo.list()
        if not rows:
            print("（无定时任务）")
            return
        for r in rows:
            print(
                f"{r['task_id']}  {r['name'] or '(未命名)'}  "
                f"cron={r['schedule']}  type={r['schedule_type']}  "
                f"status={r['status']}  runs={r['run_count']}  "
                f"last={r['last_run'] or '-'}"
            )
        return

    if action == "create":
        raw = args.cron or args.schedule or ""  # 缺省两者都没有 → normalize 走兜底
        schedule = normalize_schedule(raw)
        task_id = "t_" + os.urandom(6).hex()
        schedule_type = "once" if args.once else "recurring"
        scheduled_at = args.at if args.once else None
        auto_repo.create(
            task_id=task_id,
            name=args.name or "",
            prompt=args.prompt,
            schedule=schedule,
            schedule_type=schedule_type,
            scheduled_at=scheduled_at,
        )
        print(f"已创建定时任务 {task_id}（cron={schedule}，type={schedule_type}）")
        return

    if action in ("pause", "resume", "delete"):
        tid = args.auto_id
        if action == "pause":
            auto_repo.pause(tid)
        elif action == "resume":
            auto_repo.resume(tid)
        else:
            auto_repo.delete(tid)
        zh = {"pause": "暂停", "resume": "恢复", "delete": "删除"}[action]
        print(f"已{zh}任务 {tid}")
        return

    print("用法: agentflow automation list|create|pause|resume|delete ...")
```



**③ main() 里的 automation 分发 + 定时/长任务装配 + 启动信息 + resume/--goal（main.py:264-267 / 339-347 / 363 / 367-383）**：

```python
    # M5：automation 子命令族——轻量装配（无需模型/API key），执行完直接退出，不进 REPL
    if getattr(args, "command", None) == "automation":
        _handle_automation_command(args)
        return
```

**整块解析**：main() 顶部先分发——`args.command == "automation"` 时走轻量子命令族，`_handle_automation_command` 只建 db + repo（不建模型/agent/checkpointer），执行完直接 return，不进 REPL（无模型调用）。


## ⚠️ 风险点

1. **轻量装配**：该路径不碰模型——`create` 的 cron 由 `normalize_schedule` 归一（缺省兜底 `0 9 * * *`）。

2. `task_id = "t_" + os.urandom(6).hex()`：与 thread_id 同款随机生成，不暴露任务数量。


---
_2026-10-03 新建：从 cli/main.md 按功能拆分（automation 子命令域）。_
