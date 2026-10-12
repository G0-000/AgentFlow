# ============================================================================
# AgentFlow · tests/test_scheduler_cron.py —— cron 匹配与定时 tick 入队（M5）
# 验收项：⑤定时触发。
# 用 cron_matches_at / normalize_schedule 纯函数 + AutomationScheduler._tick
# 注入固定 now + FakeRepo/FakeQueue，不起 daemon 线程、不碰模型。
# ============================================================================
# ruff: noqa: DTZ001, DTZ005 —— 测试构造固定时间点/本地墙钟（naive datetime 是测试语义）
from datetime import UTC, datetime

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


# ---------- P-023 回归：生产默认时钟路径（不传 now） ----------

def test_tick_default_now_fires_once_task(caplog):
    """P-023 回归①：不传 now = 生产默认路径，once 任务必须真入队。

    旧代码 now=datetime.now(UTC)（aware）与 _parse_iso 剥 tz 的 naive
    scheduled_at 直接相减 → TypeError 被单任务 except 吞掉记 warning，
    once 型任务在生产默认路径永远被跳过。
    """
    now_local = datetime.now()
    repo = FakeRepo(
        [_task("t_once_prod", schedule="*/1 * * * *",
               schedule_type="once", scheduled_at=now_local.isoformat())]
    )
    q = FakeQueue()
    sched = AutomationScheduler(repo, q)
    with caplog.at_level("WARNING", logger="agentflow.scheduler.loop"):
        sched._tick()  # 不传 now —— 生产默认时钟，必须走通 once 窗口判定
    assert q.items == [("t_once_prod", "echo hi")]
    assert "自动化单任务处理失败" not in caplog.text


def test_tick_aware_now_does_not_raise(caplog):
    """P-023 回归②：注入 aware UTC now（旧生产 bug 现场）不再 TypeError 吞掉。

    修复后 aware 时钟先 astimezone 转本地 naive 再与 naive scheduled_at 比较；
    两值同一时刻，±120s 窗口内必入队。
    """
    now_local = datetime.now()
    repo = FakeRepo(
        [_task("t_once_aware", schedule="*/1 * * * *",
               schedule_type="once", scheduled_at=now_local.isoformat())]
    )
    q = FakeQueue()
    sched = AutomationScheduler(repo, q)
    with caplog.at_level("WARNING", logger="agentflow.scheduler.loop"):
        sched._tick(now=datetime.now(UTC))  # aware —— 旧代码此处必 TypeError
    assert q.items == [("t_once_aware", "echo hi")]
    assert "自动化单任务处理失败" not in caplog.text


def test_tick_default_clock_called_without_tz(monkeypatch):
    """P-023 回归③（时区语义）：缺省时钟必须本地 naive（datetime.now()）。

    旧代码 datetime.now(UTC) 使 cron 串按 UTC 墙钟匹配——用户在 UTC+8 配
    "0 9 * * *"（意为本地早 9 点）实际在 UTC 09:00 = 本地 17:00 才触发。
    用间谍断言缺省时钟调用时 tz 参数为 None（本地墙钟）。
    """
    from agentflow.scheduler import loop as loop_mod

    calls = []
    real_datetime = loop_mod.datetime

    class _SpiedDateTime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            calls.append(tz)
            return real_datetime.now()

    monkeypatch.setattr(loop_mod, "datetime", _SpiedDateTime)
    q = FakeQueue()
    AutomationScheduler(FakeRepo([_task()]), q)._tick()  # 不传 now
    assert calls == [None]
