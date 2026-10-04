# ============================================================================
# AgentFlow · collab/execution_lifecycle.py —— 执行生命周期 7 阶段（M5）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/collab/execution_lifecycle.py
# 对标来源: evoflow/collab/execution_lifecycle.py
#   原版还有结构化答案解析等重型逻辑；M5 裁剪成常量 + 标签 + 裸文本意图识别。
# 里程碑: M5
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────────────┐
# │ LIFECYCLE_* ×7 常量                                  │
# │ lifecycle_label_zh(stage) → 中文标签                 │
# │ user_execution_start_intent(text) → bool            │
# │   裸文本集合子串匹配（≤64 字符），M7 gate 用         │
# │ infer_lifecycle_stage(goal_row) → stage             │
# │   goal_status → 生命周期阶段映射                     │
# └──────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. M5 流程自动穿过 awaiting_authorization（自动授权）；intent 函数保留不接线，
#    给 M7"用户二次确认 gate"用。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. LIFECYCLE_* 常量 / lifecycle_label_zh / user_execution_start_intent /
#    infer_lifecycle_stage
# ----------------------------------------------------------------------------

from __future__ import annotations

# ---------- 7 阶段生命周期常量（稳定 key，供 UI/前端映射） ----------
LIFECYCLE_PLANNING = "planning"
LIFECYCLE_PLAN_READY = "plan_ready"
LIFECYCLE_AWAITING_AUTHORIZATION = "awaiting_authorization"
LIFECYCLE_AUTHORIZED = "authorized"
LIFECYCLE_EXECUTING = "executing"
LIFECYCLE_PAUSED = "paused"
LIFECYCLE_DONE = "done"

_LIFECYCLE_LABELS_ZH: dict[str, str] = {
    LIFECYCLE_PLANNING: "规划中",
    LIFECYCLE_PLAN_READY: "计划已定稿",
    LIFECYCLE_AWAITING_AUTHORIZATION: "待授权开始执行",
    LIFECYCLE_AUTHORIZED: "已授权待启动",
    LIFECYCLE_EXECUTING: "执行中",
    LIFECYCLE_PAUSED: "已暂停",
    LIFECYCLE_DONE: "已结束",
}

# "开始执行"裸文本意图集合（M5 冻结：子串匹配，≤64 字符）
_START_INTENT_PHRASES: frozenset[str] = frozenset(
    {
        "开始",
        "开始执行",
        "确认开始",
        "按计划开始执行",
        "开始吧",
        "执行",
        "start",
        "start execution",
        "go",
    }
)

# goal 终态
_TERMINAL = frozenset({"completed", "failed", "cancelled"})


def lifecycle_label_zh(stage: str) -> str:
    """生命周期阶段 → 中文标签（未知阶段返回原 key）。"""
    return _LIFECYCLE_LABELS_ZH.get(str(stage or ""), str(stage or ""))


def user_execution_start_intent(text: str) -> bool:
    """裸文本是否表达"开始执行"意图（≤64 字符，短语子串匹配）。

    M5 流程不 gate（自动授权）；此函数保留供 M7 用户二次确认。
    """
    raw = str(text or "").strip()
    if not raw or len(raw) > 64:
        return False
    compact = raw.replace(" ", "").replace("\u3000", "").lower()
    for phrase in _START_INTENT_PHRASES:
        if phrase.replace(" ", "") in compact:
            return True
    return False


def _goal_status_of(goal_row) -> str:
    """从 goal 行（GoalRow / sqlite3.Row / dict）取 goal_status。"""
    if goal_row is None:
        return ""
    if isinstance(goal_row, dict):
        return str(goal_row.get("goal_status") or goal_row.get("status") or "")
    if hasattr(goal_row, "goal_status"):
        return str(goal_row.goal_status or "")
    try:
        return str(goal_row["goal_status"])
    except (KeyError, TypeError):  # dict 缺 key / 不可下标 → 视为无状态
        return ""


def infer_lifecycle_stage(goal_row) -> str:
    """由 goal 行状态推断生命周期阶段：
    终态→done；paused→paused；executing→executing；
    planned→awaiting_authorization；planning→planning；其余→plan_ready。
    """
    status = _goal_status_of(goal_row).strip().lower()
    if status in _TERMINAL:
        return LIFECYCLE_DONE
    if status == LIFECYCLE_PAUSED:
        return LIFECYCLE_PAUSED
    if status == LIFECYCLE_EXECUTING:
        return LIFECYCLE_EXECUTING
    if status == "planned":
        return LIFECYCLE_AWAITING_AUTHORIZATION
    if status == LIFECYCLE_PLANNING:
        return LIFECYCLE_PLANNING
    return LIFECYCLE_PLAN_READY
