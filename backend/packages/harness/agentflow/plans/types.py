# ============================================================================
# AgentFlow · plans/types.py —— 步骤计划数据模型 + JSON 解析
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/plans/types.py
# 对标来源: evoflow/collab/plan_task_storage.py（PlanStep 形状）
# 里程碑: M5
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────────────┐
# │ PlanStep(dataclass)                                  │
# │   ref / short_name / description / depends_refs[]    │
# │   status: pending|executing|completed|failed         │
# │ parse_steps_json(text) → list[PlanStep]              │
# │   容错：截取首个完整 JSON 对象再解析                  │
# └──────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 模型吐 JSON 时常带前后废话（"好的，计划如下：```json ..."），
#    解析器按花括号配平截取首个完整 {...}，再 json.loads（容错设计）。
# 2. 解析失败一律 raise ValueError（含缺 steps / 缺 ref / 类型错误），
#    由 goal_loop 捕获后置 goal=failed。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. PlanStep: 单步计划数据类
# 2. parse_steps_json: 模型回复文本 → 步骤列表（失败 raise ValueError）
# 3. extract_first_json_object: 容错截取首个 JSON 对象（judge 复用）
# 🔒 内部私有函数
# 无
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. depends_refs 必须是字符串列表；未知 ref 的校验在 resolver.topo_sort
# ============================================================================

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass
class PlanStep:
    """单个计划步骤（与 goals.plan_steps_json 数组元素逐字段对齐）。"""

    ref: str                      # 步骤唯一编号（如 "s1"）
    short_name: str               # 短名（终端展示用）
    description: str             # 步骤详细描述（nudge 提示词用）
    depends_refs: list[str]       # 前置步骤 ref 列表（空 = 无依赖）
    status: str = "pending"       # pending/executing/completed/failed


def extract_first_json_object(text: str) -> str:
    """从模型回复里容错截取首个完整 JSON 对象文本（按花括号配平，忽略字符串内括号）。

    找不到 / 未闭合 → raise ValueError。
    """
    raw = str(text or "")
    start = raw.find("{")
    if start == -1:
        raise ValueError("回复中找不到 JSON 对象起点 '{'")
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(raw)):
        ch = raw[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return raw[start : i + 1]
    raise ValueError("JSON 对象未闭合（花括号不匹配）")


def parse_steps_json(text: str) -> list[PlanStep]:
    """把模型首转回复解析成 PlanStep 列表。

    期望 JSON 形状: {"steps": [{"ref":"s1","short_name":...,"description":...,
                               "depends_refs":[...]}, ...]}
    解析失败（无 JSON / 结构不符 / 缺必填 ref）→ raise ValueError。
    """
    blob = extract_first_json_object(text)
    try:
        data = json.loads(blob)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 解码失败: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("JSON 顶层必须是对象")  # noqa: TRY004
    raw_steps = data.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise ValueError("缺少非空 'steps' 数组")
    steps: list[PlanStep] = []
    for item in raw_steps:
        if not isinstance(item, dict):
            raise ValueError("steps 元素必须是对象")  # noqa: TRY004
        ref = item.get("ref")
        if not isinstance(ref, str) or not ref.strip():
            raise ValueError("每个步骤必须有非空字符串 ref")
        deps = item.get("depends_refs", [])
        if not isinstance(deps, list):
            raise ValueError("depends_refs 必须是数组")  # noqa: TRY004
        steps.append(
            PlanStep(
                ref=ref.strip(),
                short_name=str(item.get("short_name", "") or ""),
                description=str(item.get("description", "") or ""),
                depends_refs=[str(d) for d in deps],
            )
        )
    return steps


def steps_to_json(steps: list[PlanStep]) -> str:
    """PlanStep 列表 → JSON 字符串（落库 plan_steps_json 用）。"""
    return json.dumps([_step_to_dict(s) for s in steps], ensure_ascii=False)


def steps_from_json(blob: str) -> list[PlanStep]:
    """plan_steps_json 文本 → PlanStep 列表（断点恢复用）。"""
    data = json.loads(blob or "[]")
    out: list[PlanStep] = []
    for item in data:
        out.append(
            PlanStep(
                ref=item["ref"],
                short_name=item.get("short_name", ""),
                description=item.get("description", ""),
                depends_refs=list(item.get("depends_refs", [])),
                status=item.get("status", "pending"),
            )
        )
    return out


def _step_to_dict(s: PlanStep) -> dict:
    return {
        "ref": s.ref,
        "short_name": s.short_name,
        "description": s.description,
        "depends_refs": list(s.depends_refs),
        "status": s.status,
    }


# field 占位：避免 dataclass 未用 import 告警（保持显式）
__all__ = [
    "PlanStep",
    "extract_first_json_object",
    "parse_steps_json",
    "steps_from_json",
    "steps_to_json",
]
