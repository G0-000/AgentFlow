# ============================================================================
# AgentFlow · cli/main.py —— 终端对话 CLI
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/cli/main.py
# 对标来源: evoflow/cli/main.py
#   原版 CLI 是调试入口，正式入口在 gateway；M1 先让 CLI 成为唯一入口，
#   M7 再让位给 API。
# 里程碑: M1（M2 接入工具/中间件/标题落库/启动信息）
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────────────────────┐
# │ main()  [uv run agentflow]                                   │
# │   ├─ 解析 --thread <id> 参数                                 │
# │   ├─ load_dotenv()          ← 读项目根 .env（密钥）          │
# │   ├─ load_config()          ← 读 config.yaml → AppConfig    │
# │   ├─ init_db(db_path)       ← 建表（sessions 等）            │
# │   ├─ create_sqlite_checkpointer(db_path) ← 图状态检查点      │
# │   ├─ get_available_tools()  ← 工具目录（M2，5 个）            │
# │   ├─ 中间件 2 个            ← 标题/线程目录（M2）            │
# │   ├─ create_chat_model(cfg) ← 模型工厂 → ChatOpenAI          │
# │   ├─ make_lead_agent(...)   ← 构建主 Agent（带持久化）       │
# │   ├─ SessionRepository(conn) ← 会话记录 repo                 │
# │   └─ 对话循环:                                               │
# │        你 > 输入 → agent.stream({messages}, thread_id)       │
# │              → 逐块打印回复 → 存消息记录 → 首轮标题落库       │
# │              → 循环直到 exit                                 │
# └──────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 入口层只做装配（配置/模型/检查点/repo/工具/中间件），业务在 agents/。
# 2. 启动信息显示模型/工具/会话/数据：调试 P-014/015/016 全靠它
#    （限流/流式问题第一时间看到是哪个模型/供应商）。
# 3. 对话循环容错：模型调用失败给友好提示不崩（P-015 限流实测）。
# 4. 从任何目录启动都能找到配置（Path(__file__) 定位，P-014）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. main: CLI 入口（pyproject [project.scripts] agentflow 指向它）
# 🔒 内部私有函数
# 1. _parse_args: --thread 参数解析
# 2. _generate_thread_id: 新会话 ID（os.urandom 随机 8 字节 → 32 位 hex）
# 3. _iter_chunk_messages: 从 langgraph stream chunk 递归取消息（P-016）
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. Path(__file__).parents[5] 定位项目根，改目录层级会失效
# 2. _iter_chunk_messages 兼容嵌套/顶层两种 chunk 形态，勿简化
# 3. 首轮标题逻辑依赖 TitleMiddleware 写 state["title"]，两者需同步
# ============================================================================

from __future__ import annotations

import argparse
import os
import queue
from datetime import UTC, datetime
from pathlib import Path

# dotenv: 读取项目根 .env 到环境变量（密钥不写进 yaml/代码）
from dotenv import load_dotenv

# M5 域：定时调度（手写 cron + daemon tick 线程）/ 定时任务持久化
from langchain_core.messages import HumanMessage

from agentflow.agents.checkpointer.provider import create_sqlite_checkpointer

# agents 域（主 Agent + 检查点）
from agentflow.agents.lead_agent.agent import make_lead_agent
from agentflow.agents.lead_agent.prompt import build_lead_agent_system_prompt

# 中间件（M2）：自动标题 + 线程数据目录
from agentflow.agents.middlewares.thread_data_middleware import ThreadDataMiddleware
from agentflow.agents.middlewares.title_middleware import TitleMiddleware

# 配置域
from agentflow.config.app_config import load_config
from agentflow.config.paths import default_db_path

# M3 域：记忆门面 / 知识库服务 / 技能加载 / 工具注入
from agentflow.knowledge.service import KnowledgeService
from agentflow.memory.facade import MemoryFacade

# 模型域（工厂）
from agentflow.models.factory import create_chat_model
from agentflow.persistence.automation_repositories import AutomationRepository

# 持久化域（建表 / 会话 repo）
from agentflow.persistence.bootstrap import init_db
from agentflow.persistence.goal_repositories import GoalRepository
from agentflow.persistence.knowledge_repositories import KnowledgeRepository
from agentflow.persistence.memory_repositories import MemoryRepository
from agentflow.persistence.sandbox_audit_repositories import SandboxAuditRepository
from agentflow.persistence.session_repositories import SessionRepository

# M4 域：沙箱（目录隔离）/ 子代理注册表 / 派发与审计注入
from agentflow.sandbox import (
    LocalSandboxProvider,
    get_sandbox_provider,
    set_sandbox_provider,
)
from agentflow.scheduler.cron import normalize_schedule
from agentflow.scheduler.loop import AutomationScheduler

# skills 加载 + knowledge 工具注入（M3）
from agentflow.skills.loader import build_skills_prompt
from agentflow.subagents import get_subagent_names
from agentflow.tools.builtins.dispatch_tool import configure_dispatch_service
from agentflow.tools.builtins.file_tools import (
    configure_sandbox_audit_repository as configure_file_audit,
)
from agentflow.tools.builtins.knowledge_tool import configure_knowledge_service
from agentflow.tools.builtins.terminal_tool import (
    configure_sandbox_audit_repository as configure_terminal_audit,
)

