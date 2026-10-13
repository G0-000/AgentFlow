<!-- ============================================================
  AgentFlow doc · doc-code/config（对应 agentflow/config/）
  更新时间: 2026-10-13 | 文件: 对齐-原版config.md
================================================================ -->
# config 对齐 —— AgentFlow 5 个文件 ↔ 原版 EvoFlow 36 个文件映射

> **文档目的**: 审计差异 #5 的产出。AgentFlow config/ 只有 5 个文件，原版 evoflow/config/ 有 36 个。本文**只做映射，不改任何代码**——改名/搬文件风险大，保持 pytest 164 基线不动。
> **阅读对象**: 想知道"AgentFlow 这个文件到底对应原版哪个？缺了什么？后续学到哪个里程碑能补回来？"的学习者。

## 📋 结构图

```text
原版 evoflow/config/（36 个 .py，pydantic 全家桶，SQLite 配置表）
│
├── ✅ 同名有对应（4 个，AgentFlow 已裁剪仿写）
│     paths.py          ← AgentFlow paths.py        （⚠️同名异构，根定位思路都不同）
│     models_yaml.py     ← AgentFlow models_yaml.py  （⚠️同名异构，单段 vs 多 provider）
│     app_config.py     ← AgentFlow app_config.py    （⚠️同名异构，3 字段 vs 30+ 聚合根）
│     model_config.py   ← AgentFlow model_config.py （⚠️同名异构，5 字段 vs 30 字段）
│
├── 🟡 部分对应（1 个，只裁了一半）
│     extensions_config.py（McpServerConfig 部分）← AgentFlow mcp_config.py（M6 自造裁剪）
│     ※ 其余：acp_config.py / tool_config.py ... 原版另有归属，见下方清单
│
└── ⬜ AgentFlow 未覆盖（31 个）—— 见第三节清单表，只列表不实现
```

## 一、映射总表（AgentFlow 侧 5 个文件）

| AgentFlow 文件 | 原版对应文件 | 对应程度 | 差异说明 | 后续（M8+） |
|---|---|---|---|---|
| `paths.py`（M1） | `evoflow/config/paths.py` + `data_paths.py`（两者都要！） | ⚠️同名异构 | AgentFlow 一个文件干了原版两个文件的活：①根定位 AgentFlow=`parents[5]` 项目根，原版=`Paths` 类解析 `~/.evoflow`（构造参数>EVOFLOW_HOME>home 兜底）；②数据子目录原版分 `data/app/`、`data/observability/`、`data/checkpoints/` 三库+logs，AgentFlow 只有一个 `data/agentflow.db` | 多库拆分（observability/checkpoints）时再引 `data_paths` 思路；root 策略暂不动 |
| `models_yaml.py`（M1） | `evoflow/config/models_yaml.py` | ⚠️同名异构 | AgentFlow：固定 `chat`/`embedding` 两段 → 2 个 ChatModelConfig，单向（yaml→对象）。原版：`models.providers` 嵌套分组拍平/反序列化双向、URL 推 vendor、兼容旧式平铺 list、写回 yaml | 多模型列表/多供应商分组 + 面板回写时补 `providers` 拍平逻辑 |
| `mcp_config.py`（M6） | `evoflow/config/extensions_config.py`（仅 `McpServerConfig` 类） | 🆕自造裁剪 | 不是 acp_config！AgentFlow 的字段（name/transport/command/args/env/url/headers）= 原版 McpServerConfig 去掉 enabled/oauth/description 后的子集；原版是 `dict[name→cfg]`，AgentFlow 是 list[dict] | OAuth（sse/http 远程服务器）+ skills 状态合并进 ExtensionsConfig 时补 |
| `app_config.py`（M1） | `evoflow/config/app_config.py` | ⚠️同名异构 | AgentFlow：3 字段 dataclass，读文件不报错。原版：38KB pydantic 聚合根，import 30+ 子配置段（models/extensions/memory/skills/tracing/acp/guardrails/checkpointer...），带 save_config / reload_models_from_db / SQLite 持久化 | 每加一个子域配置（memory/sandbox...）就往 AppConfig 加一个字段——照原版"聚合根"模式长 |
| `model_config.py`（M1） | `evoflow/config/model_config.py` | ⚠️同名异构 | AgentFlow：`ChatModelConfig` 5 字段（provider/base_url/model/api_key/temperature），dataclass。原版：pydantic ModelConfig ~30 字段（vendor/use 类路径/timeout/max_tokens/context_length/thinking/vision/credentials 池/fallback/健康状态...）；原版无 chat/embedding 之分，是平铺模型 list | 加 timeout/retry/fallback/凭据池时扩字段 |

