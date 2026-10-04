# ============================================================================
# AgentFlow · scheduler/cron.py —— 手写 cron 调度匹配（M5）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/scheduler/cron.py
# 对标来源: evoflow/admin/automation_schedule.py（手写 5 字段匹配）
# 里程碑: M5
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────────────────────┐
# │ normalize_schedule(expr) → 标准 5 字段 cron 串                │
# │   标准 5 字段原样返回；关键词/非法/空 → 兜底 "0 9 * * *"       │
# │ cron_matches_at(expr, dt) → bool（dt 落在该调度上？）         │
# │   ├─ _field_matches(pattern, value)  * , - */n 全支持        │
# │   └─ _dow_matches(pattern, dt)  DOW 按 JS 0=周日             │
# └──────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 零第三方依赖：验收演示要"每分钟 echo"，rrule/croniter 不引入。
# 2. 只收标准 5 字段 cron 或"每天/daily/@daily"这类粗粒度词；
#    自然语言模糊解析（"每天早上"）不做，非法一律兜底 09:00。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. normalize_schedule: 调度表达式归一化
# 2. cron_matches_at: 判断某时刻是否命中调度
# 🔒 内部私有函数
# 1. _field_matches: 单字段匹配（* / , / - / */n）
# 2. _dow_matches: 星期字段匹配（JS 约定 0=周日，7 视为 0 别名）
# 3. _is_standard_cron / _parse_range: 校验与区间解析
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. dom/dow 用 POSIX 语义：两者都被限制时为 OR，否则被限制者须命中
# 2. DOW 是 JS 约定（0=周日），勿用 Python weekday()（0=周一）直比
# ============================================================================

from __future__ import annotations

from datetime import datetime

# 标准 cron 单字段允许的字符：数字 / * / , / - / /
_CRON_FIELD_CHARS = set("0123456789*,/-")

# 兜底调度：任何非法/空/关键词都归一到"每天 09:00"
_FALLBACK = "0 9 * * *"


def _is_standard_cron(expr: str) -> bool:
    """是否为标准 5 字段 cron（按空白切恰好 5 段，每段字符合法且非空）。"""
    parts = expr.split()
    if len(parts) != 5:
        return False
    for p in parts:
        if not p or not _CRON_FIELD_CHARS.issuperset(p):
            return False
    return True


def normalize_schedule(expr: str) -> str:
    """把用户调度表达式归一化为标准 5 字段 cron 串。

    规则（定稿）：
        - 空 / None → 兜底 "0 9 * * *"
        - 标准 5 字段 cron（如 "*/1 * * * *"、"0 9 * * *"）→ 原样返回
        - 关键词（@daily / 每天 / 每天9点 / daily …）→ "0 9 * * *"
        - 其它非法写法 → 兜底 "0 9 * * *"
    """
    if not expr:
        return _FALLBACK
    e = expr.strip()
    if not e:
        return _FALLBACK
    if _is_standard_cron(e):
        return e
    # 非标准写法（关键词/自然语言/乱填）一律兜底每天 09:00
    return _FALLBACK


def _parse_range(token: str) -> tuple[int, int] | None:
    """把 "a-b" 或 "a" 解析成 (lo, hi)；非法返回 None。"""
    try:
        if "-" in token:
            lo_s, hi_s = token.split("-", 1)
            lo, hi = int(lo_s), int(hi_s)
            return (lo, hi) if lo <= hi else None
        v = int(token)
        return v, v
    except ValueError:
        return None


def _field_matches(pattern: str, value: int) -> bool:
    """单字段匹配：支持 *、逗号列表、a-b 区间、*/n 步长、a-b/n 步长区间。"""
    for part in pattern.split(","):
        part = part.strip()
        if not part:
            continue
        if part == "*":
            return True
        if "/" in part:
            base, _, step_s = part.partition("/")
            try:
                step = int(step_s)
            except ValueError:
                continue
            if step <= 0:
                continue
            if base == "*":
                # "*/n"：每 n 个单位命中一次（value 是 step 的倍数）
                if value % step == 0:
                    return True
            else:
                rng = _parse_range(base)
                if rng is not None:
                    lo, hi = rng
                    if lo <= value <= hi and (value - lo) % step == 0:
                        return True
        else:
            rng = _parse_range(part)
            if rng is not None:
                lo, hi = rng
                if lo <= value <= hi:
                    return True
    return False


def _dow_matches(pattern: str, dt: datetime) -> bool:
    """星期字段匹配。

    DOW 按 JS 约定：0=周日，1=周一 … 6=周六（Python weekday() 是 0=周一，
    需换算）。cron 同时允许 7 作为周日(0) 的别名，这里把独立 token "7" 归一为 "0"。
    """
    js_dow = (dt.weekday() + 1) % 7  # 周一0→1 … 周日6→0
    norm = ",".join(
        "0" if p.strip() == "7" else p for p in pattern.split(",")
    )
    return _field_matches(norm, js_dow)


def cron_matches_at(expr: str, dt: datetime) -> bool:
    """判断时刻 dt 是否命中调度 expr（先归一化再逐字段比对）。

    minute / hour / month 必须同时命中（AND）；
    dom / dow 用 POSIX 语义：两者都被限制（非 *）时取 OR，否则被限制者须命中。
    """
    parts = normalize_schedule(expr).split()
    if len(parts) != 5:
        return False
    minute, hour, dom, month, dow = parts

    if not _field_matches(minute, dt.minute):
        return False
    if not _field_matches(hour, dt.hour):
        return False
    if not _field_matches(month, dt.month):
        return False

    dom_restricted = dom != "*"
    dow_restricted = dow != "*"
    if dom_restricted and dow_restricted:
        return _field_matches(dom, dt.day) or _dow_matches(dow, dt)
    if dom_restricted:
        return _field_matches(dom, dt.day)
    if dow_restricted:
        return _dow_matches(dow, dt)
    return True
