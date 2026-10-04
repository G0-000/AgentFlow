# ============================================================================
# AgentFlow · agents/goal/goal_judge.py —— 步骤完成判定（M5）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/agents/goal/goal_judge.py
# 对标来源: evoflow/agents/goal/goal_reply_interpreter.py + goal_controller.py
#   原版含 wait_user 死路（M5 砍）；判定只分 continue/complete 两路。
# 里程碑: M5
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────────────┐
# │ judge_last_reply(model, last_text) → dict             │
# │   {"verdict":"continue|complete","summary":...,"reason":...} │
# │   解析失败 / 异常 → verdict="continue" 兜底           │
# └──────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 判定模型与主 Agent 解耦：专门喂一段"你是判定器"的提示词，强制 JSON 输出。
# 2. 容错即安全：任何解析失败都判 continue（宁可多跑一轮，不误判完工），
#    连续 continue 由 goal_loop 的 fallback_streak≥3 熔断 paused（R1）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. judge_last_reply: 判定模型回复是否完成当前步骤
# ----------------------------------------------------------------------------

from __future__ import annotations

from langchain_core.messages import HumanMessage

from agentflow.plans.types import extract_first_json_object

_JUDGE_PROMPT = (
    "你是任务完成判定器。下面是执行 Agent 针对某一步骤给出的回复。"
    "请判断【该步骤是否已经完成】，只输出一个严格 JSON 对象，不要任何其他文字：\n"
    '{"verdict":"complete"|"continue","summary":"一句话总结本步成果","reason":"判断理由"}\n'
    "判定规则：\n"
    "- verdict=complete：本步骤目标已达成；\n"
    "- verdict=continue：还没做完，需要继续；\n"
    "- summary/reason 都用中文短句；拿不准时判 continue。\n\n"
    "执行 Agent 的回复如下：\n"
)


def judge_last_reply(model, last_text: str) -> dict:
    """调判定模型，返回 {verdict, summary, reason}。

    任何异常 / JSON 解析失败 → verdict="continue"，summary/reason 兜底空串。
    """
    fallback = {"verdict": "continue", "summary": "", "reason": ""}
    try:
        resp = model.invoke([HumanMessage(_JUDGE_PROMPT + str(last_text)[:2000])])
        content = getattr(resp, "content", resp)
        if not isinstance(content, str):
            content = str(content)
        blob = extract_first_json_object(content)
        import json

        data = json.loads(blob)
        verdict = str(data.get("verdict", "")).strip().lower()
        if verdict not in ("complete", "continue"):
            verdict = "continue"
        return {
            "verdict": verdict,
            "summary": str(data.get("summary", "") or ""),
            "reason": str(data.get("reason", "") or ""),
        }
    except Exception:  # noqa: BLE001 —— 判定输出不可控，任何解析失败都回退（fallback streak 计数）
        return fallback
