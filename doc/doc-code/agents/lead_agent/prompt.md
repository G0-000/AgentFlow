# agents/lead_agent/prompt.py — prompt.py

> **文件路径**: `backend/packages/harness/agentflow/agents/lead_agent/prompt.py`
> **目录位置**: agents → lead_agent → prompt.py
> **职责**: 系统提示词构建

## 📋 结构图

```text
┌──────────────────────────────────────────────────────┐
│ prompt.py（提示词构建）                               │
│   format_runtime_now_for_prompt(dt=None) → str       │
│     "2026-09-28 周一 (UTC+08:00)"                    │
│     （本地时间 + 中文星期 + UTC 偏移，原版同款格式）  │
│   build_lead_agent_system_prompt() → str             │
│     人格说明 + 【当前系统时间】注入                   │
└──────────────────────────────────────────────────────┘
```

## 📤 关键导出

**函数**

- `format_runtime_now_for_prompt()`
- `build_lead_agent_system_prompt()`

**常量**

- `WEEKDAY_NAMES_ZH`

## 💡 设计思想

1. 用"注入"而非"时间工具"：模型从 system prompt 直接读到当前时间，
   无需工具调用，省一轮往返（原版没有独立 datetime 工具）。
2. 提示词集中管理：不散在调用处，改提示词只改这一处。

## 🎯 实用场景

1. 系统提示词构建：时间注入（Agent 知道"今天"，不必调工具，P-011）
2. 提示词集中管理：不散在调用处，改提示词只改这一处

## ⚠️ 风险点

1. WEEKDAY_NAMES_ZH 顺序 = 周一(0)…周日(6)，与 datetime.weekday() 对齐
2. 时间格式是契约：Agent 靠它判断"今天"，改格式需同步测试

---
_自动生成于 doc-code 规范落地（2026-09-28）。来源：prompt.py 头部注释 + 顶层符号。_