# 工具域（M2）：工具收集 + 结果存取
from agentflow.tools.tools import get_available_tools

# 核心域（并行 shard）：GoalEngine 落点可能在 agents/goal 或顶层 goal，两者兼容
try:  # pragma: no cover
    from agentflow.agents.goal.goal_loop import GoalEngine
except ImportError:  # pragma: no cover
    from agentflow.goal.goal_loop import GoalEngine


def _parse_args() -> argparse.Namespace:
    """命令行参数: --thread 复用会话；M5 加 --goal 长任务入口 + automation 子命令族。"""
    p = argparse.ArgumentParser(description="AgentFlow 终端对话")
    p.add_argument(
        "--thread",
        default=None,  # 缺省 = 新会话（自动生成 thread_id）
        help="复用指定会话 ID（thread_id），继续上次对话",
    )
    p.add_argument(
        "--goal",
        default=None,  # 缺省 = 普通 REPL
        help="启动后先以长任务模式跑 GoalEngine（计划→逐步→汇总），完成后再进 REPL",
    )

    # M5：automation 定时任务子命令族（无子命令 = 进 REPL 默认行为）
    sub = p.add_subparsers(dest="command")
    pa = sub.add_parser("automation", help="定时任务管理（list/create/pause/resume/delete）")
    auto = pa.add_subparsers(dest="auto_action")

    auto.add_parser("list", help="列出全部定时任务")

    pc = auto.add_parser("create", help="创建定时任务")
    pc.add_argument("--name", default="", help="任务名（展示用）")
    pc.add_argument("--prompt", required=True, help="到点投递的提示词")
    pc.add_argument("--cron", default=None, help='标准 5 字段 cron，如 "*/1 * * * *"')
    pc.add_argument(
        "--schedule",
        default=None,
        help='自然语言调度，如 "每天9点"（与 --cron 二选一，经 normalize 归一）',
    )
    pc.add_argument("--once", action="store_true", help="一次性任务（配 --at）")
    pc.add_argument("--at", default=None, help='once 型目标时间 ISO，如 "2026-10-03T09:00:00"')

    pp = auto.add_parser("pause", help="暂停任务")
    pp.add_argument("auto_id", help="任务 task_id")
    pr = auto.add_parser("resume", help="恢复任务")
    pr.add_argument("auto_id", help="任务 task_id")
    pd = auto.add_parser("delete", help="删除任务（runs 历史保留）")
    pd.add_argument("auto_id", help="任务 task_id")

    return p.parse_args()


def _generate_thread_id() -> str:
    """新会话 ID：os.urandom(8) 生成 8 个随机字节 → 32 位十六进制字符串。

    纯随机、无需查重（8 字节随机冲突概率可忽略），不暴露创建时间。
    """
    return os.urandom(8).hex()


def _iter_chunk_messages(chunk: dict) -> list:
    """从 langgraph stream chunk 里取新增消息（递归）——把每一小块 chunk 里的新消息捞出来。

    langgraph 1.0.x create_agent 的 stream 输出是**节点嵌套结构**：
        {'model': {'messages': [AIMessage(...)]}}
    而不是顶层 {'messages': [...]}（CLI 曾直接取顶层导致空打印，见 P-016）。
    递归兼容两种形态，取到第一个 messages 列表即返回。
    """
    top = chunk.get("messages")
    if top:
        return top
    for v in chunk.values():
        if isinstance(v, dict):
            found = _iter_chunk_messages(v)
            if found:
                return found
    return []


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


