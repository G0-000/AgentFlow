# ============================================================================
# AgentFlow · tools/builtins/knowledge_tool.py —— 知识库检索工具
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/tools/builtins/knowledge_tool.py
# 对标来源: evoflow/tools/builtins/knowledge_tool.py
#   原版：search/read/list 三动作 + _format_hit 统一格式化，
#   接 owned RAG 服务；M2 先占位（M5 接入向量库）。
# 里程碑: M2
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────────────┐
# │ _format_hit(h, index) -> str                               │
# │   单条命中格式化：标题/分数/摘要（照原版 _format_hit）     │
# │                                                             │
# │ knowledge_tool(action, query, doc_id, kb_name) -> str      │
# │   @tool("knowledge", return_direct=True)                   │
# │   search → 关键词/自然语言检索                             │
# │   read   → 按 doc_id 读文档                                │
# │   list   → 列出知识库文档（kb_name 可选）                  │
# │   （M2 占位：返回"未接入"明确提示）                        │
# └────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 接口契约先行：search/read/list 三动作 + 参数名与返回格式固定，
#    即使 M2 未接 RAG，调用方（模型/CLI/测试）的用法不会变；
#    M5 只换函数体内部实现（接向量库），签名零改动。
# 2. _format_hit 统一命中格式：后续所有来源（向量库/全文）都走它，
#    避免各工具各写各的展示格式（照原版）。
# 3. 占位也返回"明确提示"而非空串：防止模型误以为检索到了结果
#    而编造内容（幻觉防控）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. knowledge_tool: 知识库检索工具（LangChain @tool，注册名 "knowledge"）
# 🔒 内部私有函数
# 1. _format_hit: 单条知识库命中格式化（标题/分数/摘要）
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. 函数签名（action/query/doc_id/kb_name）是契约，M5 接 RAG 时不可改
# 2. 占位提示文案会被模型直接转述给用户，措辞要准确（含"设置中添加向量模型"指引）
# 3. _format_hit 字段取值顺序（title→fileName→docId）对齐原版，勿乱改
# ============================================================================
from __future__ import annotations

from typing import Any

from langchain.tools import tool


def _format_hit(h: dict[str, Any], index: int) -> str:
    """格式化一条知识库命中（照原版 _format_hit：标题/分数/摘要）。"""
    title = h.get("title") or h.get("fileName") or h.get("docId") or f"文档{index + 1}"
    score = h.get("rrfScore") or h.get("score") or 0
    score_str = f"{float(score):.3f}" if score else "—"
    snippet = (str(h.get("content") or "")[:400]).strip()
    parts = [f"[{index + 1}] {title}", f"   分数: {score_str}"]
    if snippet:
        parts.append(f"   {snippet}")
    return "\n".join(parts)


_KNOWLEDGE_DESCRIPTION = """\
知识库检索工具（统一接口: search / read / list）。
当用户要求"查一下知识库 / 搜我们文档里有没有 xxx / 读某文档"时使用。
action=search: 传 query（关键词/自然语言问题）。
action=read: 传 doc_id（文档 ID）。
action=list: 列出知识库文档（传 kb_name 可选）。
注意: 当前知识库未接入时返回明确提示。
"""


@tool("knowledge", description=_KNOWLEDGE_DESCRIPTION, parse_docstring=False, return_direct=True)
def knowledge_tool(
    action: str = "search",
    query: str | None = None,
    doc_id: str | None = None,
    kb_name: str | None = None,
) -> str:
    """知识库检索（使用条件见工具 description）。"""
    # M2 占位实现：结构对齐原版（search/read/list 三动作 + _format_hit），
    # 真实 RAG 在 M5（向量库）接入；此处返回明确提示避免模型误以为有结果。
    if action == "list":
        return "（知识库未接入，暂无文档。M5 接入向量库后可用）"
    if action == "read":
        return f"（知识库未接入，无法读取文档: {doc_id}）"
    return (
        "（知识库未接入，无法检索。请告知用户: 需要在设置中添加向量模型后建立知识库。"
        f"查询: {query or ''}）"
    )
