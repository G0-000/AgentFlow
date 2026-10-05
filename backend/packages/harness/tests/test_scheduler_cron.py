# ============================================================================
# AgentFlow · tests/test_scheduler_cron.py —— cron 匹配与定时 tick 入队（M5）
# 验收项：⑤定时触发。
# 用 cron_matches_at / normalize_schedule 纯函数 + AutomationScheduler._tick
# 注入固定 now + FakeRepo/FakeQueue，不起 daemon 线程、不碰模型。
# ============================================================================
# ruff: noqa: DTZ001 —— 测试构造固定时间点（cron 匹配用字段比较），naive datetime 是测试语义
from datetime import datetime

from agentflow.scheduler.cron import cron_matches_at, normalize_schedule
from agentflow.scheduler.loop import AutomationScheduler


class FakeQueue:
    def __init__(self):
        self.items = []

    def put(self, item):
        self.items.append(item)


class FakeRepo:
    def __init__(self, tasks):
        self._tasks = tasks

    def list_active(self):
        return [t for t in self._tasks if t["status"] == "active"]


def _task(task_id="t1", schedule="*/1 * * * *", **kw):
    base = {
        "task_id": task_id,
        "name": "演示任务",
        "prompt": "echo hi",
        "schedule": schedule,
        "schedule_type": "recurring",
        "scheduled_at": None,
        "once_fired": 0,
        "status": "active",
    }
    base.update(kw)
    return base


# ---------- cron 纯函数 ----------

def test_cron_every_minute_matches_any_minute():
    for hh, mm in [(0, 0), (9, 1), (12, 30), (23, 59)]:
        assert cron_matches_at("*/1 * * * *", datetime(2026, 10, 2, hh, mm)) is True


def test_cron_daily_9am_boundary():
    assert cron_matches_at("0 9 * * *", datetime(2026, 10, 2, 9, 0)) is True
    assert cron_matches_at("0 9 * * *", datetime(2026, 10, 2, 9, 1)) is False
    assert cron_matches_at("0 9 * * *", datetime(2026, 10, 2, 10, 0)) is False


def test_normalize_keyword_schedule():
    assert normalize_schedule("每天9点") == "0 9 * * *"
    assert normalize_schedule("0 9 * * *") == "0 9 * * *"


# ---------- _tick 行为 ----------

def test_tick_enqueues_due_task():
    q = FakeQueue()
    sched = AutomationScheduler(FakeRepo([_task()]), q)
    sched._tick(now=datetime(2026, 10, 2, 9, 0))
    assert q.items == [("t1", "echo hi")]


def test_tick_no_enqueue_when_not_due():
    q = FakeQueue()
    sched = AutomationScheduler(FakeRepo([_task(schedule="0 9 * * *")]), q)
    sched._tick(now=datetime(2026, 10, 2, 9, 1))
    assert q.items == []


def test_tick_same_minute_dedup():
    q = FakeQueue()
    sched = AutomationScheduler(FakeRepo([_task()]), q)
    sched._tick(now=datetime(2026, 10, 2, 9, 0, 0))
    sched._tick(now=datetime(2026, 10, 2, 9, 0, 45))  # 同分钟 tick 漂移
    assert len(q.items) == 1


def test_tick_retriggers_next_minute():
    q = FakeQueue()
    sched = AutomationScheduler(FakeRepo([_task()]), q)
    sched._tick(now=datetime(2026, 10, 2, 9, 0))
    sched._tick(now=datetime(2026, 10, 2, 9, 1))
    assert len(q.items) == 2


# ---------- once 型 ----------

def test_once_task_enqueued_in_window_then_idempotent():
    repo = FakeRepo(
        [_task("t_once", schedule="*/1 * * * *",
               schedule_type="once", scheduled_at="2026-10-02T09:00:00")]
    )
    q = FakeQueue()
    sched = AutomationScheduler(repo, q)
    sched._tick(now=datetime(2026, 10, 2, 9, 0, 30))  # 偏离 30s ≤ 120s → 入队
    assert len(q.items) == 1
    # once_fired 落库幂等标记后，下一分钟再 tick 不重复入队
    repo._tasks[0]["once_fired"] = 1
    sched._tick(now=datetime(2026, 10, 2, 9, 1, 0))
    assert len(q.items) == 1


def test_once_task_skipped_outside_window():
    repo = FakeRepo(
        [_task("t_once", schedule="*/1 * * * *",
               schedule_type="once", scheduled_at="2026-10-02T09:00:00")]
    )
    q = FakeQueue()
    sched = AutomationScheduler(repo, q)
    sched._tick(now=datetime(2026, 10, 2, 9, 5, 0))  # 偏离 300s > 120s → 跳过
    assert q.items == []