**对应程度图例**: ✅同名同构 = 名字和结构都一致；⚠️同名异构 = 名字同但裁剪/思路不同；🆕自造 = 原版无同名文件、按原版某文件裁剪仿写。

## 二、关键辨析（两个最容易认错的点）

### 🔍 辨析 1：paths.py vs data_paths.py —— 原版为什么要两个文件？

| 维度 | `paths.py` | `data_paths.py` |
|---|---|---|
| 职责 | **根目录在哪**：`Paths` 类解析 `base_dir`（优先级：构造参数 > `EVOFLOW_HOME` 环境变量 > `~/​.evoflow` > cwd 兜底） | **根目录下怎么摆**：`{base_dir}/data/` 里分 `app/evoflow.db`、`observability/evoflow_observability.db`、`checkpoints/checkpoints.db`、`logs/` 四个子目录 |
| 谁依赖谁 | 独立（只做 root） | **反过来 import paths.py 的 `get_paths()`** 拿 base_dir（见 `resolve_data_base_dir()`） |
| 特色机制 | 沙箱虚拟路径 `/mnt/user-data`、Docker 主机路径 `EVOFLOW_HOST_BASE_DIR` | 旧式扁平文件名（`evoflow.db` 直接扔根目录）→ 新布局的自动迁移判定 `is_legacy_flat_*` |
| AgentFlow 现状 | `paths.py` 两者合并：`PROJECT_ROOT` + `default_data_dir()` + `default_db_path()` | 无对应——只有单库 `data/agentflow.db`，无子目录布局、无 legacy 迁移 |

**结论**：AgentFlow 的 `paths.py` ≈ 原版 `paths.py`（根定位）+ `data_paths.py`（db 路径）的极简合体，但根定位哲学根本不同——原版是"用户主目录 `~/.evoflow`"（产品化、可多实例），AgentFlow 是"项目仓库内 `data/`"（开发式）。**不要把 AgentFlow paths.py 只对到原版 paths.py**，它同时吃掉了 data_paths 的 db 路径职责。

### 🔍 辨析 2：mcp_config.py 是 M6 自造，不是原版 acp_config

| 维度 | AgentFlow `mcp_config.py` | 原版 `extensions_config.py` | 原版 `acp_config.py` | 原版 `tool_config.py` |
|---|---|---|---|---|
| 管什么 | yaml `mcp_servers` 段 → `McpServerConfig` | MCP 服务器 + skills 状态的统一配置根（含 SQLite 配置表、市场） | **ACP（Agent Client Protocol）外部 agent 子进程**：command/args/env 拉起一个完整 agent，带权限自动批准 | 工具注册表：tool/group/use（指向 provider 类路径） |
| 协议 | MCP（Model Context Protocol） | MCP（同左） | ACP——**不是 MCP，别混** | 内部工具挂载 |
| AgentFlow 关系 | —— | **真正对应物**（M6 裁剪掉 enabled/oauth/description/skills/SQLite 后仿写） | 不对应 | 不对应 |

**结论**：AgentFlow `mcp_config.py` 文件头注释写的"对标 `evoflow/config/extensions_config.py`（裁剪）"是**准确的**，字段逐一比对（transport/command/args/env/url/headers）与原版 `McpServerConfig` 一致，属 🆕自造裁剪，不是凭空造。原版 `acp_config.py` 是另一套协议（嵌入外部 agent 为工具），AgentFlow 暂无对应需求，**不要**在后续把 mcp_config 改名或往 acp 方向靠。

## 三、原版"AgentFlow 未覆盖"清单（31 个，只列表不实现）

> 按主题分组；"后续章节"指 AgentFlow `doc/doc-code/` 下已有/待建的对应域。

### A. Agent 身份与分组（对应 agents/ 域）

