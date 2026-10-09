# persistence/memory_repositories.py

> **职责**：读写 `memories` 表中的已提取事实；事实提取和去重由 memory 层负责。

## 场景：新会话取回旧事实

用户在会话 `t_old` 说“我常用 Python”。沉淀层调用 `create(thread_id="t_old", content="用户常用 Python")`；下一次会话 `t_new` 调 `recall(thread_id=None)`，默认跨会话取最近的事实，因此可以把这条记忆交给 Agent。

```text
consolidate → MemoryRepository.create → memories
新会话 → MemoryRepository.recall(None, limit=10) → 最近 10 条事实
```

## 读代码时留意

- `thread_id` 是来源信息；不传过滤条件时会跨会话读取。
- `create()` 不负责查重；同内容去重由 `memory/consolidate.py` 处理。
- 查询按 `created_at DESC` 排序，`limit` 控制返回条数。
