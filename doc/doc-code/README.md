<!-- ============================================================
  AgentFlow doc · doc-code 总览（代码地图 + M1 文件总目录）
  更新时间: 2026-10-05（更新至 M6；按当前源码复核）
  关联: 代码 /Users/main/AgentFlow/backend/packages/harness/agentflow/
  用途: 与代码目录一一对应的"设计说明 + 问题总结"文档
  维护约定: 本页是当前代码索引；历史里程碑文档保留当时记录，具体实现以当前源码与文件级说明为准
================================================================ -->
# doc-code —— 代码结构文档（与 agentflow/ 目录一一对应）

> 先用本页找到模块，再点进文件说明。历史记录可能沿用当时的阶段称呼；当前行为以源码为准。
> 当前核心包有 **104 个 Python 文件**。测试文档只覆盖明确列出的测试文件，不等同于全量测试清单。

## 1. 当前代码全景（agentflow/ 104 个 Python 文件）

```
backend/packages/harness/agentflow/          ← 核心层（import 叫 agentflow）
├── __init__.py                                ← 包入口（__version__）
├── config/       6 文件  配置域（yaml → 类型化对象，含 MCP 配置）
├── models/       3 文件  模型域（配置 → ChatOpenAI）
├── persistence/ 12 文件  业务表 repo 与 schema（M6 trace 库另由 observability/store.py 管理）
├── agents/       16 文件  Agent 域（状态/检查点/主Agent/中间件/Goal）
├── tools/        13 文件  工具域（分层/收集/结果存取 + 9 内置工具）
├── knowledge/    6 文件  知识域（chunker 切分 → embedding 向量化 → service 检索）
├── memory/       3 文件  记忆域（consolidate 合并 → facade 门面）
├── skills/       2 文件  技能域（loader 技能加载）
├── subagents/    7 文件  子代理域（M4：config/registry/executor + builtins）
├── sandbox/      6 文件  沙箱域（M4：ABC/Provider/Noop/Local 目录隔离）
├── mcp/          3 文件  MCP 外部服务器接入（M6：client + tools）
├── community/    6 文件  第三方集成包（M6 当前仅有 web 搜索 provider）
├── authz/        2 文件  鉴权守卫（M6：JWT 401 语义）
├── observability 4 文件  可观测（M6：独立 obs.db 的 tables/store/recorder）
├── webui/        3 文件  WebUI 鉴权（M6：auth/middleware）
├── plans/         4 文件  计划与 Goal 服务
├── scheduler/     3 文件  Cron 解析与定时循环
├── collab/        2 文件  M5 执行生命周期
└── cli/           2 文件  命令行入口（另有 4 篇功能说明文档）
```

## 2. 历史文件设计索引（M1 起逐步追加，非当前源码清单）

> 每文件一行：**职责 → 为什么这样设计（设计动机） → 设计需求 → 涉及问题/教训**。

### config/ —— 配置域（6 文件）

| 文件 | 职责 | 为什么这样设计 | 设计需求 | 涉及问题 |
|---|---|---|---|---|
| `__init__.py` | 包入口 | 统一导出，外部 `from agentflow.config import ...` | 无业务逻辑 | — |
| `app_config.py` | `AppConfig` + `load_config()` | 全局配置唯一入口，yaml → 类型化对象；**文件缺失返回默认不报错**（容错设计，由调用方校验） | 支持路径参数/环境变量覆盖；M7 gateway 复用 | **P-014**（默认找 cwd 的 config.yaml，CLI 已传项目根路径） |
| `model_config.py` | `ModelConfig`/`ChatModelConfig` 数据类 | 配置先类型化再使用（防止散落 dict 魔法键）；字段对齐原版 | 只留"连一个对话模型"必需字段 | — |
| `models_yaml.py` | yaml models 段 → `ModelConfig`；`${ENV}` 展开 | 密钥不落 yaml（安全），环境变量展开集中在解析层 | provider 白名单校验 | **Q1-3**（models_yaml 是干嘛的 / ${ENV} 怎么展开 / parents[5] 从哪来） |
| `paths.py` | 默认路径定位（data 目录/db 文件） | 路径计算集中一处，各模块不各自拼路径 | 支持环境变量覆盖 | **Q**（路径定位规则） |

### models/ —— 模型域（3 文件）

