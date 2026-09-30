# skills/__init__.py — __init__.py

> **文件路径**: `backend/packages/harness/agentflow/skills/__init__.py`
> **目录位置**: skills → __init__.py
> **职责**: skills 域包入口（M3：SKILL.md 发现/加载/注入 prompt）

## 📋 结构图

```text
（无复杂调用图）
```

## 📤 关键导出

（无顶层导出，见结构图）

> 包入口仅一行注释声明职责，不 re-export 任何符号；实际能力在子模块 `skills/loader.py`，由 `cli/main.py` 直接 `from agentflow.skills.loader import build_skills_prompt` 使用。

## 💡 设计思想

1. 包入口保持纯净：只声明"本包负责 SKILL.md 发现/加载/注入 prompt"，不承载逻辑、不做 re-export。
2. 调用方直达子模块：外部直接从 `.loader` 导入 `build_skills_prompt`，无需经过本入口中转。

## 🎯 实用场景

1. 技能装配场景：cli/main.py 启动时经 `skills.loader.build_skills_prompt()` 把可用技能清单注入系统提示词
2. 技能扩展场景：在项目根 `skills/` 下新增技能目录 + SKILL.md，无需改本入口

## ⚠️ 风险点

1. 勿在此放业务逻辑（保持包入口纯净）
2. 新增对外导出时注意与 `cli/main.py` 的导入路径保持一致

---
_2026-09-30 新建：M3 包入口索引。_
