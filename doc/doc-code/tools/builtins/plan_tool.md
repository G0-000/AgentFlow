# tools/builtins/plan_tool.py — plan_tool.py

> **文件路径**: `backend/packages/harness/agentflow/tools/builtins/plan_tool.py`
> **目录位置**: tools → builtins → plan_tool.py
> **职责**: 计划工具

## 📋 结构图

```text
┌────────────────────────────────────────────────────────────┐
│ _plan: dict —— 会话内计划存储（内存；原版是文档）           │
│                                                             │
│ plan_tool(action, plan_text) -> str                        │
│   @tool("plan", return_direct=True)                        │
│   get    → 读取当前计划（无则提示可 update 写入）           │
│   update → 写入计划内容（plan_text 必填）                  │
│   save   → 同 update（语义区分：保存到持久层，M2 同内存）   │
└────────────────────────────────────────────────────────────┘
```

## 📤 关键导出

**函数**

- `plan_tool()`

**常量**

- `_PLAN_DESCRIPTION`

## 💡 设计思想

1. 计划是"任务级"能力：用户要求分步执行时，模型可把步骤写进
   计划再逐项推进，避免上下文里反复重复计划全文。
2. M2 内存 dict 够用：单会话内读写；M3+ 落盘（文件/DB）时
   只改存储实现，工具签名不动。
3. save 与 update 语义区分：update=改内存内容，save=持久化
   （M2 两者同实现，为 M3+ 预留接口语义）。

## 🎯 实用场景

1. 会话内计划：get/update/save 管理对话中的计划（如学习计划分步）
2. 计划持久化后续：M2 内存版，M3+ 可落 SQLite 或文件

## ⚠️ 风险点

1. _plan 是模块级内存 dict：进程重启即清空（当前设计，调试够用）
2. update 无 plan_text 时返回错误提示，不可静默覆盖
3. save/update 语义在 M3+ 持久化时可能拆分，改动需同步 description

---
_自动生成于 doc-code 规范落地（2026-09-28）。来源：plan_tool.py 头部注释 + 顶层符号。_