| 文件 | 职责 | 为什么这样设计 | 设计需求 | 涉及问题 |
|---|---|---|---|---|
| `__init__.py` | 包入口 | 同上 | 无业务逻辑 | — |
| `factory.py` | `create_chat_model()` 模型工厂 | 工厂模式：配置 → 模型实例，调用方不关心具体供应商 | provider 白名单分发；默认 openai-compatible | **Q1-3**（为什么全走 OpenAI 兼容） |
| `patched_openai.py` | 供应商适配层（M1 直接返回标准 ChatOpenAI） | **扩展点预留**：不同供应商 extra body/参数别名/流式格式有差异，需要收敛层（原版同款设计） | M6 多供应商时在此补 patch | — |

### persistence/ —— 持久化域（12 文件 · 业务数据访问）

| 文件 | 职责 | 为什么这样设计 | 设计需求 | 涉及问题 |
|---|---|---|---|---|
| `__init__.py` | 包入口 | 同上 | 无业务逻辑 | — |
| `db.py` | `connect()` 连接管理 | 连接集中管理：自动建目录 + row_factory + WAL + 外键 | 其他模块不直接连 DB（铁律②） | **Q1-3**（persistence 分层） |
| `schema.py` | `SCHEMA_SQL` 业务表定义 | 表结构集中一处；当前含会话、记忆、知识、沙箱审计、goal 与 automation 表 | trace 表由 observability 独立库维护 | — |
| `bootstrap.py` | `init_db()` 建表入口 | 启动时幂等建表（CREATE IF NOT EXISTS） | CLI/测试统一入口 | — |
| `repositories.py` | `BaseRepository` 抽象基类 | 基类统一 `_execute`（SQL+commit），子类只实现 4 方法 | 表多时避免重复 SQL | **P-008**（insert→create 命名对齐） |
| `session_repositories.py` | `SessionRepository`（会话+消息 repo） | 业务记录与图状态（checkpoint）**两套存储**分开 | add_message/touch 供 CLI 与 M7 UI 用 | **Q3**（为什么先存 user 再跑图） |
| `sandbox_audit_repositories.py` | `SandboxAuditRepository`（沙箱审计 repo） | **M4 新增**：每次沙箱操作（放行/拦截）落库，可追溯 | record/query/count + BaseRepository 契约 | — |
| `timestamps.py` | `now_utc_iso()` 统一时间戳 | 全库统一 UTC ISO 字符串，**避免各模块自己格式化**（时区/格式漂移） | 时间列统一口径 | — |

### agents/ —— Agent 域（16 文件 · 核心）

| 文件 | 职责 | 为什么这样设计 | 设计需求 | 涉及问题 |
|---|---|---|---|---|
| `__init__.py` | 包入口 | 同上 | 无业务逻辑 | — |
| `thread_state.py` | `ThreadState` 图状态 | **继承 `langchain.agents.AgentState`**（原版做法，非自写 TypedDict），自带 messages 归约 | 预留 SandboxState 占位 | **Q1**（为什么继承 AgentState） |
| `checkpointer/provider.py` | `create_sqlite_checkpointer()` → SqliteSaver | 图状态持久化维度（thread_id）；**直接 `SqliteSaver(sqlite3.connect(...))`** | 同一 thread 恢复对话（验收⑤） | **P-010**（from_conn_string 3.x 返回上下文管理器） |
| `checkpointer/async_provider.py` | 异步版检查点（AsyncSqliteSaver） | **M7 gateway 预留**（FastAPI 异步场景），M1 建好对齐结构 | 同步/异步两套并存 | — |
| `lead_agent/agent.py` | `make_lead_agent()` 主 Agent | 装配器：model + system_prompt + checkpointer → 编译图 | **`create_agent` 从 langchain.agents 导入**（非 langgraph.prebuilt） | **P-009**（prebuilt 1.0.8 无 create_agent） |
| `lead_agent/prompt.py` | `format_runtime_now_for_prompt()` 时间注入 | **原版没有独立时间工具**——时间靠 system prompt 注入（格式"2026-09-28 周一 (UTC+08:00)"） | Agent 知道"今天"，不必调工具 | **P-011**（删 datetime 工具，改 prompt 注入） |
| `middlewares/__init__.py` | 中间件包入口 | **M2 新增**：照原版 agents/middlewares/ 目录 | 横向能力集中放这里 | — |
| `middlewares/title_middleware.py` | 首条消息 → 标题 → state[title] | **M2 新增**：照原版标题中间件；M2 规则截断（防 P-015 限流） | 幂等只生成一次 | **P-017**（middleware 单数） |
| `middlewares/thread_data_middleware.py` | 建线程数据目录 | **M2 新增**：照原版每个会话独立工作区 | 目录结构对齐原版命名 | — |

