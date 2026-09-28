# ============================================================================
# AgentFlow · tools/builtins/todo_tool.py —— 会话内待办工具
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/tools/builtins/todo_tool.py
# 对标来源: evoflow/tools/builtins/todo_tool.py
#   原版：会话级 checklist（对话内待办），内存存储，不进任务中心；
#   M2 简化：动作收敛为 add/list/update/delete，返回格式固定。
# 里程碑: M2
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────────────┐
# │ TodoStatus(str, Enum): pending / in_progress / done /      │
# │                        cancelled（状态枚举）               │
# │ TodoItem(@dataclass): id / title / status / created_at     │
# │                                                             │
# │ _todos: dict[str, TodoItem] —— 会话级内存存储              │
# │                                                             │
# │ todo_tool(action, item, id, title, status) -> str          │
# │   @tool("todo", return_direct=True)                        │
# │   add    → 新增待办（title 必填）                           │
# │   list   → 列出全部（无则"（暂无待办）"）                  │
# │   update → 按 id 改状态                                    │
# │   delete → 按 id 删除                                      │
# └────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 参考文档：doc/doc-dev/01-里程碑/M2-工具与中间件.md §3
# 2. 原版语义：待办是"对话级 checklist"，不跨会话、不进任务中心——
#    用户随手记的待办跟会话走，轻量、无持久化负担。
# 3. return_direct=True：工具结果直接回给用户，不再让模型二次加工，
#    避免模型对结构化结果过度解读（照原版 clarification 工具模板）。
# 4. docstring 即说明书：_TODO_DESCRIPTION 就是给模型看的"何时用、
#    参数怎么填"，工具体保持最简。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. TodoStatus: 待办状态枚举
# 2. TodoItem: 待办数据类
# 3. todo_tool: 待办工具本体（LangChain @tool，注册名 "todo"）
# 🔒 内部私有函数
# 1. _format_todo: 单条待办格式化（列表展示用）
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. _todos 是模块级内存 dict：进程重启即清空（当前设计，调试够用）
# 2. 待办 ID 用 len(_todos)+1 生成：删除后 ID 可能复用（可接受，或用 uuid）
# 3. 修改 _TODO_DESCRIPTION 会直接影响模型何时调用本工具（措辞要准）
# ============================================================================
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Literal

from langchain.tools import tool


class TodoStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


@dataclass
class TodoItem:
    id: str
    title: str
    status: str = TodoStatus.PENDING.value
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))


# 会话级存储：内存 dict（原版语义：不跨会话、不进任务中心）
_todos: dict[str, TodoItem] = {}


def _format_todo(item: TodoItem) -> str:
    return f"- [{item.status}] {item.title}（{item.id}）"


_TODO_DESCRIPTION = """\
会话内待办清单工具（对话级 checklist，不是任务中心）。
当用户要求"列一下要做的事 / 帮我记个待办 / 进度到哪了"时使用。
动作: add=添加待办（title 必填）；list=列出全部；
update=改状态（id + status: pending/in_progress/done/cancelled）；delete=删除（id）。
"""


@tool("todo", description=_TODO_DESCRIPTION, parse_docstring=False, return_direct=True)
def todo_tool(
    action: Literal["add", "list", "update", "delete"] = "list",
    item: str | None = None,
    id: str | None = None,
    title: str | None = None,
    status: Literal["pending", "in_progress", "done", "cancelled"] = "pending",
) -> str:
    """会话内待办清单（使用条件见工具 description）。"""
    if action == "add":
        t = TodoItem(id=id or f"todo-{len(_todos) + 1}", title=title or item or "未命名待办")
        _todos[t.id] = t
        return f"已添加待办: {t.title}（{t.id}）"
    if action == "list":
        if not _todos:
            return "（暂无待办）"
        return "当前待办:\n" + "\n".join(_format_todo(t) for t in _todos.values())
    if action == "update":
        t = _todos.get(id or "")
        if not t:
            return f"待办不存在: {id}"
        t.status = status
        return f"已更新待办: {t.title} → {status}"
    if action == "delete":
        t = _todos.pop(id or "", None)
        return f"已删除待办: {t.title}" if t else f"待办不存在: {id}"
    return "未知动作，可选: add/list/update/delete"
