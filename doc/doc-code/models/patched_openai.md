# models/patched_openai.py — patched_openai.py

> **文件路径**: `backend/packages/harness/agentflow/models/patched_openai.py`
> **目录位置**: models → patched_openai.py
> **职责**: OpenAI 兼容供应商适配

## 📋 结构图

```text
┌──────────────────────────────────────────────┐
│ create_openai_compatible_chat(ChatModelConfig)│
│   → ChatOpenAI(                              │
│       api_key=cfg.api_key,                   │
│       base_url=cfg.base_url,                 │
│       model=cfg.model,                       │
│       temperature=cfg.temperature,           │
│     )                                        │
└──────────────────────────────────────────────┘
```

## 📤 关键导出

**函数**

- `create_openai_compatible_chat()`

## 💡 设计思想

1. ChatOpenAI 向 base_url 发 /chat/completions 请求——
   DeepSeek/GLM/Ollama/LM Studio 都兼容此协议。
2. 独立文件 = 收敛层占位：供应商差异（如智谱 thinking extra_body,
   P-016）以后都收在这里，不污染 factory。

## 🎯 实用场景

1. 智谱流式修复：extra_body thinking disabled，让流式走 content 而非 reasoning_content（P-016）

## ⚠️ 风险点

1. 智谱流式需 extra_body thinking disabled（P-016），M6 在此补 patch
2. 当前直接返回标准 ChatOpenAI，无副作用

---
_自动生成于 doc-code 规范落地（2026-09-28）。来源：patched_openai.py 头部注释 + 顶层符号。_
