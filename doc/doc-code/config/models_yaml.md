# config/models_yaml.py — models_yaml.py

> **文件路径**: `backend/packages/harness/agentflow/config/models_yaml.py`
> **目录位置**: config → models_yaml.py
> **职责**: yaml models 段解析

## 📋 结构图

```text
┌──────────────────────────────────────────────────┐
│ load_models_from_yaml(raw dict)                  │
│   raw = { "chat": { provider/base_url/model/...}}│
│   ① 无 raw → 返回 None                          │
│   ② chat 段字段逐项读取（缺省走默认）            │
│   ③ api_key 经 _resolve_env 展开 ${ENV}          │
│   ④ 返回 ModelConfig(chat=...)                  │
└──────────────────────────────────────────────────┘
```

## 📤 关键导出

**函数**

- `load_models_from_yaml()`

## 💡 设计思想

1. 密钥不落 yaml（安全）：${ENV} 由本层统一展开，读取 .env。
2. 提供"获取 config 数据"的对外方法：app_config 只调这一个函数，
   其他模块不直接碰 yaml 细节。

## 🎯 实用场景

1. YAML 加载与校验：config.yaml → 结构化配置（models 段）
2. 多 provider 支持：zhipu/deepseek/openai 兼容 OpenAI 协议

## ⚠️ 风险点

1. ${ENV} 展开失败时返回原样字符串（调用方兜底，勿抛异常）
2. 字段缺省默认值与 model_config.py 的 dataclass 默认值需保持一致

---
_自动生成于 doc-code 规范落地（2026-09-28）。来源：models_yaml.py 头部注释 + 顶层符号。_
