# subagents/__init__.py — __init__.py

> **文件路径**: `backend/packages/harness/agentflow/subagents/__init__.py`
> **目录位置**: subagents → __init__.py
> **职责**: 子代理包入口（统一 re-export，不承载业务逻辑）

## 📋 结构图

```text
（无复杂调用图）
subagents/ 对外导出:
  config.py     → SubagentConfig
  executor.py    → SubagentStatus / SubagentResult / SubagentExecutor
                 → get/list/cleanup_background_task
  registry.py   → get_subagent_config / list_subagents / get_subagent_names
```

## 📤 关键导出

- `SubagentConfig`（config.py）
- `SubagentStatus` / `SubagentResult` / `SubagentExecutor`（executor.py）
- `get_background_task_result` / `list_background_tasks` / `cleanup_background_task`（executor.py 模块级）
- `get_subagent_config` / `list_subagents` / `get_subagent_names`（registry.py）

## 💡 设计思想

1. 包入口只 re-export，不承载逻辑（使用者 `import subagents` 一个点）。
2. M4 包小无需延迟加载；若未来 subagents 变重，再学原版 `__getattr__`。

## 🎯 实用场景

1. 派发工具装配：dispatch_tool.py:49 从这里 import `SubagentExecutor, get_subagent_config, get_subagent_names`。
2. CLI 启动信息：cli/main.py:91 import `get_subagent_names` 打印已注册子代理名单。
3. 测试：test_subagent_registry / retry / parallel 从这里 import 执行器与查表函数。

## ⚠️ 风险点

1. 勿在此放业务逻辑（保持包入口纯净）。
2. 新增导出记得加进 `__all__`（否则 `from subagents import *` 拿不到）。
3. 依赖单向：builtins 只依赖 config，registry 依赖 builtins，executor 依赖 config——保持单向，勿成环。

---
_2026-10-01 M4 补齐：目录 + 顺序执行链流程图 + 成块代码解析（+Q&A）。_
