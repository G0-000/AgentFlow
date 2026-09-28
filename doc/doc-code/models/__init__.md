# models/__init__.py — __init__.py

> **文件路径**: `backend/packages/harness/agentflow/models/__init__.py`
> **目录位置**: models → __init__.py
> **职责**: 模型域包入口

## 📋 结构图

```text
（无复杂调用图）
```

## 📤 关键导出

（无顶层导出，见结构图）

## 💡 设计思想

1. 只做统一导出/包声明，不承载业务逻辑。

## 🎯 实用场景

1. 切换模型供应商场景：zhipu↔deepseek↔openai 兼容协议，改配置即切
2. 测试 mock 场景：不真调 API 也能验证装配逻辑

## ⚠️ 风险点

1. 勿在此放业务逻辑（保持包入口纯净）

---
_自动生成于 doc-code 规范落地（2026-09-28）。来源：__init__.py 头部注释 + 顶层符号。_
