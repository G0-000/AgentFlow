<!-- ============================================================
  AgentFlow doc · doc-code 总览（代码地图 + M1 文件总目录）
  更新时间: 2026-09-30 | 关联: 代码 /Users/main/AgentFlow/backend/packages/harness/agentflow/
  用途: 与代码目录一一对应的"设计说明 + 问题总结"文档
  维护约定: M1 文件总目录随里程碑推进持续更新（每完成一个 M，追加其文件）
================================================================ -->
# doc-code —— 代码结构文档（与 agentflow/ 目录一一对应）

> 看代码前先读这里。每个子目录对应一个代码包（config/models/persistence/agents/tools/cli），
> 每份域文档 = **①文件清单 ②设计说明 ③你问过的问题总结（Q&A） ④原版对照**。
> **本页 = 总目录**：一页看清全部 52 个文件"为什么这么设计"（M1 28 + M2 11 + M3 新增 knowledge/memory/skills 三包 11 个文件）。

## 1. 代码全景（agentflow/ 52 文件 · M3）

```
backend/packages/harness/agentflow/          ← 核心层（import 叫 agentflow）
├── __init__.py                                ← 包入口（__version__）
├── config/       5 文件  配置域（yaml → 类型化对象）
├── models/       3 文件  模型域（配置 → ChatOpenAI）
├── persistence/  7 文件  持久化域（SQLite 唯一属主）
├── agents/       11 文件  Agent 域（状态/检查点/主Agent/提示词/中间件）
├── tools/        10 文件  工具域（分层/收集/结果存取 + 5 内置工具）
├── knowledge/    6 文件  知识域（chunker 切分 → embedding 向量化 → service 检索）
├── memory/       3 文件  记忆域（consolidate 合并 → facade 门面）
├── skills/       2 文件  技能域（loader 技能加载）
└── cli/          2 文件  命令行入口（对话循环）
```

## 2. M1 文件总目录（逐文件设计说明 · 后续里程碑在此持续追加）

> 每文件一行：**职责 → 为什么这样设计（设计动机） → 设计需求 → 涉及问题/教训**。

### config/ —— 配置域（5 文件）

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

### persistence/ —— 持久化域（7 文件 · SQLite 唯一属主）

| 文件 | 职责 | 为什么这样设计 | 设计需求 | 涉及问题 |
|---|---|---|---|---|
| `__init__.py` | 包入口 | 同上 | 无业务逻辑 | — |
| `db.py` | `connect()` 连接管理 | 连接集中管理：自动建目录 + row_factory + WAL + 外键 | 其他模块不直接连 DB（铁律②） | **Q1-3**（persistence 分层） |
| `schema.py` | `SCHEMA_SQL` 表定义（唯一定义处） | 表结构集中一处（对齐原版 data_layout"布局先行"）；sessions/session_messages 两张表 | M7 后按原版增表 | — |
| `bootstrap.py` | `init_db()` 建表入口 | 启动时幂等建表（CREATE IF NOT EXISTS） | CLI/测试统一入口 | — |
| `repositories.py` | `BaseRepository` 抽象基类 | 基类统一 `_execute`（SQL+commit），子类只实现 4 方法 | 表多时避免重复 SQL | **P-008**（insert→create 命名对齐） |
| `session_repositories.py` | `SessionRepository`（会话+消息 repo） | 业务记录与图状态（checkpoint）**两套存储**分开 | add_message/touch 供 CLI 与 M7 UI 用 | **Q3**（为什么先存 user 再跑图） |
| `timestamps.py` | `now_utc_iso()` 统一时间戳 | 全库统一 UTC ISO 字符串，**避免各模块自己格式化**（时区/格式漂移） | 时间列统一口径 | — |

### agents/ —— Agent 域（8 文件 · 核心）

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

### tools/ —— 工具域（2 文件 · M1 空壳）

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

### cli/ —— 命令行入口（2 文件）

| 文件 | 职责 | 为什么这样设计 | 设计需求 | 涉及问题 |
|---|---|---|---|---|
| `__init__.py` | 包入口 | 同上 | 无业务逻辑 | — |
| `main.py` | `uv run agentflow` 入口 + 对话循环 | **入口层只做装配**（配置/模型/检查点/repo），业务在 agents/；CLI 是调试入口（M7 让位 gateway） | 从任何目录启动都能找到配置；对话循环容错 | **P-009/P-010/P-013/P-014/P-015**（详见问题日志） |

