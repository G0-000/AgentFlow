# tools/builtins/clarification_tool.py — clarification_tool.py

> **文件路径**: `backend/packages/harness/agentflow/tools/builtins/clarification_tool.py`
> **目录位置**: tools → builtins → clarification_tool.py
> **职责**: 澄清工具

## 📋 结构图

```text
┌────────────────────────────────────────────────────────┐
│ @tool("ask_clarification", return_direct=True)         │
│   ask_clarification(question, clarification_type,      │
│     context, options, questions, title, category)      │
│   用途: 信息缺失/歧义/方案选择/风险确认时向用户提问     │
│   类型: missing_info | ambiguous_requirement |         │
│         approach_choice | risk_confirmation |          │
│         suggestion                                    │
│   返回: "澄清请求已发出，等待用户回答"（占位）          │
└────────────────────────────────────────────────────────┘
```

## 📤 关键导出

**函数**

- `ask_clarification_tool()`

**常量**

- `_ASK_CLARIFICATION_DESCRIPTION`

## 💡 设计思想

1. return_direct=True 必须为 True：否则 langchain create_agent 会
   把工具结果再送进模型循环——澄清问题还没答就又调一次澄清（死循环）。
2. 本工具是"占位"：真正交互由中间件/UI 处理（M2 CLI 直接打印提问），
   工具本体只负责"把提问意图结构化地表达出来"。
3. docstring 即说明书：clarification_type 枚举约束了提问类型，
   model 看到 description 就知道何时用、怎么填。

## 🎯 实用场景

1. 意图不明确时澄清：Agent 判断用户需求模糊 → return_direct=True 直接反问用户
2. 会话脊柱工具：与原版 SESSION_SYSTEM_TOOL_NAMES 对齐，属于 runtime 档系统核心
3. 工具模板学习：39 行最小工具模板（docstring 即说明书），新工具开发的起点

## ⚠️ 风险点

1. return_direct 不可改为 False（否则模型循环死循环）
2. clarification_type 枚举与 description 必须同步（模型按 description 填参）
3. M2 是占位返回；M6 接真实澄清交互时只改函数体，签名保持

---
_自动生成于 doc-code 规范落地（2026-09-28）。来源：clarification_tool.py 头部注释 + 顶层符号。_
