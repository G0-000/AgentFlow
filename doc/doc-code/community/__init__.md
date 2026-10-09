# community/__init__.py

> **路径**：`backend/packages/harness/agentflow/community/__init__.py`  
> **作用**：标记第三方集成包；M6 的具体能力位于 `community/web/`。

## 阅读重点

这个文件没有运行逻辑，也没有统一导出搜索 API。要理解当前搜索适配器，按这个顺序读：

1. [provider.py](web/provider.md)：provider 的统一接口。
2. [registry.py](web/registry.md)：注册、发现和选择后端。
3. [ddgs.py](web/providers/ddgs.md)：DuckDuckGo 实现。

## 场景

应用代码显式调用 `resolve_search_backend()` 选择后端，再取 provider 并调用其 `search()`；当前主 Agent 装配尚未调用这条链路。