## 3. 文件级说明导航（每个 py 文件一份，含结构图/导出/设计思想/实用场景/Q&A/风险）

> 目录结构与 `agentflow/` 代码目录一一对应；域级问答看下方"文档导航"，文件级细节看这里。

### config/（5）
- [app_config.py](config/app_config.md) · [model_config.py](config/model_config.md) · [models_yaml.py](config/models_yaml.md) · [paths.py](config/paths.md) · [__init__.py](config/__init__.md)

### models/（3）
- [factory.py](models/factory.md) · [patched_openai.py](models/patched_openai.md) · [__init__.py](models/__init__.md)

### persistence/（7）
- [bootstrap.py](persistence/bootstrap.md) · [db.py](persistence/db.md) · [schema.py](persistence/schema.md) · [repositories.py](persistence/repositories.md) · [session_repositories.py](persistence/session_repositories.md) · [timestamps.py](persistence/timestamps.md) · [__init__.py](persistence/__init__.md)

### agents/（11）
- [thread_state.py](agents/thread_state.md)
- lead_agent/: [agent.py](agents/lead_agent/agent.md) · [prompt.py](agents/lead_agent/prompt.md) · [__init__.py](agents/lead_agent/__init__.md)
- middlewares/: [title_middleware.py](agents/middlewares/title_middleware.md) · [thread_data_middleware.py](agents/middlewares/thread_data_middleware.md) · [__init__.py](agents/middlewares/__init__.md)
- checkpointer/: [provider.py](agents/checkpointer/provider.md) · [async_provider.py](agents/checkpointer/async_provider.md) · [__init__.py](agents/checkpointer/__init__.md)
- [__init__.py](agents/__init__.md)

### tools/（10）
- [tool_catalog.py](tools/tool_catalog.md) · [tools.py](tools/tools.md) · [tool_result_store.py](tools/tool_result_store.md) · [__init__.py](tools/__init__.md)
- builtins/: [clarification_tool.py](tools/builtins/clarification_tool.md) · [todo_tool.py](tools/builtins/todo_tool.md) · [knowledge_tool.py](tools/builtins/knowledge_tool.md) · [plan_tool.py](tools/builtins/plan_tool.md) · [fetch_url_tool.py](tools/builtins/fetch_url_tool.md) · [__init__.py](tools/builtins/__init__.md)

### cli/（2）
- [main.py](cli/main.md) · [__init__.py](cli/__init__.md)

### knowledge/（6）
- [chunker.py](knowledge/chunker.md) · [service.py](knowledge/service.md) · [__init__.py](knowledge/__init__.md)
- embedding/: [base.py](knowledge/embedding/base.md) · [registry.py](knowledge/embedding/registry.md) · [__init__.py](knowledge/embedding/__init__.md)

### memory/（3）
- [consolidate.py](memory/consolidate.md) · [facade.py](memory/facade.md) · [__init__.py](memory/__init__.md)

### skills/（2）
- [loader.py](skills/loader.md) · [__init__.py](skills/__init__.md)

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

## 4. 全项目三条铁律（任何代码都要遵守）

```
① 核心层不反向 import 应用层（agentflow/* 不得引用 app/*）——M7 才有应用层
② SQLite 唯一属主 = persistence/（其他模块不直接碰 DB）
③ 新文件命名/位置对齐原版（先看 evoflow/ 对应目录再动手）
```

## 5. 阅读顺序建议

1. 先读 `cli/设计说明.md`（一条对话的全链路）→ 建立整体感
2. 再按依赖序读：`config` → `models` → `persistence` → `agents`
3. 最后读 `tools`（M1 空壳，M2 才学工具目录）
4. 对照本页"文件总目录"逐文件看——每个文件的"为什么"都在表里

## 6. 项目背景快问快答（非代码结构类，之前问过）

| 问题 | 结论 |
|---|---|
| EvoFlow 源码全公开？ | GitHub 公开，但许可证 PolyForm Noncommercial（商用需书面授权） |
| GLM-4.7-Flash 够用？ | 对话够用；**不能当向量模型**（chat≠embedding） |
| 本地向量不可用？ | 官方发行版 lean build 未打包 torch；用云端或 OpenAI 兼容本地服务 |
| 本地编码模型选哪个？ | Qwen3.8-27B Q4（17-19GB，M2 极限档）/ 14B Q4（~8.4GB 内存小档） |
| Bonsai-2 适合？ | 27B 三进制（5.9GB）读代码行、长任务编码不合用（SWE-bench 80.6→60.8） |
