# ============================================================================
# AgentFlow · agents/lead_agent/prompt.py —— 系统提示词（M1 雏形）
# ----------------------------------------------------------------------------
# 文件: backend/packages/harness/agentflow/agents/lead_agent/prompt.py
# 仿原: evoflow/agents/lead_agent/prompt.py（原版 2000+ 行：技能段/工具段/场景段，
#       M1 只学它的核心思想——"当前时间注入 system prompt"）
# 里程碑: M1
# ----------------------------------------------------------------------------
# 结构图:
# ┌──────────────────────────────────────────────────────┐
# │ prompt.py（提示词构建）                               │
# │   format_runtime_now_for_prompt(dt=None) → str       │
# │     "2026-09-28 周一 (UTC+08:00)"                    │
# │     （本地时间 + 中文星期 + UTC 偏移，原版同款格式）  │
# │   build_lead_agent_system_prompt() → str             │
# │     人格说明 + 【当前系统时间】注入                   │
# │                                                      │
# │ 为什么用"注入"而不是"时间工具"（关键设计）:          │
# │   原版没有独立 datetime 工具——模型从 system prompt   │
# │   里直接读到当前时间，无需工具调用，省一轮往返。     │
# └──────────────────────────────────────────────────────┘
# ============================================================================
from __future__ import annotations

from datetime import datetime, timedelta, timezone

# 中文星期名（Monday=0 ... Sunday=6，与原版 WEEKDAY_NAMES 对齐）
WEEKDAY_NAMES_ZH = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def format_runtime_now_for_prompt(
    dt: datetime | None = None, *, prompt_language: str | None = None
) -> str:
    """把"当前时间"格式化为适合注入提示词的字符串（原版同款函数）。

    格式: "2026-09-28 周一 (UTC+08:00)"
        - 日期: YYYY-MM-DD（本地时区）
        - 星期: 中文（周一到周日）
        - 时区: UTC 偏移（+/-HH:MM），括号包裹

    参数:
        dt: 指定时刻；缺省取当前本地时间
        prompt_language: 原版用于切换中英文星期名；M1 固定中文，
                         保留该参数以对齐原版签名（后续扩展）

    为什么有 UTC 偏移: 模型推理无本地时区概念，显式偏移
    才能正确换算"还有几小时到期"这类相对时间问题。
    """
    # ① 取本地时间（缺省时 astimezone 自动补本地时区）
    if dt is None:
        dt = datetime.now().astimezone()
    if dt.tzinfo is None:
        # 无时区信息时按 UTC 0 处理再转本地（与原版一致）
        dt = dt.replace(tzinfo=timezone(timedelta(0))).astimezone()

    # ② 星期（Monday=0 → 列表索引）
    weekday_zh = WEEKDAY_NAMES_ZH[dt.weekday()]

    # ③ UTC 偏移 → "+08:00" / "-05:00"
    offset = dt.utcoffset() or timedelta(0)
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    hh, mm = divmod(abs(total_minutes), 60)
    utc_part = f"UTC{sign}{hh:02d}:{mm:02d}"

    # ④ 拼装
    return f"{dt.strftime('%Y-%m-%d')} {weekday_zh} ({utc_part})"


def build_lead_agent_system_prompt() -> str:
    """M1 系统提示词：人格 + 当前时间注入。

    原版在 prompt.py 里把时间/技能/工具段拼成完整 system prompt；
    M1 只做最小注入（回答日期问题不靠工具、靠这里的时间）。
    M2 起在此基础上追加技能段、工具段（学原版 get_skills_prompt_section 等）。
    """
    return (
        "你是 AgentFlow 的助手（仿写 EvoFlow 的 M1 最小实现）。\n"
        "请用中文简洁回答；需要准确日期/时间时，直接使用下面注入的当前时间。\n\n"
        f"当前系统时间：{format_runtime_now_for_prompt()}"
    )
