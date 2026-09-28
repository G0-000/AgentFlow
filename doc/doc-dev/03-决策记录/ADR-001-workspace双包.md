<!-- ============================================================
  AgentFlow doc · 文档注释
  更新时间: 2026-09-28
  维护约定: 本文件内容随里程碑推进更新；接手 AI 先读标题与正文引言。
  关联项目: AgentFlow（仿写 EvoFlow，原版参照 /Users/main/EvoFlow 只读）
================================================================ -->
# ADR-001：双包 Workspace 结构

- **状态**：✅ 已采纳（M0）
- **背景**：仿写项目要不要照搬原版 `backend/ + packages/harness/` 双包结构，还是用单包简化？

## 决策

**采用双包 workspace**：

```
backend/pyproject.toml          # 应用层（gateway 预留）
packages/harness/pyproject.toml # 核心层 agentflow-harness
```

成员关系（照搬原版写法）：

```toml
# backend/pyproject.toml
[tool.uv.workspace]
members = ["packages/harness"]
[tool.uv.sources]
agentflow-harness = { workspace = true }
```

## 为什么

1. **对照学习零偏差**：原版就是 gateway（应用）+ harness（核心）分工，目录结构完全一致，读原版代码时"每一个文件都有地方落"
2. **M7 前就分好层**：未来 Gateway 应用层（FastAPI）天然属于 backend 包，不用重构
3. **原版 R1 规则的物理基础**：核心层不反向 import 应用层，双包从依赖图上就保证了单向性

## 代价与权衡

- 多一层目录，新人容易迷路
- workspace 解析比单包慢一点（可忽略）
- 单包在 M1 也完全够用——但为了学习路径一致性，值得多付这点成本

## 备选方案

- **单包 `backend/agentflow/`**：更简单，被否决（失去与原文的对照结构）
- **完全照搬三层（加 app/）**：M1 阶段 app/ 还是空的，先不建，M7 再加
