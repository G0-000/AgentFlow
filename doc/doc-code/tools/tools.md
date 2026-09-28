# tools/tools.py — tools.py

> **文件路径**: `backend/packages/harness/agentflow/tools/tools.py`
> **目录位置**: tools → tools.py
> **职责**: 工具收集模块（延迟加载 + 去重 + 按Tier排序）

## 📋 结构图

```text
┌────────────────────────────────────────────────────────────┐
│ get_builtin_tools() -> tuple[BaseTool, ...]                 │
│   @lru_cache：首次调用才导入 5 个工具模块，加快项目启动速度  │
│   返回内置工具元组：(clarification, todo, knowledge, plan,  │
│                     fetch_url)                              │
│                                                             │
│ _finalize_tool_catalog(tools) -> list[BaseTool]             │
│   工具目录后置处理：                                         │
│     ① 根据工具 name 去重，保留第一个出现的工具定义          │
│     ② 依据 ToolTier 优先级顺序进行排序（runtime → core →    │
│        workspace → …）                                      │
│                                                             │
│ get_available_tools() -> list[BaseTool]                     │
│   对外入口：输出最终挂载给 Agent 使用的工具列表             │
└────────────────────────────────────────────────────────────┘
```

## 📤 关键导出

**函数**

- `get_builtin_tools()`
- `get_available_tools()`

## 💡 设计思想

1. 参考文档：doc/doc-dev/01-里程碑/M2-工具与中间件.md §2
2. 原版 EvoFlow 设计动机：工具数量庞大（50+），启动时一次性全部 import
   会拖慢启动；使用 @lru_cache + 函数内部 import 实现延迟加载：
   仅第一次调用 get_builtin_tools 时加载，后续直接复用缓存。
3. M2 精简改造：移除退役工具表、工具别名、社区工具、沙箱相关逻辑，
   只保留核心收集流程。

## 🎯 实用场景

1. Agent 启动装配：get_available_tools() 输出最终挂载给 Agent 的工具列表（CLI/未来 gateway 共用）
2. 工具开发回归：新增工具后测试去重与 tier 排序是否生效
3. 性能敏感场景：lru_cache 延迟加载避免启动时 import 全部工具模块（requests 等重依赖）
4. 原版对齐演示：对照 EvoFlow 原版 tools.py（566 行）理解"收集-去重-排序"管线

## ❓ Q&A

**Q: 为什么延迟加载？**

A: 5 个工具模块含 requests 等重依赖，模块级 import 拖慢 CLI 启动；lru_cache 保证只加载一次，之后复用

**Q: lru_cache 怎么清？**

A: 修改工具定义后需重启进程（或手动 cache_clear）；调试期重启最省事

## ⚠️ 风险点

1. TOOL_TIER_ORDER 元组顺序直接影响工具排序结果，不可随意调整
2. get_builtin_tools 带有 lru_cache 缓存；修改工具定义后，需要清空缓存才能生效
3. 去重规则：按工具 name 字段，保留最先出现的工具，丢弃后续同名工具

---
_自动生成于 doc-code 规范落地（2026-09-28）。来源：tools.py 头部注释 + 顶层符号。_