def main() -> None:
    """CLI 入口：装配所有组件，进入对话循环。"""
    args = _parse_args()  # ① 解析命令行：--thread 复用会话

    # ② 密钥：加载项目根 .env（AGENTFLOW_ROOT 向上找）
    #    config.yaml 里 ${DEEPSEEK_API_KEY} 由 models_yaml 在此之后展开
    project_root = Path(__file__).resolve().parents[5]
    load_dotenv(project_root / ".env")

    # M5：automation 子命令族——轻量装配（无需模型/API key），执行完直接退出，不进 REPL
    if getattr(args, "command", None) == "automation":
        _handle_automation_command(args)
        return

    # ③ 配置：config.yaml → AppConfig（路径/日志/模型）
    #    对齐原版：固定用项目根 config.yaml（Path(__file__).parents[N] 向上找），
    #    不依赖"从哪个目录启动"——否则在 backend/ 下跑会找不到根目录的 config.yaml
    cfg = load_config(str(project_root / "config.yaml"))
    if cfg.models is None or not cfg.models.chat.api_key:
        print("缺少模型配置：请检查 config.yaml 的 models 段，并在 .env 填写 API key")
        return

    # ④ 数据库：建表 + 连接（sessions/session_messages + checkpoint 表）
    db_path = default_db_path()
    conn = init_db(db_path)

    # ⑤ 检查点：图状态 → SQLite（同一 thread_id 恢复对话）
    checkpointer = create_sqlite_checkpointer(db_path)

    # ⑥ 工具（M2→M4）：工具目录全量工具（9 个，含沙箱终端/文件/子代理派发）
    tools = get_available_tools()

    # M4：沙箱装配——本地目录沙箱（子代理/终端操作落在项目 .sandbox 内，
    # **1 进程 = 1 provider = 1 沙箱 = 1 根目录**。多会话多沙箱（按 thread_id 区分目录）是 `acquire(thread_id)` 参数预留的方向，M4 未实现。
    #     宿主目录访问被 LocalSandbox._resolve 拦截；全程写审计）
    sandbox_root = project_root / ".sandbox"
    # ← 沙箱单例
    # 注入沙箱
    set_sandbox_provider(LocalSandboxProvider(sandbox_root))
    # 审计追踪 repo 注入：
    sandbox_audit = SandboxAuditRepository(db_path=db_path)
    # 挂到 terminal_run 与 read_file/write_file 工具（模块级句柄），每次沙箱操作写一行 sandbox_audit
    configure_terminal_audit(sandbox_audit)
    configure_file_audit(sandbox_audit)

    # ⑦ 中间件（M2）：标题 + 线程数据目录（挂到 Agent 上，横向能力）
    middlewares = [TitleMiddleware(), ThreadDataMiddleware()]

    # ⑧ 模型 + M3 记忆/知识装配 + ⑨ Agent（含记忆/技能注入）
    model = create_chat_model(cfg.models.chat)

    # M4：派发服务注入（dispatch_subagents 工具用：子代理工具集 + 父模型） 把全量工具集 + 父模型塞进
    configure_dispatch_service(tools, model)

    # M3：记忆门面（跨会话用户事实）与知识库服务（分块/向量/检索）
    #     用 db_path 模式（P-018）：LangGraph 工具在后台线程跑 SQL，
    #     repo 按线程建连接，避免 SQLite 跨线程报错
    memories = MemoryFacade(MemoryRepository(db_path=db_path))
    knowledge = KnowledgeService(
        KnowledgeRepository(db_path=db_path), cfg.models.embedding
    )
    configure_knowledge_service(knowledge)  # 挂到 knowledge 工具上（模块级句柄）

    # M3：启动时注入"已记住的事实 + 可用技能"到系统提示词
    #     （记忆随对话增长，新会话启动时读取最新快照——跨会话记住的入口）
    memory_ctx = memories.recall(limit=10)
    skills_ctx = build_skills_prompt()
    system_prompt = build_lead_agent_system_prompt(memory_ctx, skills_ctx)

    agent = make_lead_agent(
        model=model,
        checkpointer=checkpointer,
        tools=tools,
        middlewares=middlewares,
        system_prompt=system_prompt,
    )

    # ⑩ 会话记录 repo（业务记录：会话 + 明文消息）
    sessions = SessionRepository(conn)

    # ⑪ 确定 thread_id（复用 or 新建），并保证会话行存在
    thread_id = args.thread or _generate_thread_id()
    sessions.create(thread_id)

    # M5：定时调度 + 长任务装配
    #    auto_repo/goal_repo 用 db_path 模式（P-018）：scheduler 是 daemon 线程，
    #    线程本地连接，绝不共享主线程注入的 conn；tick 只扫库+入队，不碰模型。
    goal_repo = GoalRepository(db_path=db_path)
    auto_repo = AutomationRepository(db_path=db_path)
    q = queue.Queue()
    scheduler = AutomationScheduler(auto_repo, q, interval=60)
    scheduler.start()
    engine = GoalEngine(agent, model, goal_repo)

    # ⑫ 启动信息：让控制台一眼看清"用的哪个模型 / 供应商 / 会话 / 数据 / 工具"
    #    （需求：之前只显示会话 ID 太少；模型信息对调试很关键，P-014/015/016 都要靠它）
    reuse = "续用历史会话" if args.thread else "新会话"
    print(
        f"模型: {cfg.models.chat.model}（provider={cfg.models.chat.provider} @ {cfg.models.chat.base_url}）"
    )
    print(f"工具: {len(tools)} 个（{', '.join(t.name for t in tools)}）")
    print(
        f"记忆: {memories.count()} 条 | 知识库: {len(knowledge.list_docs())} 文档"
    )  # M3
    print(f"沙箱: {type(get_sandbox_provider()).__name__}（{sandbox_root}）")  # M4
    print(f"子代理: {', '.join(get_subagent_names())}（并行 ≤3）")  # M4
    print(f"审计: {sandbox_audit.count()} 条")  # M4
    print(f"会话: {thread_id}（{reuse}；--thread {thread_id} 可继续此会话）")
    print(f"定时: {len(auto_repo.list_active())} 条 active（tick 60s）")  # M5
    print(f"数据: {db_path}")
    print("输入 exit 退出\n")

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

    # ⑬ 对话循环
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


if __name__ == "__main__":
    main()
