# config/model_config.py — model_config.py

> **文件路径**: `backend/packages/harness/agentflow/config/model_config.py`
> **目录位置**: config → model_config.py
> **职责**: 模型配置类型

## 📋 结构图

```text
┌──────────────────────────────────────────────┐
│ ModelConfig                                  │
│   └── chat: ChatModelConfig                  │
│         provider  : 供应商类型（分发依据）     │
│         base_url  : API 地址                  │
│         model     : 模型名                    │
│         api_key   : 密钥（支持 ${ENV}）       │
│         temperature: 采样温度                 │
└──────────────────────────────────────────────┘
```

## 📤 关键导出

**类**

- `ChatModelConfig`
- `ModelConfig`

## 💡 设计思想

1. 配置先类型化再使用：防止散落 dict 魔法键（字段对齐原版）。
2. dataclass 足够（无需 pydantic 校验，M1 保持最简）。

## 🎯 实用场景

1. 模型配置数据结构：chat 模型/provider/base_url/api_key 的字段定义
2. 环境变量展开：api_key 支持 ${ENV} 从 .env 读取，密钥不落 yaml

## ⚠️ 风险点

1. api_key 走 ${ENV} 展开（models_yaml 处理），勿在 yaml 明文写密钥
2. 新增字段需同步 models_yaml.py 解析与 config.yaml 示例

---
_自动生成于 doc-code 规范落地（2026-09-28）。来源：model_config.py 头部注释 + 顶层符号。_
