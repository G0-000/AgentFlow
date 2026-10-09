# cli/assembly.md — main() 装配段详解（M1→M5）

> 本文件由 cli/main.md 按功能拆分（2026-10-03）：装配域详解。主流程/入口/知识点/Q&A 见 [main.md](main.md)
>
> assembly  装配；组装

## 📑 目录

- [块 4：main() 装配段（①-⑫）](#块-4main-装配段-①-⑫)
- [块 4·分流：automation 子命令族（main.py:28-31）](#块-4分流automation-子命令族mainpy28-31)
- [块 4-M4：M4 沙箱/审计/派发装配段](#块-4-m4m4-沙箱审计派发装配段)
- [块 6-M5：M5 定时调度 + 长任务装配](#块-6-m5m5-定时调度--长任务装配)
- [⚠️ 风险点](#️-风险点)

## 🧩 代码解析（成块对照 main.py）

### 块 4：`main()` 装配段（①-⑫）

```python
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
```

**结构简析**：装配段只做一件事——**把零件造齐、接好，不干业务**。`main()` 本身无参
（`def main() -> None:`），全部输入来自 `_parse_args()` 返回的 `args`。按数据依赖顺序走，共 12 步：

| 步骤 | 做什么 | 要点 |
|---|---|---|
| ① `_parse_args()` | 解析命令行 | `--thread` 复用会话 / `--goal` 长任务入口 / `automation` 子命令族 |
| ② `load_dotenv` | 加载项目根 `.env`（密钥） | 必须在 `load_config` 之前（`config.yaml` 里 `${API_KEY}` 占位后续展开） |
| **M5 分流** | `args.command=="automation"` → `_handle_automation_command` + `return` | 轻量装配，不进 REPL（详见块 4·分流） |
| ③ `load_config` | 读 `config.yaml` | 缺 API key → 打印提示退出 |
| ④⑤ `init_db` + `create_sqlite_checkpointer` | 持久化底座 | 建表（业务）+ 图状态检查点（LangGraph 自管） |
| ⑥ `get_available_tools` | 工具目录 | 9 个工具 |
| **M4** | 沙箱/审计/派发装配 | `set_sandbox_provider` + 审计 repo + `configure_dispatch_service`（详见块 4-M4） |
| ⑦ 中间件 | `[TitleMiddleware, ThreadDataMiddleware]` | 自动标题 + 线程数据目录 |
| ⑧ 模型 + M3 记忆/知识 | `create_chat_model` + `MemoryFacade`/`KnowledgeService`/`configure_knowledge_service` | 建模型；记忆/知识挂 knowledge 工具 |
| ⑨ `make_lead_agent` | 编译图 | 系统提示注入 `memories.recall(limit=10)` + `build_skills_prompt()` |
| ⑩⑪ `SessionRepository(conn)` + thread_id | 会话记录 + 确定复用/新建 | `thread_id = args.thread or _generate_thread_id()`；`sessions.create(thread_id)` 幂等建行 |
| **M5** | 定时/长任务装配 | `AutomationScheduler` + `GoalEngine`（详见块 6-M5） |
| ⑫ 打印启动信息 | 模型/工具/记忆/知识/沙箱/子代理/审计/会话/定时/数据 | 一眼看清装配了什么 |

**落库要点/补充**：

- `Path(__file__).resolve().parents[5]` 向上 5 级定位项目根，从任何目录启动都找得到 `config.yaml`（P-014）；`load_dotenv(project_root/".env")` 必须在 `load_config` **之前**——`config.yaml` 里 `${DEEPSEEK_API_KEY}` 这类占位由 models_yaml 在此之后展开。
- `sessions.create(thread_id)` 用 `INSERT OR IGNORE`，重复建同 ID 会话不覆盖旧数据（幂等）。
- **M3 为什么用 db_path 而非 conn**：knowledge/memory 工具在 LangGraph 后台线程跑 SQL，SQLite 连接不能跨线程共用——repo 按线程建连接（P-018）；所以 `MemoryRepository(db_path=…)`/`KnowledgeRepository(db_path=…)`/`GoalRepository(db_path=…)`/`AutomationRepository(db_path=…)` 都传路径，唯独 `SessionRepository(conn)` 用主线程连接（主线程专用）。
- 缺 API key 早退：`if cfg.models is None or not cfg.models.chat.api_key: print(...); return`——不建库不建模型，用户能立刻看到缺配置提示。

### 块 4·分流：automation 子命令族（main.py:28-31）

这三行是 M5 加的第一道**分流闸**——把"管理定时任务"的命令从"进 REPL 对话"的完整装配里切出去。

```text
用户敲的命令                     args.command 的值        main() 走哪条路
─────────────────────────────────────────────────────────────────────
uv run agentflow               （没有该属性）            → 继续重装配 → 进 REPL
uv run agentflow automation    "automation"             → 轻量处理 → return（直接退出）
```

**逐行拆**：

| 代码 | 干什么 | 为什么这么写 |
|---|---|---|
| `getattr(args, "command", None)` | **安全**读 `args.command` | argparse 的 `dest="command"` **只在敲了子命令时才生成该属性**；普通启动时 `args` 上没有 command，直接 `args.command` 会抛 `AttributeError`——getattr 带默认值 None 兜底 |
| `== "automation"` | 判断是不是 automation 子命令族 | `_parse_args()` 里 `sub.add_parser("automation")` 注册的就是该值；命中 = 用户要 list/create/pause/resume/delete |
| `_handle_automation_command(args)` | 轻量处理 | 只做 `default_db_path()` + `init_db()` + `AutomationRepository(db_path=...)`，再按 `args.auto_action` 分发 5 个子动作——全部是纯 SQLite 读写，不碰模型 |
| `return` | 立即退出 main() | 跳过后面 ③~⑫ 全部重装配（config/API key/工具/沙箱/模型/agent/checkpointer/REPL 循环） |

**为什么能"轻量装配"**：automation 命令只操作数据库（automations / automation_runs 两张表），
不需要模型、API key、agent、沙箱——所以它们也不该被加载。两个直接好处：

1. **没配 API key 也能用**：`agentflow automation list` 照常工作（缺 key 只拦对话，不拦管理命令）；
2. **省启动时间**：不白跑一遍重装配。

**放置位置也有讲究**：在 ② `load_dotenv` 之后、③ `load_config` 之前——只做完"解析参数 + 读 .env"
两步最轻的准备就分流，连 config.yaml 都不读。

**对比**：`--goal` / `--thread` 不走这条路——它们要进 REPL/长任务，必须完整装配；
automation 是"纯管理命令"，执行完打印结果直接退出，不进对话循环。

**实际用法示例**（在 `backend/packages/harness` 目录下执行；`automation` 不是独立命令，
必须通过 `agentflow` 入口进入，由 argparse 解析出 `args.command == "automation"`）：

```bash
uv run agentflow automation list                                          # 列出所有定时任务
uv run agentflow automation create --name "检查" \
    --prompt "帮我检查一下待办" --cron "*/1 * * * *"                      # 每分钟触发
uv run agentflow automation create --name "日报" \
    --prompt "写今日日报" --schedule "每天9点"                             # 自然语言调度（归一化）
uv run agentflow automation create --name "一次性提醒" --prompt "提醒我" \
    --once --at "2026-10-08T09:00:00"                                     # 一次性任务
uv run agentflow automation pause t_xxxx                                  # 暂停（status→paused）
uv run agentflow automation resume t_xxxx                                 # 恢复（status→active）
uv run agentflow automation delete t_xxxx                                 # 删除（runs 历史保留）
```

命令结构拆解：

```text
uv run agentflow        ← 程序入口（可执行文件 agentflow，pyproject.toml 注册）
          automation    ← argparse 一级子命令（sub.add_parser("automation")）
                  list  ← 二级子动作（auto_action：list/create/pause/resume/delete）
```

单独敲 `automation` 会报 `command not found`——必须带 `agentflow` 前缀。且这些命令
**不需要 API key**：没配 `.env` 时 `uv run agentflow automation list` 也能正常执行
（返回"（无定时任务）"或任务列表）。

### 块 4-M4：M4 沙箱/审计/派发装配段（main 内部片段，main.py:177-192）

```python
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
```

**结构简析**（M4 增量）：插在块 4 既有装配链里的三段新逻辑——① **沙箱 provider 注入**：`set_sandbox_provider(LocalSandboxProvider(project_root / ".sandbox"))` 把本地目录沙箱设为全局单例，终端/文件/子代理操作都落在项目 `.sandbox` 内，越界路径被 `LocalSandbox._resolve` 拦；② **审计 repo 注入**：`SandboxAuditRepository(db_path=db_path)` 建好后，分别 `configure_terminal_audit` / `configure_file_audit` 挂到 terminal_run 与 read_file/write_file 工具（模块级句柄），每次沙箱操作写一行 sandbox_audit；③ **派发服务注入**：`configure_dispatch_service(tools, model)` 把全量工具集 + 父模型塞进 dispatch_subagents 工具的模块级句柄，子代理才能复用工具与模型。本段是 main() 内部片段，无独立函数签名，**不另造参数表**。

**落库要点/补充**：装配顺序敏感——必须先有 `tools`（⑥）→ 沙箱/审计 → 再建 `model`（⑧）→ 最后用 `(tools, model)` 调 `configure_dispatch_service`；沙箱根固定为 `project_root / ".sandbox"`，改项目根定位会同时影响沙箱隔离边界。1 进程 = 1 provider = 1 沙箱 = 1 根目录；按 thread_id 多会话多沙箱是 `acquire(thread_id)` 参数预留方向，M4 未实现。

启动信息随之新增三行（main.py:226-228）：

```python
    print(f"沙箱: {type(get_sandbox_provider()).__name__}（{sandbox_root}）")  # M4
    print(f"子代理: {', '.join(get_subagent_names())}（并行 ≤3）")  # M4
    print(f"审计: {sandbox_audit.count()} 条")  # M4
```

`type(get_sandbox_provider()).__name__` 打印沙箱实现类名；`get_subagent_names()`（subagents/registry.py:64）列出已注册子代理名并标注"并行 ≤3"；`sandbox_audit.count()`（sandbox_audit_repositories.py:86）回显历史审计条数。

### 块 6-M5·③a：M5 定时调度 + 长任务装配 + 启动信息（main.py:338-345）

```python
    # M5：定时调度 + 长任务装配
    #    auto_repo/goal_repo 用 db_path 模式（P-018）：scheduler 是 daemon 线程，
    #    线程本地连接，绝不共享主线程注入的 conn；tick 只扫库+入队，不碰模型。
    goal_repo = GoalRepository(db_path=db_path)
    auto_repo = AutomationRepository(db_path=db_path)
    q = queue.Queue()
    scheduler = AutomationScheduler(auto_repo, q, interval=60)
    scheduler.start()
    engine = GoalEngine(agent, model, goal_repo)
```

```python
    print(f"定时: {len(auto_repo.list_active())} 条 active（tick 60s）")  # M5
```


**整块解析**：M5 在装配末尾注入两条新能力线——

1. `goal_repo`/`auto_repo` 用 **db_path 模式（P-018）**：scheduler 是 daemon 新线程，tick 扫库发生在该线程，必须线程本地连接（threading.local），绝不共享主线程 conn（否则 SQLite check_same_thread 报错）。

2. `q = queue.Queue()`：线程间交接箱——scheduler 只 `put`，主线程 drain 时 `get`。

3. `scheduler = AutomationScheduler(auto_repo, q, interval=60)` + `start()`：启动 daemon tick 线程（每 60s 扫库+入队）。

4. `engine = GoalEngine(agent, model, goal_repo)`：长任务引擎（service 自动包建）；模型只在主线程同步 invoke（R6）。


## ⚠️ 风险点

1. **db_path 是硬要求**：scheduler 线程任何 SQL 走线程本地连接；sessions 保持 conn（只在主线程用）。

2. **scheduler 构造绝不收 agent/模型**：只扫库+入队，执行权在 REPL 主线程（R6）。

3. **tick 命中后主线程同步执行会阻塞 REPL**：换线程并发跑模型会撞 LangGraph 单线程约束。


---
_2026-10-03 新建：从 cli/main.md 按功能拆分（装配域）。_

_2026-10-07 追加：块 4·分流小节（automation 子命令族逐行拆解 + 轻量装配原因 + 放置位置说明）。_

_2026-10-07 追加：块 4·分流 实际用法示例（list/create/pause/resume/delete 命令 + 结构拆解）。_

_2026-10-07 改：块 4 结构简析由长箭头段改为 12 步分条表格（每步一行：步骤/做什么/要点）。_
