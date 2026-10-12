# community/web/__init__.py — __init__.py

> **文件路径**: `backend/packages/harness/agentflow/community/web/__init__.py`
> **目录位置**: community/web → __init__.py
> **职责**: 网页搜索集成包入口（M6：provider 抽象 + registry 注册中心 + ddgs 后端）

## 📋 结构图

```text
agentflow/community/                     ← community/ 顶层包
│
└── web/                                 ← community/web/ 网页搜索子包
    │
    ├── __init__.py                      ← 本文件（包入口，仅声明，无业务逻辑）
    ├── provider.py                      ← WebSearchProvider 抽象基类 + 统一契约
    │                                     → 见 doc-code/community/web/provider.md
    ├── registry.py                      ← Provider 注册中心（懒加载 + RLock + 后端解析）
    │                                     → 见 doc-code/community/web/registry.md
    │
    └── providers/                       ← community/web/providers/ 具体后端实现目录
        ├── __init__.py
        └── ddgs.py                      ← DDGSWebSearchProvider（免费无 key，双后端兜底）
                                         → 见 doc-code/community/web/providers/ddgs.md
```

## 📤 关键导出

（无顶层导出——本 `__init__.py` 仅作包声明，业务符号从子模块按需 import：
`from agentflow.community.web.registry import resolve_search_backend` 等。）

## 💡 设计思想

1. **包入口纯净**：`community/web/__init__.py` 不承载业务逻辑，只声明这是"网页搜索集成"包；
   不在这里 re-export，避免 import 即触发 registry 副作用（懒加载由 registry 自己管）。
2. **三层层级划分**：
   - `community/`——顶层社区集成包（目前只挂 `web/`，将来可扩 `slack/`/`github/` 等第三方集成）；
   - `community/web/`——网页搜索域，放"抽象基类 provider.py + 注册中心 registry.py"两个骨架文件；
   - `community/web/providers/`——具体后端实现目录，每个搜索引擎一个文件（当前仅 `ddgs.py`）。
3. **骨架与实现分离**：换/加搜索引擎只动 `providers/` 里的文件，`provider.py`/`registry.py` 不动——
   符合 WebSearchProvider 统一契约 + registry 字典注册的扩展点设计。

## 🎯 实用场景

### 端到端场景：Agent 会话里的一次网页搜索（先看这条）

> 本目录的全部代码，最终只为一个目的：**Agent 在会话里调搜索，把网页/API 返回的结构化数据喂给 Agent**。
> 全程没有"打开网页"——搜索结果是文本数据进 LLM 上下文，模型自己组织回答。

```
你（REPL）：帮我查下"2026 杭州亚运会"相关新闻
    ↓ Agent 决定用搜索工具
上层工具 → registry.resolve_search_backend()      ← 选中 ddgs（自动序第一，免费无 key）
        → get_provider("ddgs").search("2026 杭州亚运会", limit=5)
        → DDGSWebSearchProvider.search             ← DuckDuckGo 真实搜索（auto→bing 兜底）
        → {"success": True, "data": {"web": [{title,url,description,position} × 5]}}
        ↓ 结构化数据回给 Agent（进 LLM 上下文）
Agent：基于 5 条摘要组织回答，附链接；若 success=False 则把 error 文本回给模型/用户
```

**一句话定位**：`community/web/` = "Agent 的搜索能力插座"（调网页搜索/API → 数据进对话）；
`community/` 顶层将来平行扩 `github/`/`slack/` 是"Agent 调其他平台 API 的插座"，与搜索平行、互不增强。

### 开发者场景

1. **接入新搜索后端**：在 `community/web/providers/` 新增 `xxx.py`，实现 `WebSearchProvider` 子类，
   在 `registry.ensure_providers_loaded` 里注册即可（上层零改动）。
2. **上层取搜索能力**：`from agentflow.community.web.registry import resolve_search_backend, get_provider`
   拿到当前后端实例调 `search()`——不直接碰 `providers/` 下的具体类。

## ⚠️ 风险点

1. **勿在本 `__init__.py` re-export 业务符号**：否则 import `community.web` 即触发 registry/ddgs 依赖，
   破坏"import 无副作用、懒加载"的设计。
2. **`providers/` 与 `community/` 层级别混**：具体后端永远放在 `community/web/providers/`（web 域内），
   不要直接丢进 `community/` 根下——`community/` 是跨域顶层包，将来会挂多个子域。

---
_2026-10-05 M6 新增：目录 + 结构图 + 流程图 + 成块代码解析（参数逐条表）+ Q&A。_
_2026-10-12 补充：实用场景重排——新增"Agent 会话端到端场景"（搜索=调 API 返数据给 Agent，非打开网页）。_