### tools/ —— 工具域（13 文件；下方表格是早期设计记录）

| 文件 | 职责 | 为什么这样设计 | 设计需求 | 涉及问题 |
|---|---|---|---|---|
| `__init__.py` | 包入口 | 同上 | 无业务逻辑 | — |
| `builtins/__init__.py` | 内置工具包占位 | **M2 开始填充**（原版 60+ 工具）；M1 无工具因为"时间不靠工具" | 目录结构先对齐原版 | — ||
| `tools.py` | 工具收集（lru_cache 延迟加载 + 去重 + 按 tier 排序） | **M2 新增**：照原版 get_builtin_tools 延迟收集，启动快 | 5 个工具一次加载 | **P-017**（create_agent 参数名） |
| `tool_result_store.py` | 工具结果存取（预览截断） | **M2 新增**：照原版对话只显摘要，完整结果按 thread 存 | M7 gateway 接它 | — |
| `builtins/clarification_tool.py` | 澄清工具（return_direct） | **M2 新增**：照原版 39 行模板，docstring 即说明书 | return_direct 防模型循环 | — |
| `builtins/todo_tool.py` | 会话内待办 | **M2 新增**：照原版对话级 checklist，内存存储 | add/list/update/delete | — |
| `builtins/knowledge_tool.py` | 知识库 search/read/list | **M2 新增**：照原版接口；未接 RAG（M5 接向量库） | _format_hit 格式化 | — |
| `builtins/plan_tool.py` | 计划 get/update/save | **M2 新增**：照原版计划思想，M2 内存版 | 会话内计划 | — |
| `builtins/fetch_url_tool.py` | 网页抓取 URL→文本 | **M2 新增**：学原版 web_fetch 接口，requests 简化版 | 静态页面 | — |
| `builtins/terminal_tool.py` | 沙箱终端工具（terminal_run） | **M4 新增**：一切宿主命令必须走沙箱（Noop 拒绝/Local 目录隔离）+ 审计 | 单命令 + 超时；不提供绕过沙箱路径 | — |
| `builtins/file_tools.py` | 沙箱文件工具（read_file/write_file） | **M4 新增**：文件读写统一走沙箱接口，越界由 _resolve 拦截 + 审计 | 路径必须经沙箱（不能直接 open 宿主路径） | — |
| `builtins/dispatch_tool.py` | 子代理派发工具（dispatch_subagents） | **M4 新增**：任务列表 → 并行派发 ≤3 → 按序回传；configure_dispatch_service 注入 | max_parallel 硬上限 3；未配置给友好提示 | — |

### cli/ —— 命令行入口（6 文档：main 总览 + 4 功能子文档 + __init__）

> main.py 已按功能拆分：装配（assembly.md）/ 定时子命令（automation.md）/ 长任务（goal.md）/ 对话循环（repl.md）。

| 文件 | 职责 | 为什么这样设计 | 设计需求 | 涉及问题 |
|---|---|---|---|---|
| `__init__.py` | 包入口 | 同上 | 无业务逻辑 | — |
| `main.py` | `uv run agentflow` 入口 + 对话循环 | **入口层只做装配**（配置/模型/检查点/repo），业务在 agents/；CLI 是调试入口（M7 让位 gateway） | 从任何目录启动都能找到配置；对话循环容错 | **P-009/P-010/P-013/P-014/P-015**（详见问题日志） |

## 3. 文件级说明导航（每个 py 文件一份，含结构图/导出/设计思想/实用场景/Q&A/风险）

> 目录结构与 `agentflow/` 代码目录一一对应；域级问答看下方"文档导航"，文件级细节看这里。

### config/（6）
- [app_config.py](config/app_config.md) · [model_config.py](config/model_config.md) · [models_yaml.py](config/models_yaml.md) · [paths.py](config/paths.md) · [mcp_config.py](config/mcp_config.md) · [__init__.py](config/__init__.md)

### models/（3）
- [factory.py](models/factory.md) · [patched_openai.py](models/patched_openai.md) · [__init__.py](models/__init__.md)

