# cli/repl.md — 对话循环（⑬ + 定时队列 drain）

> 本文件由 cli/main.md 按功能拆分（2026-10-03）：REPL 主循环详解。总览见 [main.md](main.md)。

## 📑 目录

- [块 5：main() 对话循环（⑬）](#块-5main-对话循环⑬)
- [④ REPL 每轮 input 前的定时队列 drain 循环](#④-repl-每轮-input-前的定时队列-drain-循环)
- [⚠️ 风险点](#️-风险点)

## 🧩 代码解析（成块对照 main.py）

### 块 5：`main()` 对话循环（⑬，main 内部片段）

```python
    first_turn = True
    while True:
        # M5：每轮 input 之前先非阻塞 drain 定时队列——命中即在主线程同步执行；
        #     scheduler daemon 线程绝不触碰 agent/模型（R6：单线程 CLI，执行期间用户等待）
        while True:
            try:
                task_id, prompt = q.get_nowait()
            except queue.Empty:
                break
            run_id = auto_repo.start_run(task_id)
            task_row = auto_repo.get(task_id) or {}
            tname = task_row.get("name") or task_id
            print(f"⏰ 定时触发: {tname}")
            t0 = datetime.now(UTC)
            run_status = "success"
            try:
                resp = agent.invoke(
                    {"messages": [HumanMessage(prompt)]},
                    config={"configurable": {"thread_id": f"auto-{task_id}"}},
                )
                msgs = (
                    resp.get("messages") if isinstance(resp, dict) else getattr(resp, "messages", [])
                )
                out_text = msgs[-1].content if msgs else ""
                auto_repo.finish_run(
                    run_id,
                    status="success",
                    output=out_text,
                    duration_seconds=(datetime.now(UTC) - t0).total_seconds(),
                )
                run_status = "success"
                print(f"Agent > {out_text}")
            except Exception as exc:  # noqa: BLE001 —— 单次定时任务失败不崩 REPL
                auto_repo.finish_run(run_id, status="failed", error=str(exc)[:300])
                run_status = "failed"
                print(f"[定时任务失败] {str(exc)[:200]}")
            auto_repo.touch_last_run(
                task_id,
                last_status=run_status,
                run_count_inc=1,
                once_fired=1 if task_row.get("schedule_type") == "once" else None,
            )

        try:
            user_input = input("你 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见")
            break
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            print("再见")
            break

        # 存用户消息（业务记录）
        sessions.add_message(thread_id, "user", user_input)

        # M3：沉淀记忆（规则提取用户事实，静默落库；新会话启动时自动注入）
        memories.remember(thread_id, "user", user_input)

        # 跑图：LangGraph 内部循环（模型→工具→模型），逐块流式回传
        print("Agent > ", end="", flush=True)
        full_response = ""
        try:
            for chunk in agent.stream(
                {"messages": [{"role": "user", "content": user_input}]},
                config={"configurable": {"thread_id": thread_id}},  # 持久化维度
            ):
                # chunk 是节点输出字典；取 messages 里新增的 assistant 文本
                # （结构可能是 {'model': {...}} 嵌套，用 _iter_chunk_messages 兼容）
                for msg in _iter_chunk_messages(chunk):
                    text = getattr(msg, "content", "")
                    if text and isinstance(msg.content, str):
                        print(text, end="", flush=True)  # 流式（逐块打印）
                        full_response += text
        except Exception as exc:  # noqa: BLE001 —— 故意捕获所有模型调用异常（限流/欠费/网络抖动）给友好提示，不让调试 CLI 崩掉
            # 容错：模型服务端限流/欠费/网络抖动时给友好提示，不崩掉整个 CLI
            # （实测：智谱免费模型高峰期返回 code 1305 访问量过大，见问题日志 P-015）
            print(f"\n[模型调用失败] {type(exc).__name__}: {str(exc)[:200]}")
            full_response = f"(调用失败: {str(exc)[:120]})"
        print()  # 换行结束本轮

        # 存回复 + 刷新会话时间
        sessions.add_message(thread_id, "assistant", full_response)
        sessions.touch(thread_id)

        # 自动标题（M2）：首轮对话后读图状态里的 title（TitleMiddleware 生成），
        # 落库 sessions.title + 控制台提示。标题只生成一次（中间件幂等）。
        if first_turn:
            first_turn = False
            try:
                st = agent.get_state({"configurable": {"thread_id": thread_id}})
                title = (st.values or {}).get("title") if st else None
                if title:
                    sessions.update_title(thread_id, title)
                    print(f"\n[标题] {title}")
            except Exception:  # noqa: BLE001, S110 —— 标题失败不影响对话（无日志，调试期静默）
                pass

```

**结构简析**：REPL 主循环，一次运行 = 一个会话，循环到 exit/quit/EOF/Ctrl-C。每轮七步：① **M5 drain 定时队列**（`q.get_nowait()` 非阻塞抽队列，命中就在主线程 `agent.invoke` 跑定时任务，跑完 `finish_run`+`touch_last_run`，队列空才 `break`）；② `input("你 > ").strip()` 读用户输入（空行 continue、exit/quit 退出）；③ `sessions.add_message(thread_id, "user", ...)` 先存用户消息；④ `memories.remember(thread_id, "user", ...)` M3 规则提取用户事实静默落库；⑤ `agent.stream(...)` 流式跑图，`_iter_chunk_messages` 逐块取消息 `print(..., end="", flush=True)` 打字机打印并拼 `full_response`；⑥ `sessions.add_message(thread_id, "assistant", full_response)` + `sessions.touch(thread_id)` 存回复并刷新会话时间；⑦ 首轮 `agent.get_state` 读 TitleMiddleware 写入的 `title` → `sessions.update_title` 落库（`first_turn` 保证只做一次）。

**落库要点/补充**：

- `except Exception` 故意兜住所有模型调用异常（限流/欠费/网络抖动不崩 CLI，实测智谱 code 1305），本轮回复记为 `(调用失败: ...)`；定时任务 drain 段的异常同样被兜住，只打印 `[定时任务失败]`，**不崩 REPL**。
- 标题生成异常静默吞掉（无日志，调试期静默）——标题是锦上添花，失败不影响对话。
- 定时任务用独立 `thread_id=f"auto-{task_id}"`，**不污染用户会话**；`agent.invoke`（一次性）而非 `stream`（流式）跑定时任务，结果整段打印。
- 先存后跑：用户消息在 `agent.stream` **之前**落库——即使模型调用崩了，历史也能查到。



**④ REPL 每轮 input 前的定时队列 drain 循环（main.py:388-427）**：

```python
        # M5：每轮 input 之前先非阻塞 drain 定时队列——命中即在主线程同步执行；
        #     scheduler daemon 线程绝不触碰 agent/模型（R6：单线程 CLI，执行期间用户等待）
        while True:
            try:
                task_id, prompt = q.get_nowait()
            except queue.Empty:
                break
            run_id = auto_repo.start_run(task_id)
            task_row = auto_repo.get(task_id) or {}
            tname = task_row.get("name") or task_id
            print(f"⏰ 定时触发: {tname}")
            t0 = datetime.now(UTC)
            run_status = "success"
            try:
                resp = agent.invoke(
                    {"messages": [HumanMessage(prompt)]},
                    config={"configurable": {"thread_id": f"auto-{task_id}"}},
                )
                msgs = (
                    resp.get("messages") if isinstance(resp, dict) else getattr(resp, "messages", [])
                )
                out_text = msgs[-1].content if msgs else ""
                auto_repo.finish_run(
                    run_id,
                    status="success",
                    output=out_text,
                    duration_seconds=(datetime.now(UTC) - t0).total_seconds(),
                )
                run_status = "success"
                print(f"Agent > {out_text}")
            except Exception as exc:  # noqa: BLE001 —— 单次定时任务失败不崩 REPL
                auto_repo.finish_run(run_id, status="failed", error=str(exc)[:300])
                run_status = "failed"
                print(f"[定时任务失败] {str(exc)[:200]}")
            auto_repo.touch_last_run(
                task_id,
                last_status=run_status,
                run_count_inc=1,
                once_fired=1 if task_row.get("schedule_type") == "once" else None,
            )
```

**④ 整块解析**（main 内部片段）：每轮 `input("你 > ")` **之前**先非阻塞 drain 定时队列——

1. `q.get_nowait()` 取到就执行（`except queue.Empty: break` 无任务立即退出）；

2. 命中任务在**主线程** `agent.invoke` 跑模型（R6：模型调用只在主线程），thread_id=`auto-{task_id}` 独立会话；

3. `finish_run` 写执行历史、`touch_last_run` 更新 run_count/once_fired（once 型传 1 幂等标记）。


## ⚠️ 风险点

1. **drain 在主线程同步执行会阻塞用户输入**：单次定时任务失败不崩 REPL（BLE001 兜底，finish_run 记 failed）。

2. 定时任务与用户对话共用主线程：长任务执行期间用户等待（R6 设计取舍）。


---
_2026-10-03 新建：从 cli/main.md 按功能拆分（对话循环域）。_
