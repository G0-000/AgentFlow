# ============================================================================
# AgentFlow · tools/tool_result_store.py —— 工具结果存取模块（摘要截断 + 内存存储）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/tools/tool_result_store.py
# 对标来源: evoflow/tools/tool_result_store.py
#   原版共 168 行：UI 预览帮助、大输出截断 / 终端类跳过 / 读类 offload；
#   M2 简化成【内存存取 + 截断预览】核心。
# 里程碑: M2
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────────────┐
# │ _PREVIEW_MAX_CHARS = 1200（预览截断阈值，照原版常量）        │
# │ _SUMMARY_MAX_CHARS = 300（摘要默认展示长度）                │
# │                                                             │
# │ summarize_tool_result(text, max_chars) -> str               │
# │   工具结果 → 聊天可见摘要（非字符串先转字符串，超长截断）    │
# │                                                             │
# │ ToolResultStore（内存版）                                   │
# │   save(thread_id, tool_call_id, name, result) → 存完整结果   │
# │   get(thread_id, tool_call_id) → 取完整结果                 │
# │   summaries(thread_id) → 列出该线程全部摘要                 │
# │   clear_thread(thread_id) → 清空某线程结果                  │
# └────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 学原版：工具可能返回大结果（网页/文件），对话流只展示摘要；
#    完整结果按 thread_id + tool_call_id 存这里，供后续引用 / UI 展示。
# 2. M2 用内存 dict（进程内有效）；M3+ 如需跨进程再落 SQLite。
# 3. 摘要与完整结果分开存，避免对话上下文被大结果撑爆（token 成本控制）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. summarize_tool_result: 工具结果压成"聊天可见摘要"（截断 + 占位）
# 2. ToolResultStore: 工具结果存取类（内存版）
# 🔒 内部私有函数
# 无
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. _PREVIEW_MAX_CHARS / _SUMMARY_MAX_CHARS 是全局常量，调整影响所有摘要长度
# 2. 内存 dict 进程内有效；进程重启后结果丢失（当前仅调试用，可接受）
# ============================================================================
from __future__ import annotations

from typing import Any

# 预览截断阈值（照原版常量：大结果在聊天里只显示摘要）
_PREVIEW_MAX_CHARS = 1200

# 结果摘要默认展示长度
_SUMMARY_MAX_CHARS = 300


def summarize_tool_result(text: str | Any, max_chars: int = _SUMMARY_MAX_CHARS) -> str:
    """把工具结果压成"聊天可见摘要"（学原版：正文完整存，展示用摘要）。

    规则:
      - 非字符串先转字符串
      - 超长截断 + "…（已截断，原文 N 字）"
      - 空结果返回占位
    """
    raw = str(text or "")
    if not raw.strip():
        return "（工具无输出）"
    if len(raw) <= max_chars:
        return raw
    return f"{raw[:max_chars]}…（已截断，原文 {len(raw)} 字）"


class ToolResultStore:
    """工具结果存取（内存版）。

    为什么存在（学原版）：工具可能返回大结果（网页/文件），
    对话流只展示摘要；完整结果按 thread_id + tool_call_id 存这里，
    供后续引用/UI 展示（M7 gateway 接它）。
    M2 用内存 dict（进程内有效）；M3+ 如需跨进程再落 SQLite。
    """

    def __init__(self) -> None:
        # thread_id → {tool_call_id: {"name": ..., "result": ..., "summary": ...}}
        self._results: dict[str, dict[str, dict[str, Any]]] = {}

    def save(self, thread_id: str, tool_call_id: str, name: str, result: Any) -> None:
        """保存工具结果（自动生成摘要）。"""
        self._results.setdefault(thread_id, {})[tool_call_id] = {
            "name": name,
            "result": result,
            "summary": summarize_tool_result(result),
        }

    def get(self, thread_id: str, tool_call_id: str) -> dict[str, Any] | None:
        """按 thread + call id 取完整结果。"""
        return self._results.get(thread_id, {}).get(tool_call_id)

    def summaries(self, thread_id: str) -> list[dict[str, str]]:
        """列出某线程的全部工具摘要（对话流展示用）。"""
        return [
            {"name": r["name"], "summary": r["summary"]}
            for r in (self._results.get(thread_id) or {}).values()
        ]

    def clear_thread(self, thread_id: str) -> None:
        """清空某线程的工具结果。"""
        self._results.pop(thread_id, None)