| 原版文件 | 一句话用途 | 对应学习章节 |
|---|---|---|
| `agents_config.py`（54KB） | 自定义 agent 全量配置 + SQLite 配置表 + 10s TTL 缓存 | M8+ agents 域（doc-code/agents/） |
| `agent_orchestration_config.py` | 编排模式：react / hybrid 预取 / local_scheduler | agents 域（编排子章） |
| `agent_resource_validation.py` | 创建/改 agent 时校验 tool/skill 标识符合法 | agents 域 |
| `agent_tags.py` | 扁平可组合标签系统（替代 team 分组） | agents 域 |
| `agent_teams.py` | **已废弃** shim（team 表已删，兼容旧迁移用） | 仅历史参考，不学 |
| `agent_avatars.py` | agent 头像文件存取（WebP/PNG 裁切） | webui/agents 域 |
| `avatar_presets.py` | 系统预设头像集（`preset:<id>` 引用） | webui/agents 域 |
| `external_agents_config.py` | config.yaml 里挂外部 agent 的配置 | agents 域（外部 agent 子章） |
| `acp_config.py` | ACP 协议外部 agent 子进程拉起 + 权限批准 | agents 域（辨析 2 已述） |
| `subagents_config.py` | subagent 系统逐 agent 覆盖配置 | doc-code/subagents/（已有）扩展 |

### B. 记忆与知识（对应 memory/ knowledge/ 域）

| 原版文件 | 一句话用途 | 对应学习章节 |
|---|---|---|
| `memory_config.py` | 记忆知识图谱抽取/扩展开关、批大小、防抖 | doc-code/memory/（已有）扩展 |
| `working_memory_config.py` | 工作记忆 read registry 同步路径表 | memory 域 |

### C. 运行时与可观测（对应 observability/ persistence/ 域）

| 原版文件 | 一句话用途 | 对应学习章节 |
|---|---|---|
| `data_paths.py` | data/ 下三库子目录布局 + 旧扁平文件名迁移 | persistence 域（见辨析 1） |
| `storage_config.py` | 主应用库路径声明（委托 data_paths） | persistence 域 |
| `observability_config.py` | SQLite 可观测库（trace/tools/model payload），默认关闭 | doc-code/observability/（已有） |
| `tracing_config.py` | LangSmith tracing 开关 + api_key/project | observability 域 |
| `checkpointer_config.py` | LangGraph 状态持久化：memory/sqlite/postgres | doc-code/memory/ 或 persistence |
| `data_retention_config.py` | SQLite/日志/checkpoint 孤儿数据定期清理策略 | observability 域 |
| `token_usage_config.py` | token 用量统计中间件开关 | observability 域 |
| `session_intent_config.py` | 会话意图 rollup（max_turns、LLM 汇总开关） | app 域 |
| `summarization_config.py` | 上下文压缩策略（主 agent + 压缩模型选择） | memory 域 |
| `title_config.py` | 线程自动生成标题开关 | app 域 |
| `tool_results_config.py` | 超大工具结果 offloading | doc-code/tools/（已有）扩展 |

### D. 工具、扩展与安全（对应 tools/ mcp/ skills/ sandbox/ 域）

| 原版文件 | 一句话用途 | 对应学习章节 |
|---|---|---|
| `extensions_config.py`（除 McpServerConfig 外） | skills 状态、OAuth、SQLite 配置表扩展 | doc-code/mcp/（已有）扩展 |
| `tool_config.py` | 工具组/工具 provider 注册表（name/group/use 类路径） | doc-code/tools/ |
| `tool_search_config.py` | 延迟工具加载（原版当前临时禁用） | tools 域 |
| `skills_config.py` | skills 发现根目录 + 额外只读根 | doc-code/skills/（已有） |
| `sandbox_config.py` | Docker 卷挂载配置（host→container 映射） | doc-code/sandbox/（已有） |
| `guardrails_config.py` | 工具调用前授权 provider（allowlist 等） | doc-code/authz/（已有）扩展 |
| `web_config.py` | Web 搜索/抽取后端可插拔配置 | doc-code/webui/ 或 tools 域 |
| `code_index_config.py` | LSP 语言服务（stdio JSON-RPC）代码索引 | knowledge 域（代码索引子章） |
| `credential_pool.py` | 多 API key 轮换/限流冷却/耗尽恢复 | models 域（与 model_config credentials 字段配套） |

