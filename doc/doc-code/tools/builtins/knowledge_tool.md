# tools/builtins/knowledge_tool.py — knowledge_tool.py

> **文件路径**: `backend/packages/harness/agentflow/tools/builtins/knowledge_tool.py`
> **目录位置**: tools → builtins → knowledge_tool.py
> **职责**: 知识库检索工具

## 📋 结构图

```text
┌────────────────────────────────────────────────────────────┐
│ _format_hit(h, index) -> str                               │
│   单条命中格式化：标题/分数/摘要（照原版 _format_hit）     │
│                                                             │
│ knowledge_tool(action, query, doc_id, kb_name) -> str      │
│   @tool("knowledge", return_direct=True)                   │
│   search → 关键词/自然语言检索                             │
│   read   → 按 doc_id 读文档                                │
│   list   → 列出知识库文档（kb_name 可选）                  │
│   （M2 占位：返回"未接入"明确提示）                        │
└────────────────────────────────────────────────────────────┘
```

## 📤 关键导出

**函数**

- `knowledge_tool()`

**常量**

- `_KNOWLEDGE_DESCRIPTION`

## 💡 设计思想

1. 接口契约先行：search/read/list 三动作 + 参数名与返回格式固定，
   即使 M2 未接 RAG，调用方（模型/CLI/测试）的用法不会变；
   M5 只换函数体内部实现（接向量库），签名零改动。
2. _format_hit 统一命中格式：后续所有来源（向量库/全文）都走它，
   避免各工具各写各的展示格式（照原版）。
3. 占位也返回"明确提示"而非空串：防止模型误以为检索到了结果
   而编造内容（幻觉防控）。

## 🎯 实用场景

1. 知识库检索（M5 接入前占位）：search/read/list 接口先行，_format_hit 统一命中格式
2. 接口契约先行：工具名称/参数/返回格式固定，后续换向量库实现不动调用方

## ⚠️ 风险点

1. 函数签名（action/query/doc_id/kb_name）是契约，M5 接 RAG 时不可改
2. 占位提示文案会被模型直接转述给用户，措辞要准确（含"设置中添加向量模型"指引）
3. _format_hit 字段取值顺序（title→fileName→docId）对齐原版，勿乱改

---
_自动生成于 doc-code 规范落地（2026-09-28）。来源：knowledge_tool.py 头部注释 + 顶层符号。_
