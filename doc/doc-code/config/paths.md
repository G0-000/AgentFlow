# config/paths.py — paths.py

> **文件路径**: `backend/packages/harness/agentflow/config/paths.py`
> **目录位置**: config → paths.py
> **职责**: 数据路径定位

## 📋 结构图

```text
┌────────────────────────────────────────────────────────┐
│ 目录层级（从本文件向上数）:                             │
│   parents[0] agentflow/config                          │
│   parents[1] agentflow                                 │
│   parents[2] harness                                   │
│   parents[3] packages                                  │
│   parents[4] backend                                   │
│   parents[5] AgentFlow  ← 项目根 (PROJECT_ROOT)         │
│                                                        │
│  default_data_dir() → 项目根/data                      │
│  default_db_path()  → 项目根/data/agentflow.db         │
└────────────────────────────────────────────────────────┘
```

## 📤 关键导出

**函数**

- `default_data_dir()`
- `default_db_path()`

**常量**

- `PROJECT_ROOT`
- `BACKEND_ROOT`

## 💡 设计思想

1. 用 __file__ 定位（而非 os.getcwd()）：保证从任何目录启动
   都能找到 data/ 与数据库，不依赖"先 cd 到项目根"（P-014 教训）。
2. 路径计算集中一处，各模块不各自拼路径。

## 🎯 实用场景

1. 路径解析唯一入口：项目根/data 目录/默认 DB 路径集中管理
2. 消除 cwd 依赖：不依赖"从哪个目录启动"（P-014 教训）

## ⚠️ 风险点

1. parents[5] 依赖目录层级；整体移动 backend/ 时需重算
2. 支持环境变量覆盖（AGENTFLOW_CONFIG_PATH 等），勿删

---
_自动生成于 doc-code 规范落地（2026-09-28）。来源：paths.py 头部注释 + 顶层符号。_
