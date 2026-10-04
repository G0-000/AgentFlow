# collab/__init__.py — __init__.py

> **文件路径**: `backend/packages/harness/agentflow/collab/__init__.py`
> **目录位置**: collab → __init__.py
> **职责**: 协作域包入口（M5 仅保留执行生命周期一个文件）

## 📋 结构图

```text
（无复杂调用图）

collab/（M5 唯一文件）
  └─ execution_lifecycle.py  执行生命周期 7 阶段常量 + 标签 + 意图识别
```

## 📤 关键导出

（无顶层导出；collab/ 包 M5 只此一个业务文件，见 [execution_lifecycle.md](./execution_lifecycle.md)）

## 💡 设计思想

1. 对标 evoflow/collab/（50+ 文件：supervisor/peer/org/App/推送/观测），M5 全砍，
   只学 `execution_lifecycle.py` 一个文件，其余留 M7。
2. 只做统一包声明，不承载业务逻辑。

## 🎯 实用场景

1. 协作域扩展场景：M7 接 supervisor/peer gate 时在此包内新增文件
2. 执行生命周期展示场景：UI/前端按 LIFECYCLE_* 稳定 key 映射中文标签

## ⚠️ 风险点

1. 勿在此放业务逻辑（保持包入口纯净）
2. M5 collab/ 包内仅有 execution_lifecycle.py 一个业务文件，新增文件前先确认里程碑

---
_2026-10-02 新建：M5 文档（目录 + 流程图 + 成块代码解析 + Q&A）。_
