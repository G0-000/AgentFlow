# ============================================================================
# AgentFlow · scheduler/loop.py —— 定时调度 daemon tick 线程（M5）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/scheduler/loop.py
# 对标来源: evoflow/app/gateway/automation_runner.py（tick 循环 60s）
# 里程碑: M5
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────────────────────┐
# │ AutomationScheduler(repo, queue, interval=60)                │
# │   start() → threading.Thread(target=_loop, daemon=True)     │
# │   stop()  → _running=False                                   │
# │   _loop() → while running: _tick(); sleep(interval)          │
# │   _tick(now=None):                                          │
# │     repo.list_active() → cron_matches_at 命中                │
# │       → 分钟级去重 _fired_minute（同分钟只入队一次，R2）      │
# │       → once 型：once_fired 或偏离 scheduled_at>120s 跳过    │
# │       → queue.put((task_id, prompt))  ← 只投递，不执行       │
# └──────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. tick 线程是 daemon：只扫库 + 入队，**绝不建 agent / 不碰模型**。
#    真正执行在 REPL 主线程 drain 队列时（规划 R4/R6）。
# 2. repo 走 db_path 线程本地连接（P-018）：tick 线程不共享主线程 conn。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. AutomationScheduler: 定时调度器（启停 daemon tick 线程）
# 🔒 内部私有函数
# 1. _parse_iso: 容错解析 scheduled_at（去时区，与本地 naive now 比较）
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. _fired_minute 是进程内内存态：重启后不保留，靠 once_fired 落库兜底
# 2. tick 内异常静默吞掉——daemon 线程崩了会静默停摆，故每个任务单独 try
# 3. 时间语义（P-023）：tick 缺省时钟 = 本地 naive 墙钟（datetime.now()），
#    cron 串与 --at 均按用户本地墙钟解释；注入 aware 时钟先转本地 naive，
#    勿再退回 datetime.now(UTC)（旧代码 aware-naive 相减 TypeError 被吞，
#    once 任务生产路径永不触发；且 UTC 墙钟与本地 cron 错配 8 小时）
# ============================================================================

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime

from agentflow.scheduler.cron import cron_matches_at

logger = logging.getLogger(__name__)


def _parse_iso(value: object) -> datetime | None:
    """容错解析 ISO 时间串；带时区则去时区（与本地 naive now 比较）。"""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt


class AutomationScheduler:
    """定时调度器：后台 daemon 线程每分钟扫 active 任务，到点投队列。

    参数:
        repo:    AutomationRepository（db_path 模式，线程本地连接）
        queue:   queue.Queue，命中后投递 (task_id, prompt)
        interval: tick 间隔秒（默认 60）
    """

    def __init__(self, repo, queue, interval: float = 60):
        self._repo = repo
        self._queue = queue
        self.interval = interval
        self._running = False
        self._thread: threading.Thread | None = None
        # R2：分钟级去重 task_id -> "YYYYMMDDHHM"，同一分钟只入队一次
        self._fired_minute: dict[str, str] = {}

    def start(self) -> None:
        """启动 daemon tick 线程（detach，主进程退出即随进程结束）。"""
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """停止 tick 循环（下一轮 sleep 返回后退出）。"""
        self._running = False

    def _loop(self) -> None:
        while self._running:
            self._tick()
            time.sleep(self.interval)

    def _tick(self, now: datetime | None = None) -> None:
        """扫一遍 active 任务，命中者投队列。

        now 可注入（测试用固定时刻，naive 本地墙钟）；缺省取本地当前时间。

        时间语义（P-023）：cron 串与 --at 都是用户本地墙钟，故缺省时钟统一为
        本地 naive；注入 aware 时钟时先转本地 naive，与 _parse_iso 剥 tz 后的
        scheduled_at 同域比较，杜绝 aware-naive 直接相减的 TypeError。
        """
        now = now or datetime.now()  # noqa: DTZ005 —— 刻意本地 naive 墙钟（P-023 语义）
        if now.tzinfo is not None:
            # 容错：注入 aware 时钟（如旧 datetime.now(UTC)）先转本地 naive
            now = now.astimezone().replace(tzinfo=None)
        minute_key = now.strftime("%Y%m%d%H%M")

        try:
            tasks = self._repo.list_active()
        except Exception:  # noqa: BLE001 —— daemon 读库失败本轮静默，下轮重试
            return

        for a in tasks:
            try:
                task_id = a["task_id"]
                # ① cron 是否命中当前分钟
                if not cron_matches_at(a["schedule"], now):
                    continue
                # ② R2 分钟级去重：同一分钟同一任务只入队一次
                if self._fired_minute.get(task_id) == minute_key:
                    continue
                # ③ once 型幂等：已触发过，或偏离目标时间窗 >120s 则跳过
                if a.get("schedule_type") == "once":
                    if a.get("once_fired"):
                        continue
                    sat = _parse_iso(a.get("scheduled_at"))
                    if sat is not None and abs((now - sat).total_seconds()) > 120:
                        continue
                # ④ 标记 + 投递（不执行，执行权在 REPL 主线程）
                self._fired_minute[task_id] = minute_key
                self._queue.put((task_id, a["prompt"]))
            except Exception as exc:  # noqa: BLE001 —— 单任务异常不影响其它任务
                logger.warning("自动化单任务处理失败: %s", exc)
                continue
