# ============================================================================
# AgentFlow · tools/tool_catalog.py —— 工具Tier分层定义与字段增强模块
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/tools/tool_catalog.py
# 对标来源: evoflow/tools/tool_catalog.py
#   原版共 273 行：7 档 tier + 大量分类函数，服务于 DB 同步 / Gateway 元数据 /
#   UI 展示；M2 只留【分层定义 + 中文标注 + 排序权重】核心。
# 里程碑: M2
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────────────┐
# │ ToolTier: Literal 类型，7 种工具档位静态类型定义             │
# │ TOOL_TIER_ORDER: 元组常量，Tier 优先级排序基准               │
# │ TOOL_TIER_LABELS_ZH: 档位 → 中文标签映射                     │
# │ TOOL_TIER_MAP: M2 本地硬编码 5 个工具的档位                  │
# │                                                             │
# │ normalize_tool_name(name) → 小写去空格                       │
# │ resolve_tool_tier(name) → 查档位（未知 → optional 兜底）     │
# │ tool_tier_label_zh(tier) → 中文标签                          │
# │ enrich_tool_catalog_fields(doc) → 给工具文档注入 tier 字段   │
# │ tier_sort_key(tier) → 排序权重（供 tools.py 排序用）         │
# └────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 使用 Literal 实现静态类型约束，Pylance 静态校验，限制 tier 只能使用
#    7 个指定字符串。
# 2. 独立维护 TOOL_TIER_ORDER 元组，统一定义优先级顺序，用于全局工具排序。
# 3. 拆分多个单一职责函数：归一化 / 分层判定 / 中文标注 / 字段增强 / 排序权重，
#    便于单独扩展（照原版 tool_catalog.py 的职责拆分）。
# 4. M2 简化：去掉对 intent_tool_profile 等深层模块的依赖，
#    用本地 TOOL_TIER_MAP 硬编码当前 5 个工具的档位。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. ToolTier: 工具档位类型别名（Literal，7 档）
# 2. TOOL_TIER_ORDER: Tier 排序常量元组
# 3. TOOL_TIER_LABELS_ZH: 档位中文标签映射表
# 4. normalize_tool_name: 工具名归一化（小写去空格）
# 5. resolve_tool_tier: 自动解析工具 tier（未知兜底 optional）
# 6. tool_tier_label_zh: 档位 → 中文标签
# 7. enrich_tool_catalog_fields: 批量丰富工具目录字段，注入中文标签
# 8. tier_sort_key: 档位 → 排序权重整数
# 🔒 内部私有函数
# 无
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. TOOL_TIER_ORDER 元组顺序直接决定工具优先级，禁止随意调整顺序
# 2. 新增 Tier 枚举值，需要同步更新 TOOL_TIER_ORDER、TOOL_TIER_LABELS_ZH
# 3. retired 代表退役工具，业务逻辑默认不参与 Agent 调度
# 4. 新增工具必须同步在 TOOL_TIER_MAP 追加一行，否则默认 optional
# ============================================================================
from __future__ import annotations

from typing import Any, Literal

# 工具档位（照原版）：（7个tier）
# 1. runtime=系统核心
# 2. core=日常常驻
# 3. workspace=工作区
# 4. plan=规划协作
# 5. goal=目标模式
# 6. optional=扩展可选
# 7. retired=已退役
ToolTier = Literal[
    "runtime", "core", "workspace", "plan", "goal", "optional", "retired"
]

# 档位展示顺序（供排序）  每一个元素都必须是 `ToolTier` 类型   `...` 代表**不定长元组**
TOOL_TIER_ORDER: tuple[ToolTier, ...] = (
    "runtime",
    "core",
    "workspace",
    "plan",
    "goal",
    "optional",
    "retired",
)

# 中文标签（照原版）
TOOL_TIER_LABELS_ZH: dict[ToolTier, str] = {
    "runtime": "系统核心",
    "core": "日常常驻",
    "workspace": "工作区",
    "plan": "规划协作",
    "goal": "目标模式",
    "optional": "扩展可选",
    "retired": "已退役",
}

# M2 本地硬编码：当前 5 个工具的分层（原版依赖 intent_tool_profile 动态解析，
# M2 直接写死——工具少，分层一目了然；加新工具时在此追加一行）
TOOL_TIER_MAP: dict[str, ToolTier] = {
    # 澄清：会话脊柱工具（原版 SESSION_SYSTEM_TOOL_NAMES 含 ask_clarification → runtime）
    "ask_clarification": "runtime",
    # 待办：对话内常驻（原版 todo → core 日常常驻）
    "todo": "core",
    # 知识库：工作区场景（原版 knowledge → workspace 档，角色勾选）
    "knowledge": "workspace",
    # 计划：规划协作（原版 plan → plan 档）
    "plan": "plan",
    # 抓网页：工作区场景
    "fetch_url": "workspace",
}


def normalize_tool_name(name: str | None) -> str:
    """工具名归一化：去首尾空格 + 转小写（照原版）。"""
    return str(name or "").strip().lower()


def resolve_tool_tier(name: str | None) -> ToolTier:
    """查工具档位：已知 → 对应 tier；未知 → optional（照原版兜底）。"""
    n = normalize_tool_name(name)
    if not n:
        return "optional"
    return TOOL_TIER_MAP.get(n, "optional")


def tool_tier_label_zh(tier: ToolTier | str | None) -> str:
    """档位中文标签（未知档位 → optional 标签，照原版）。"""
    key = str(tier or "optional").strip().lower()
    return TOOL_TIER_LABELS_ZH.get(key, TOOL_TIER_LABELS_ZH["optional"])  # type: ignore[return-value]


def enrich_tool_catalog_fields(doc: dict[str, Any]) -> dict[str, Any]:
    """给工具文档加 tier 字段（照原版 enrich_tool_catalog_fields）。

    用途: M7 gateway 返回工具列表 / 会话记录工具元数据时，附带分层信息。
    """
    out = dict(doc)
    tier = resolve_tool_tier(str(out.get("name") or ""))
    out["tool_type"] = tier
    out["tool_type_label"] = tool_tier_label_zh(tier)
    return out


def tier_sort_key(tier: ToolTier | str | None) -> int:
    """档位排序权重（tier 越靠前权重越小；未知档位排最后，照原版）。"""
    t = str(tier or "optional").strip().lower()
    try:
        return TOOL_TIER_ORDER.index(t)  # type: ignore[arg-type]
    except ValueError:
        return len(TOOL_TIER_ORDER)