## 💡 设计思想（为什么 AgentFlow 敢只留 5 个文件）

1. **学习优先级**：原版 36 个文件里大部分是"产品化后才需要"的（头像、标签、凭据池、数据保留、可观测库）。AgentFlow M1-M7 的目标是跑通"yaml→模型→对话→MCP→gateway"主干，这些横切配置全部后置。
2. **同一哲学但裁剪粒度不同**：两边都遵循"yaml 文件 → 类型化对象"（原版 pydantic，AgentFlow dataclass——刻意不引 pydantic 依赖）。
3. **不改名、不搬文件**：本审计结论是"认知对齐"而非"代码对齐"。5 个文件保持原名即与原版主干对应，后续新增子配置按原版清单逐项补，而不是现在一次性搬过来。

## 🎯 实用场景

- **场景 1**：学到某个原版文件（如 `memory_config.py`）想在 AgentFlow 里找对应 → 先查第一节总表，再查第三节清单的"对应学习章节"。
- **场景 2**：M8 要加"多 API key 轮换" → 清单里 `credential_pool.py` + `model_config.py` 的 credentials/credential_strategy 字段是原版参考。
- **场景 3**：怀疑 mcp_config 对应错了（会不会该对应 acp_config？）→ 看辨析 2，结论是 extensions_config。

## 📊 顺序执行链流程图（配置加载主链，与原版的差异）

```text
AgentFlow:                          原版 EvoFlow:
paths.py (parents[5]=项目根)         paths.py (Paths→base_dir=~/.evoflow)
  │                                  data_paths.py (data/app|obs|checkpoints 三库)
app_config.load_config()             app_config.AppConfig (pydantic 聚合 30+ 段)
  ├─ log_level                       ├─ models: list[ModelConfig] (providers 拍平)
  ├─ data_dir                        ├─ extensions (McpServerConfig dict + skills)
  └─ models_yaml(chat/embedding)     ├─ memory / tracing / guardrails / checkpointer ...
       └─ model_config(5字段)         └─ SQLite 配置表 save/reload
mcp_config(M6, 独立 list 解析)        extensions_config.McpServerConfig (含 oauth)
```

## ❓ Q&A / 知识点

**Q1：AgentFlow paths.py 到底对原版一个文件还是两个？**
A：两个都对。它把原版 `paths.py`（根定位）和 `data_paths.py`（db 子路径）合并成了一个 60 行的小文件，但根定位策略不同（项目内 vs ~/.evoflow）。见辨析 1。

**Q2：mcp_config.py 文件头写"对标 extensions_config.py"，注释可信吗？**
A：可信。逐字段比对：AgentFlow McpServerConfig = 原版 McpServerConfig 的子集（去掉了 enabled/oauth/description）。acp_config.py 是 ACP 协议另一套东西，不是对应物。

**Q3：31 个未覆盖文件里，哪些是 AgentFlow 近期最可能先补的？**
A：按已有 doc-code 域推断：tracing/observability（已有 observability 域）、sandbox 卷挂载（已有 sandbox 域）、skills 发现（已有 skills 域）。纯产品化项（头像/标签/保留策略）最后补。

**Q4：为什么不现在把 31 个文件搬过来？**
A：审计纪律——改名/搬文件会打破 pytest 164 基线，且大部分文件当前没有消费者（没有调用方就没有存在意义）。先补"有调用方"的配置段。

## ⚠️ 风险点

1. **别误读对应关系**：paths.py 不是只对 paths.py；mcp_config 不是对 acp_config。本表结论均基于实际逐行读过的文件内容。
2. **拿不准的**：`tool_config.py` 与 AgentFlow 是否将来有对应（工具注册表）——标注**待确认**，取决于后续 tools 域设计是否引入 provider 类路径注册表。
3. **清单 31 个不含 `__init__.py`**（原版包入口只做 re-export，AgentFlow 包入口风格一致，无需对齐）。
4. 本文档**不代表代码必须对齐**；后续新增文件时请回到本页更新映射表。

---
> 更新时间: 2026-10-13 ｜ 审计差异 #5 ｜ 只读审计，未修改任何代码
