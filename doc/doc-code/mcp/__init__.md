# mcp/__init__.py — __init__.py

> **文件路径**: `backend/packages/harness/agentflow/mcp/__init__.py`
> **目录位置**: mcp → __init__.py
> **职责**: MCP 外部服务器接入包入口（M6）

## 📋 结构图

```text
（无复杂调用图）
```

## 📤 关键导出

（无顶层导出，见结构图）

## 💡 设计思想

1. 只做包声明，不承载业务逻辑；MCP 配置解析在 `config/mcp_config.py`，
   参数字典构建在 `mcp/client.py`，工具加载在 `mcp/tools.py`。

## 🎯 实用场景

1. MCP 外部服务器接入场景：config.yaml 配 mcp_servers 段 → load_mcp_tools 产出 BaseTool 列表
2. 可选项降级场景：无配置 / 连接失败一律返回 []，不阻断主 Agent 装配

## ⚠️ 风险点

1. 勿在此放业务逻辑（保持包入口纯净）

---
_2026-10-05 M6 新增：目录 + 结构图 + 流程图 + 成块代码解析（参数逐条表）+ Q&A。_
