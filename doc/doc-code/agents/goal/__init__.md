# agents/goal/__init__.py — agents/goal/__init__.py

> **文件路径**: `backend/packages/harness/agentflow/agents/goal/__init__.py`
> **目录位置**: agents → goal → __init__.py
> **职责**: 长任务（Goal）引擎域包入口（M5）

## 📋 结构图

```text
（无复杂调用图，仅包声明；子模块业务见各自文档）

agents/goal/
├── goal_state.py   状态常量 + GoalRow 内存镜像
├── goal_prompts.py preamble 规划引导词 / continue nudge
├── goal_judge.py   judge_last_reply 完成判定（两路）
└── goal_loop.py    GoalEngine 外部 while 闭环引擎
```

## 📤 关键导出

（无顶层导出，按需 import 子模块：`from agentflow.agents.goal.goal_loop import GoalEngine` 等）

## 💡 设计思想

1. 只做统一包声明，不承载业务逻辑——状态常量（state）、提示词（prompts）、判定（judge）、
   闭环引擎（loop）四层解耦，由 goal_loop 统一装配。
2. 对标 evoflow/agents/goal：原版闭环在 middleware after_model 钩子（伪 goal_graph），
   M5 改外部 while 同步闭环，对齐 CLI 同步主循环。

## 🎯 实用场景

1. 长任务入口：`cli/main.py` 经 `agentflow.agents.goal.goal_loop` 导入 GoalEngine（try 回退
   顶层 `agentflow.goal.goal_loop`），挂 --goal 与 --thread resume。
2. 单独测试：goal_prompts/goal_state 纯函数可脱离 DB 单测；goal_loop 需注入 agent/model/repo。

## ⚠️ 风险点

1. 勿在此放业务逻辑（保持包入口纯净）。
2. 包内依赖方向单向：goal_loop → judge/prompts/state → plans；勿反向 import，避免循环依赖。
3. cli 用 try/except 双路径导入（agents/goal 与顶层 goal）——两处落点需保持导出一致。

---
_2026-10-02 新建：M5 文档（目录 + 流程图 + 成块代码解析 + Q&A）。_
