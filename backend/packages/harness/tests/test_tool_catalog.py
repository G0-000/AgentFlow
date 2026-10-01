# ============================================================================
# AgentFlow · tests/test_tool_catalog.py —— 工具目录测试（M2）
# 验收点 1：工具目录。覆盖：收集数量/去重/分层/排序。
# ============================================================================
from agentflow.tools.tool_catalog import (
    resolve_tool_tier,
    tier_sort_key,
    tool_tier_label_zh,
)
from agentflow.tools.tools import get_available_tools, get_builtin_tools


def test_get_builtin_tools_has_all():
    """M2 5 个基础工具 + M4 新增 4 个 = 9 个内置工具。"""
    tools = list(get_builtin_tools())
    assert len(tools) == 9
    names = {t.name for t in tools}
    # M2 基础 5 个
    assert {"ask_clarification", "todo", "knowledge", "plan", "fetch_url"} <= names
    # M4 新增：沙箱终端/文件 + 子代理派发
    assert {"terminal_run", "read_file", "write_file", "dispatch_subagents"} <= names


def test_tool_names_unique():
    """工具名不重复（_finalize_tool_catalog 去重保证）。"""
    names = [t.name for t in get_available_tools()]
    assert len(names) == len(set(names))


def test_available_tools_sorted_by_tier():
    """按 tier 排序：runtime 在前，plan 在后。"""
    tools = get_available_tools()
    tiers = [resolve_tool_tier(t.name) for t in tools]
    # 排序权重应是非递减（tier_sort_key 从小到大）
    weights = [tier_sort_key(t) for t in tiers]
    assert weights == sorted(weights)


def test_resolve_tool_tier_known():
    """已知工具的分层正确。"""
    assert resolve_tool_tier("ask_clarification") == "runtime"
    assert resolve_tool_tier("todo") == "core"
    assert resolve_tool_tier("knowledge") == "workspace"
    assert resolve_tool_tier("plan") == "plan"
    assert resolve_tool_tier("fetch_url") == "workspace"
    # M4 新增工具分层
    assert resolve_tool_tier("terminal_run") == "workspace"
    assert resolve_tool_tier("read_file") == "workspace"
    assert resolve_tool_tier("write_file") == "workspace"
    assert resolve_tool_tier("dispatch_subagents") == "core"


def test_resolve_tool_tier_unknown_defaults_optional():
    """未知工具名兜底 optional（照原版）。"""
    assert resolve_tool_tier("no_such_tool") == "optional"
    assert resolve_tool_tier("") == "optional"
    assert resolve_tool_tier(None) == "optional"


def test_tier_label_zh():
    """中文标签。"""
    assert tool_tier_label_zh("core") == "日常常驻"
    assert tool_tier_label_zh("unknown") == "扩展可选"
