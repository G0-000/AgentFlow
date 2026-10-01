# subagents/builtins/__init__.py — __init__.py

> **文件路径**: `backend/packages/harness/agentflow/subagents/builtins/__init__.py`
> **目录位置**: subagents → builtins → __init__.py
> **职责**: 内置子代理注册表（代码侧默认配置集中一处）

## 📋 结构图

```text
（无复杂调用图）
BUILTIN_SUBAGENTS: dict[str, object]
  "general-purpose" → GENERAL_PURPOSE_CONFIG（general_purpose.py）
  "bash"            → BASH_AGENT_CONFIG（bash_agent.py）
  registry 查表键 = 子代理 name
```

## 📤 关键导出

- `BUILTIN_SUBAGENTS`：内置子代理注册表（name → config；标注 `dict[str, object]` 规避导入环）
- `GENERAL_PURPOSE_CONFIG`（general_purpose.py）
- `BASH_AGENT_CONFIG`（bash_agent.py）

## 💡 设计思想

1. 代码侧默认配置集中一处（原版同款）；后续 M5 再学"agents 目录持久化配置覆盖"。
2. M4 只内置 2 个最小子代理，够验证"派发-并行-回传"链路。
3. 注册表键名必须等于 `config.name`（registry.get_subagent_config 按 name 查表）。

## 🎯 实用场景

1. registry.py:45 import `BUILTIN_SUBAGENTS`，过滤 `isinstance(cfg, SubagentConfig)` 后构建 `_SUBAGENT_MAP`。
2. 新增子代理 = 加配置文件 + 在此注册一条（键名 = config.name）。

## ⚠️ 风险点

1. 注册表键与 `config.name` 不一致 → registry 查不到（静默失败）。
2. `dict[str, object]` 是刻意的防环标注，registry 层再收类型；勿在 builtins 里 import registry。

---
_2026-10-01 M4 补齐：目录 + 顺序执行链流程图 + 成块代码解析（+Q&A）。_
