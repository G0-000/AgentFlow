# community/web/providers/__init__.py — __init__.py

> **文件路径**: `backend/packages/harness/agentflow/community/web/providers/__init__.py`
> **目录位置**: community/web/providers → __init__.py
> **职责**: 搜索后端实现包入口（M6：ddgs 后端目录声明，无业务逻辑）

## 📋 结构图

```text
community/web/providers/                 ← 具体搜索后端实现目录
│
├── __init__.py                          ← 本文件（包入口，仅声明，无业务逻辑）
│
└── ddgs.py                              ← DDGSWebSearchProvider（免费无 key，auto→bing 双后端兜底）
                                          → 见 doc-code/community/web/providers/ddgs.md
```

## 📤 关键导出

（无顶层导出——本 `__init__.py` 仅作包声明；业务符号从 `ddgs.py` 按需 import：
`from agentflow.community.web.providers.ddgs import DDGSWebSearchProvider` 等。）

## 💡 设计思想

1. **包入口纯净**：`providers/__init__.py` 不 re-export 具体后端类，避免 `import community.web.providers`
   就触发 ddgs 依赖加载——保持"import 无副作用、懒加载"的纪律（与 `community/web/__init__.py` 同款）。
2. **一后端一文件**：每个搜索引擎一个实现文件（当前仅 `ddgs.py`）——未来接 tavily/bocha 就是
   新增 `tavily.py`/`bocha.py` 并注册，`providers/__init__.py` 不动。
3. **注册由 registry 统一管理**：后端实例的"何时加载、按什么优先级解析"全在
   `community/web/registry.py`（懒加载 + RLock）——providers 目录只负责"实现契约"，不负责"怎么选"。

## 🎯 实用场景

1. **加新搜索后端**：在 `providers/` 新增 `xxx.py`（实现 `WebSearchProvider.search` 统一契约），
   在 `registry.ensure_providers_loaded` 注册即可——上层 resolve/get 逻辑零改动。
2. **上层取搜索能力**：走 `registry`（`resolve_search_backend` → `get_provider`）拿实例，
   不直接 import `providers/` 下的具体类——便于测试注入与后端切换。

## ⚠️ 风险点

1. **勿在本 `__init__.py` re-export**：否则 import `community.web.providers` 即连带加载 ddgs，
   破坏懒加载纪律（registry 需要显式触发才加载后端）。
2. **后端必须遵守统一契约**：`{"success": bool, "data": {"web": [...]}}` 形状由 `provider.py` 定义——
   新后端若自造形状，上层 Agent 工具解析会失败（契约校验在 ddgs 测试里被显式断言）。

---
_2026-10-05 M6 新增：目录 + 结构图 + 流程图 + 成块代码解析（参数逐条表）+ Q&A。_
