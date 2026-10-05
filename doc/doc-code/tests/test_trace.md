# tests/test_trace.py — test_trace.py

> **文件路径**: `backend/packages/harness/tests/test_trace.py`
> **目录位置**: tests → test_trace.py
> **职责**: 可观测链路测试（M6 验收点 4）——按 run_id 查完整 span 链路 + recorder 异步落库

## 📑 目录

- [📋 结构图](#📋-结构图)
- [📤 关键导出](#📤-关键导出)
- [💡 设计思想](#💡-设计思想)
- [🧩 代码解析（成块对照 test_trace.py）](#🧩-代码解析成块对照-test_tracepy)
- [⚠️ 风险点](#⚠️-风险点)

## 📋 结构图

```text
tests/test_trace.py（8 用例 → 验收点 4：可观测）
├── 建表（1）
│   └── test_create_tables_idempotent           建表两次幂等
├── store 同步链路（4）
│   ├── test_insert_and_get_run_roundtrip       run 写查往返
│   ├── test_full_chain_query_by_run_id         1 run + 3 span 按序查（核心）
│   ├── test_query_events_other_run_isolated    run 间隔离
│   └── test_recorder_fire_and_forget_writes    异步落库文件库可见
└── 工具（2）
    ├── test_new_run_id_unique                  50 个 run_id 唯一
    └── test_table_names_prefixed               表名前缀 agentflow_obs_

被测对象: agentflow/observability/{tables,store,recorder}.py
```

## 📤 关键导出

无独立导出（测试文件）。覆盖的被测契约：

- `ObsTraceStore`：建表幂等 / insert_run / insert_event / get_run / query_events（按 started_at 升序）
- `ObservabilityRecorder`：record_run / record_trace_event（fire-and-forget 后台线程）
- `new_run_id`：`r_` + 6 字节随机 hex
- `ObservabilityTable`：`agentflow_obs_runs` / `agentflow_obs_trace_events`

## 💡 设计思想

1. **验收点 4 的"完整链路"模型**：1 run（根）+ N events（span）——模型调用/工具调用/中间件各记一条，按 run_id 一查即得完整时序（`query_events` 按 started_at 升序断言）。
2. **内存库测同步路径**：store 直测用 `":memory:"`——快且隔离；**recorder 异步路径用临时文件库**（P-020 教训：线程本地连接下内存库每线程独立，主线程查不到后台线程的写入）。
3. **fire-and-forget 轮询等待**：异步落库不可 join，测试用"轮询直到可见（上限 5s）"证明最终一致。
4. **meta JSON 往返**：写入 dict → 存 JSON → 查询解析回 dict——meta 字段的序列化/反序列化被显式断言。

## 🧩 代码解析（成块对照 test_trace.py）

### 块 1：完整链路查询（验收点 4 核心）

```python
def test_full_chain_query_by_run_id():
    """验收点 ④：模拟一次对话 = 1 run + 模型 span + 工具 span，按 run_id 查完整链路。"""
    store = ObsTraceStore(":memory:")
    store.insert_run(run_id="r-chain", thread_id="t1", started_at="T0", duration_ms=50.0)
    store.insert_event(run_id="r-chain", kind="model_call", span_name="chat", started_at="T1", duration_ms=30.0, meta={"tokens": 42})
    store.insert_event(run_id="r-chain", kind="tool_call", span_name="todo_add", started_at="T2", duration_ms=10.0, meta={"tool": "todo"})
    store.insert_event(run_id="r-chain", kind="model_call", span_name="chat2", started_at="T3", duration_ms=10.0)

    events = store.query_events("r-chain")
    assert [e["span_name"] for e in events] == ["chat", "todo_add", "chat2"]  # 按 started_at 升序
    assert [e["kind"] for e in events] == ["model_call", "tool_call", "model_call"]
    assert events[0]["meta"]["tokens"] == 42
    assert events[0]["duration_ms"] == 30.0
    # 完整链路：run 根 + 3 span
    assert store.get_run("r-chain")["status"] == "ok"
    assert len(events) == 3
```

**整块解析**（参数逐条）：

| 步骤 | 数据 | 断言点 |
|---|---|---|
| `insert_run(run_id="r-chain", thread_id="t1", ...)` | 根记录 | 一次对话 = 1 run |
| `insert_event(kind="model_call", span_name="chat", duration_ms=30.0, meta={"tokens":42})` | 模型调用 span | kind/span_name/meta/耗时 |
| `insert_event(kind="tool_call", span_name="todo_add", ...)` | 工具调用 span | 中间插一条工具 span |
| `insert_event(kind="model_call", span_name="chat2", ...)` | 第二轮模型调用 | 完整对话含多次模型调用 |
| `query_events("r-chain")` | 查询 | **按 started_at 升序**（T1/T2/T3）返回 3 条 |
| `events[0]["meta"]["tokens"] == 42` | meta 往返 | dict → JSON 存 → dict 查 |
| `get_run("r-chain")["status"] == "ok"` | 根记录状态 | run 存在且 ok |

**关键细节**：`"T0"/"T1"/"T2"/"T3"` 是字典序即时间序的占位符——SQL `ORDER BY started_at ASC` 对字符串排序，占位符刻意选字典序=时间序，让断言无歧义。

### 块 2：recorder 异步落库

```python
def test_recorder_fire_and_forget_writes(tmp_path):
    """recorder 异步落库：文件库可见（后台线程写，主线程查）。"""
    store = ObsTraceStore(tmp_path / "obs.db")
    rec = ObservabilityRecorder(store)
    rid = new_run_id()
    rec.record_run(run_id=rid, thread_id="t1", started_at="T0", duration_ms=1.0)
    rec.record_trace_event(run_id=rid, kind="model_call", span_name="chat", started_at="T1", duration_ms=2.5)

    # fire-and-forget 是异步：轮询等待后台线程落库（上限 5s）
    deadline = time.time() + 5
    while time.time() < deadline:
        if store.get_run(rid) and store.query_events(rid):
            break
        time.sleep(0.05)
    run = store.get_run(rid)
    events = store.query_events(rid)
    assert run is not None
    assert run["status"] == "ok"
    assert len(events) == 1
    assert events[0]["span_name"] == "chat"
    assert events[0]["duration_ms"] == 2.5
```

**整块解析**（参数逐条）：

| 步骤 | 动作 | 作用 |
|---|---|---|
| `ObsTraceStore(tmp_path / "obs.db")` | 文件库 | **必须文件库**——内存库每线程独立（P-020），后台线程写入主线程不可见 |
| `rec.record_run(...)` + `record_trace_event(...)` | 异步提交 | 各起 daemon 线程写库（fire-and-forget） |
| `while ... deadline` | 轮询 | 无 join 句柄，轮询直到后台线程落库可见（上限 5s） |
| 断言 | run + 1 event | 异步写入最终一致（status/span_name/duration 正确） |

**关键细节**：store 的线程本地连接（P-018 方案）让后台线程自己建连接写文件库，主线程查询连接各自独立——SQLite 文件多连接并发写靠 busy timeout（10s）兜底。

## ⚠️ 风险点

1. **内存库 ≠ 跨线程**：`":memory:"` 每线程独立——recorder 测试必须用文件库（P-020 已踩坑并记录）。
2. **轮询等待是软等待**：5s 上限内后台线程若被调度延迟，断言可能偶发失败——实际 0.05s 间隔 + 50 次足够，但 CI 高负载需留意。
3. **占位符时间串**：`"T0"` 等仅测试用；生产必须 ISO 时间（`datetime.now(UTC).isoformat()` 风格），否则排序语义错误。

---
_2026-10-05 M6 新增：结构图 + 设计思想 + 成块代码解析（参数逐条表）+ 风险点。_