### persistence/（12 个源码文件；文件说明未全覆盖）
- [bootstrap.py](persistence/bootstrap.md) · [db.py](persistence/db.md) · [schema.py](persistence/schema.md) · [repositories.py](persistence/repositories.md) · [session_repositories.py](persistence/session_repositories.md) · [knowledge_repositories.py](persistence/knowledge_repositories.md) · [memory_repositories.py](persistence/memory_repositories.md) · [goal_repositories.py](persistence/goal_repositories.md) · [automation_repositories.py](persistence/automation_repositories.md) · [sandbox_audit_repositories.py](persistence/sandbox_audit_repositories.md) · [timestamps.py](persistence/timestamps.md) · [__init__.py](persistence/__init__.md)

### agents/（16）
- [thread_state.py](agents/thread_state.md)
- lead_agent/: [agent.py](agents/lead_agent/agent.md) · [prompt.py](agents/lead_agent/prompt.md) · [__init__.py](agents/lead_agent/__init__.md)
- middlewares/: [title_middleware.py](agents/middlewares/title_middleware.md) · [thread_data_middleware.py](agents/middlewares/thread_data_middleware.md) · [__init__.py](agents/middlewares/__init__.md)
- checkpointer/: [provider.py](agents/checkpointer/provider.md) · [async_provider.py](agents/checkpointer/async_provider.md) · [__init__.py](agents/checkpointer/__init__.md)
- [__init__.py](agents/__init__.md)

### tools/（13）
- [tool_catalog.py](tools/tool_catalog.md) · [tools.py](tools/tools.md) · [tool_result_store.py](tools/tool_result_store.md) · [__init__.py](tools/__init__.md)
- builtins/: [clarification_tool.py](tools/builtins/clarification_tool.md) · [todo_tool.py](tools/builtins/todo_tool.md) · [knowledge_tool.py](tools/builtins/knowledge_tool.md) · [plan_tool.py](tools/builtins/plan_tool.md) · [fetch_url_tool.py](tools/builtins/fetch_url_tool.md) · [terminal_tool.py](tools/builtins/terminal_tool.md) · [file_tools.py](tools/builtins/file_tools.md) · [dispatch_tool.py](tools/builtins/dispatch_tool.md) · [__init__.py](tools/builtins/__init__.md)

### cli/（6）
- [main.py](cli/main.md)（总览：入口/结构图/知识点/Q&A） · [__init__.py](cli/__init__.md)
- 功能子文档： [assembly.md](cli/assembly.md)（装配） · [automation.md](cli/automation.md)（定时子命令） · [goal.md](cli/goal.md)（长任务） · [repl.md](cli/repl.md)（对话循环）

### mcp/（M6，3 文件）
- [client.py](mcp/client.md)（build_server_params：stdio/sse/http 参数构建） · [tools.py](mcp/tools.md)（load_mcp_tools 同步桥接）

### community/web/（M6，5 个源码文件）
- [provider.py](community/web/provider.md)（WebSearchProvider ABC） · [registry.py](community/web/registry.md)（注册/解析） · providers/: [ddgs.py](community/web/providers/ddgs.md)（免费搜索）
- 包入口说明：[community/__init__.md](community/__init__.md)

### authz/（M6，2 文件）
- [http_guard.py](authz/http_guard.md)（AuthRequiredError 401 语义守卫）

### observability/（M6，4 文件）
- [tables.py](observability/tables.md)（表名常量） · [store.py](observability/store.md)（ObsTraceStore） · [recorder.py](observability/recorder.md)（fire-and-forget） · [__init__.py](observability/__init__.md)

### webui/（M6，3 文件）
- [auth.py](webui/auth.md)（PBKDF2 + JWT） · [middleware.py](webui/middleware.md)（WebuiAuthGuard 白名单+401） · [__init__.py](webui/__init__.md)

### knowledge/（6）
- [chunker.py](knowledge/chunker.md) · [service.py](knowledge/service.md) · [__init__.py](knowledge/__init__.md)
- embedding/: [base.py](knowledge/embedding/base.md) · [registry.py](knowledge/embedding/registry.md) · [__init__.py](knowledge/embedding/__init__.md)

### memory/（3）
- [consolidate.py](memory/consolidate.md) · [facade.py](memory/facade.md) · [__init__.py](memory/__init__.md)

### plans/（4）
- [types.py](plans/types.md) · [service.py](plans/service.md) · [resolver.py](plans/resolver.md) · [__init__.py](plans/__init__.md)

### scheduler/（3）
- [cron.py](scheduler/cron.md) · [loop.py](scheduler/loop.md) · [__init__.py](scheduler/__init__.md)

### collab/（2）
- [execution_lifecycle.py](collab/execution_lifecycle.md) · [__init__.py](collab/__init__.md)

### skills/（2）
- [loader.py](skills/loader.md) · [__init__.py](skills/__init__.md)

