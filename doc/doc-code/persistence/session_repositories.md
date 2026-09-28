# persistence/session_repositories.py — session_repositories.py

> **文件路径**: `backend/packages/harness/agentflow/persistence/session_repositories.py`
> **目录位置**: persistence → session_repositories.py
> **职责**: 会话数据访问

## 📋 结构图

```text
┌────────────────────────────────────────────────────┐
│ SessionRepository(BaseRepository)                  │
│   table_name → "sessions"                          │
│   create(thread_id, title="") → 建会话            │
│   get(thread_id) → 会话行                         │
│   delete(thread_id) → 删会话                      │
│   add_message(session_id, role, content)          │
│       → 写入 session_messages（带时间戳）          │
│   list_messages(session_id) → 按时间序消息        │
│   touch(thread_id) → 更新 updated_at              │
│   update_title(thread_id, title) → 改标题（M2）   │
└────────────────────────────────────────────────────┘
```

## 📤 关键导出

**类**

- `SessionRepository`

## 💡 设计思想

1. 会话业务记录与检查点互补：检查点存图状态二进制（恢复对话用），
   本 repo 存业务明文（会话列表/消息展示用）。
2. create 用 INSERT OR IGNORE：重复建会话幂等（不覆盖已存在会话）。
3. update_title 由 CLI 首轮后调用（M2 标题落库链路终点）。

## 🎯 实用场景

1. 会话业务记录：create/get/delete/touch/update_title
2. 消息记录：add_message/list_messages（明文，与检查点二进制互补）
3. CLI 标题落库：update_title 写 sessions.title

## ❓ Q&A

**Q: 和检查点（checkpointer）什么关系？**

A: 检查点存图状态二进制（恢复对话用）；session_repositories 存业务明文（列表展示用），两者互补

**Q: 消息存明文安全吗？**

A: 本地单机调试够用；M7 gateway 上线前需考虑脱敏

## ⚠️ 风险点

1. INSERT OR IGNORE 幂等：重复 create 不会覆盖原会话
2. 消息明文存储：本地单机调试够用；M7 gateway 上线前考虑脱敏

---
_自动生成于 doc-code 规范落地（2026-09-28）。来源：session_repositories.py 头部注释 + 顶层符号。_
