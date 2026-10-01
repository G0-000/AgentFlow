# sandbox/__init__.py — __init__.py

> **文件路径**: `backend/packages/harness/agentflow/sandbox/__init__.py`
> **目录位置**: sandbox → __init__.py
> **职责**: 沙箱包入口——re-export 全部公共符号（接口/实现/异常/单例管理）

## 📋 结构图

```text
（无复杂调用图）
```

## 📤 关键导出

按 `__all__` 如实列出（源码 __init__.py:54-69）：

**接口与实现类**

- `Sandbox`（沙箱抽象基类）
- `SandboxProvider`（提供者抽象基类）
- `NoopSandbox` / `NoopSandboxProvider`（默认全拒绝）
- `LocalSandbox` / `LocalSandboxProvider`（目录隔离，CLI 生产装配）

**异常类**

- `SandboxError` / `SandboxPermissionError` / `SandboxFileError` /
  `SandboxFileNotFoundError` / `SandboxCommandError`

**单例管理函数**

- `get_sandbox_provider()` / `set_sandbox_provider(p)` / `reset_sandbox_provider()`

## 💡 设计思想

1. 包入口 re-export 全部公共符号——工具层一个 `from agentflow.sandbox import …`
   拿全（terminal_tool.py:45、file_tools.py:46 均如此）。
2. 单例函数直接导出：工具层只调 `get_sandbox_provider()` 拿当前沙箱，不感知全局是谁。

## 🎯 实用场景

1. 工具层接线：terminal_run/read_file/write_file 经此入口取 `SandboxError` 与
   `get_sandbox_provider`。
2. CLI 装配：cli/main.py:90 经此入口 import `LocalSandboxProvider` +
   `get/set_sandbox_provider`，:176 完成注入。
3. 测试注入：test_sandbox_guard.py:9-18 经此入口拿全套符号做隔离测试。

## ⚠️ 风险点

1. 新增实现类记得在此导出并补 `__all__`——否则工具层 import 不到。
2. 单例函数名（get/set/reset_sandbox_provider）保持稳定——工具层与 CLI 都按名依赖。

---
_2026-10-01 M4 补齐：目录 + 顺序执行链流程图 + 成块代码解析（+Q&A）。_