### subagents/（7 · M4）
- [config.py](subagents/config.md) · [registry.py](subagents/registry.md) · [executor.py](subagents/executor.md) · [__init__.py](subagents/__init__.md)
- builtins/: [general_purpose.py](subagents/builtins/general_purpose.md) · [bash_agent.py](subagents/builtins/bash_agent.md) · [__init__.py](subagents/builtins/__init__.md)

### sandbox/（6 · M4）
- [sandbox.py](sandbox/sandbox.md) · [sandbox_provider.py](sandbox/sandbox_provider.md) · [noop.py](sandbox/noop.md) · [local.py](sandbox/local.md) · [exceptions.py](sandbox/exceptions.md) · [__init__.py](sandbox/__init__.md)

### tests/（9 份说明；测试目录共有 21 个测试文件）
- [test_subagent_registry.py](tests/test_subagent_registry.md)（5 用例 → 验收点 1 注册）
- [test_subagent_parallel.py](tests/test_subagent_parallel.md)（3 用例 → 验收点 2/3 并行 + 按序）
- [test_sandbox_guard.py](tests/test_sandbox_guard.md)（7 用例 → 验收点 4 隔离 + 审计）
- [test_subagent_retry.py](tests/test_subagent_retry.md)（4 用例 → 重试语义）
- [test_tool_catalog.py](tests/test_tool_catalog.md)（6 用例 → M2 工具目录 + M4 增量）
- [test_mcp_client.py](tests/test_mcp_client.md) · [test_community_search.py](tests/test_community_search.md) · [test_auth.py](tests/test_auth.md) · [test_trace.py](tests/test_trace.md)（M6 组件测试；不是主 Agent 端到端接线测试）

### 根（1）
- [__init__.py](__init__.md)

> 生成方式：`doc/doc-code/_gen_file_docs.py`（从每个 py 文件头部注释 + 顶层符号自动生成；改代码后重跑即可同步）。

## 4. 文档导航（与代码目录一致）

| doc-code 目录 | 对应代码 | 读它解决什么问题 |
|---|---|---|
| [config/设计说明.md](config/设计说明.md) | `agentflow/config/` | 配置怎么从 yaml 变成对象？models_yaml 是干嘛的？ |
| [models/设计说明.md](models/设计说明.md) | `agentflow/models/` | 模型怎么创建？为什么都走 OpenAI 兼容？ |
| [persistence/设计说明.md](persistence/设计说明.md) | `agentflow/persistence/` | SQLite 归谁管？表和 repo 怎么分层？ |
| [agents/设计说明.md](agents/设计说明.md) | `agentflow/agents/` | 状态/检查点/主Agent/提示词怎么协作？ |
| [tools/设计说明.md](tools/设计说明.md) | `agentflow/tools/` | 为什么 M1 没有工具？ |
| [cli/设计说明.md](cli/设计说明.md) | `agentflow/cli/` | 一条对话从输入到回复怎么走完？ |

## 5. 当前边界（读源码时牢记）

```
① 核心层不反向 import 应用层（当前还没有 app/）
② 业务数据通过 persistence/ repo；LangGraph checkpoint 与 observability 独立库是专用边界
③ M6 MCP/search/auth/trace 模块目前是组件能力，尚未全部接进主 Agent 对话链路
```

## 6. 阅读顺序建议

1. 先读 `cli/设计说明.md`（一条对话的全链路）→ 建立整体感
2. 再按依赖序读：`config` → `models` → `persistence` → `agents`
3. 再读 `tools` 与 M4 子代理/沙箱，理解工具如何装配与受限执行
4. 对照本页"文件总目录"逐文件看——每个文件的"为什么"都在表里

## 7. 项目背景快问快答（非代码结构类，之前问过）

| 问题 | 结论 |
|---|---|
| EvoFlow 源码全公开？ | GitHub 公开，但许可证 PolyForm Noncommercial（商用需书面授权） |
| GLM-4.7-Flash 够用？ | 对话够用；**不能当向量模型**（chat≠embedding） |
| 本地向量不可用？ | 官方发行版 lean build 未打包 torch；用云端或 OpenAI 兼容本地服务 |
| 本地编码模型选哪个？ | Qwen3.8-27B Q4（17-19GB，M2 极限档）/ 14B Q4（~8.4GB 内存小档） |
| Bonsai-2 适合？ | 27B 三进制（5.9GB）读代码行、长任务编码不合用（SWE-bench 80.6→60.8） |
