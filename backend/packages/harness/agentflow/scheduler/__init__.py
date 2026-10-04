# ============================================================================
# AgentFlow · scheduler —— 定时调度域（M5）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/scheduler/__init__.py
# 对标来源: evoflow/admin/automation_schedule.py + app/gateway/automation_runner.py
# 里程碑: M5（长任务与协作——定时任务触发链）
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────────────────────┐
# │ scheduler/                                                    │
# │   ├─ cron.py   手写 5 字段 cron 匹配（无第三方依赖）           │
#   └─ loop.py    AutomationScheduler（daemon tick 线程，只入队）│
# └──────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. tick 线程只"扫库 + 入队"，绝不建 agent / 不碰模型（执行权在 REPL 主线程）。
# 2. cron 匹配纯 stdlib 手写，不引第三方库。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. normalize_schedule / cron_matches_at（cron.py）
# 2. AutomationScheduler（loop.py）
# ============================================================================

from agentflow.scheduler.cron import cron_matches_at, normalize_schedule
from agentflow.scheduler.loop import AutomationScheduler

__all__ = ["AutomationScheduler", "cron_matches_at", "normalize_schedule"]
