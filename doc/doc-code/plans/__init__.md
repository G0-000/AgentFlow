# plans/__init__.py — plans/__init__.py

> **文件路径**: `backend/packages/harness/agentflow/plans/__init__.py`
> **目录位置**: plans → __init__.py
> **职责**: 长任务步骤计划域包入口（M5）

## 📋 结构图

```text
（无复杂调用图，仅包声明；子模块业务见各自文档）

plans/
├── types.py     PlanStep + parse_steps_json（JSON 容错解析）
├── resolver.py  topo_sort / next_ready_step（Kahn 拓扑）
└── service.py   GoalStateService（goal 状态迁移守卫）
```

## 📤 关键导出

（无顶层导出，按需 import 子模块：`from agentflow.plans.types import ...` 等）

## 💡 设计思想

1. 只做统一包声明，不承载业务逻辑——数据模型（types）、拓扑校验（resolver）、状态守卫（service）
   三者解耦，goal_loop 按需拼装。
2. 对标 evoflow/collab：原版 plans/ 实为第三方套餐绑定模块（M5 砍），本包按"计划模型 + 迁移"重组。

## 🎯 实用场景

1. 长任务装配：`agents/goal/goal_loop.py` 同时 import 本包三个子模块，串起"解析→拓扑→状态迁移"。
2. 单独测试：resolver/types 是纯函数可脱离 DB 单测；service 需注入 GoalRepository。

## ⚠️ 风险点

1. 勿在此放业务逻辑（保持包入口纯净）。
2. 三者有顺序依赖：types（PlanStep）→ resolver（消费 PlanStep）→ service（消费 repo），
   改动 types 字段需同步 resolver/service。

---
_2026-10-02 新建：M5 文档（目录 + 流程图 + 成块代码解析 + Q&A）。_
