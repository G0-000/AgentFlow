# models/factory.py — factory.py

> **文件路径**: `backend/packages/harness/agentflow/models/factory.py`
> **目录位置**: models → factory.py
> **职责**: 模型工厂

## 📋 结构图

```text
┌──────────────────────────────────────────────┐
│ create_chat_model(ChatModelConfig)           │
│   │                                         │
│   ├─ provider = openai-compatible → ChatOpenAI│
│   ├─ provider = openai           → ChatOpenAI│
│   ├─ provider = zhipu           → ChatOpenAI│
│   └─ 其他 → raise ValueError                 │
└──────────────────────────────────────────────┘
```

## 📤 关键导出

**函数**

- `create_chat_model()`

**常量**

- `_SUPPORTED_PROVIDERS`

## 💡 设计思想

1. 工厂模式：配置 → 模型实例，调用方不关心具体供应商。
2. 全走 OpenAI 兼容协议（zhipu/deepseek/openai 都是），
   ChatOpenAI 换 base_url + api_key 即可（Q: 为什么都走 OpenAI 兼容）。
3. 测试注入点：测试可传 mock 模型，不真调 API。

## 🎯 实用场景

1. 模型工厂：按配置创建 ChatOpenAI（zhipu/deepseek 都是 OpenAI 兼容协议）
2. 切模型只需改配置：4.5↔4.7↔DeepSeek 不用改代码（config.yaml 注释里有备选）
3. 测试注入点：测试可传 mock 模型，不真调 API

## ❓ Q&A

**Q: zhipu/deepseek 为什么都能用？**

A: 都是 OpenAI 兼容协议，ChatOpenAI 换 base_url+api_key 即可

**Q: 怎么切回 DeepSeek？**

A: config.yaml models 段 provider 改 deepseek，.env 配 DEEPSEEK_API_KEY

## ⚠️ 风险点

1. provider 白名单外直接 raise ValueError（宁可失败不静默换供应商）
2. 新增供应商 = 加一个分支 + config.yaml 注释说明，勿破坏现有分支

---
_自动生成于 doc-code 规范落地（2026-09-28）。来源：factory.py 头部注释 + 顶层符号。_
