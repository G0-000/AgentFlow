# ============================================================================
# AgentFlow · tools/builtins/file_tools.py —— 沙箱文件工具
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/tools/builtins/file_tools.py
# 对标来源: evoflow/tools/host_direct/file_tools.py（原版 read/write/update/delete，M4 简化为 read+write）
# 里程碑: M4
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────────────┐
# │ read_file(path) -> str                              │
# │   @tool("read_file", return_direct=True)            │
# │   读沙箱内文件（沙箱外路径 → 拦截提示）             │
# │                                                    │
# │ write_file(path, content, append) -> str           │
# │   @tool("write_file", return_direct=True)           │
# │   写/追加沙箱内文件（越界被 LocalSandbox 拦截）     │
# └──────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 文件读写统一走沙箱接口（_sandbox_guard 复用），
#    路径越界由 LocalSandbox._resolve 统一拦截（验收点 4 核心）。
# 2. 审计：每次文件操作落库（放行/拦截），可追溯子代理动过什么。
# 3. append 参数区分写/追加，语义直白（对齐 todo_tool 风格）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. read_file: 沙箱读文件工具（注册名 "read_file"）
# 2. write_file: 沙箱写文件工具（注册名 "write_file"）
# 3. configure_sandbox_audit_repository: 注入审计仓库
# 🔒 内部私有函数
# 1. _sandbox_guard: 取沙箱 + 异常统一 catch（工具共用）
# 2. _audit: 写审计记录
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. 路径必须经沙箱（不能直接 open() 宿主路径）
# 2. 审计仓库未注入时静默跳过（不阻塞工具主流程）
# ============================================================================

from __future__ import annotations

from langchain.tools import tool

from agentflow.persistence.sandbox_audit_repositories import SandboxAuditRepository
from agentflow.sandbox import Sandbox, SandboxError, get_sandbox_provider

_audit_repo: SandboxAuditRepository | None = None


def configure_sandbox_audit_repository(repo: SandboxAuditRepository | None) -> None:
    """注入沙箱审计仓库（CLI 装配；与 terminal_tool 共用同一注入点）。"""
    global _audit_repo
    _audit_repo = repo


def _audit(action: str, target: str, allowed: bool, reason: str = "") -> None:
    if _audit_repo is None:
        return
    try:
        _audit_repo.record(
            action=action,
            target=target,
            allowed=allowed,
            reason=reason,
            subagent_name=action,
        )
    except Exception:  # noqa: BLE001,S110 —— 审计失败不影响工具主流程
        pass


def _sandbox_guard() -> Sandbox | None:
    """取当前沙箱（无则 None）。"""
    provider = get_sandbox_provider()
    return provider.get(provider.acquire())


_READ_DESCRIPTION = """\
沙箱读文件工具：读取沙箱工作目录内的文件内容。
当需要查看沙箱内文件（如子代理生成的结果文件）时使用。
"""


@tool("read_file", description=_READ_DESCRIPTION, parse_docstring=False, return_direct=True)
def read_file(path: str) -> str:
    """读取沙箱内文件（沙箱外路径被拦截，全程审计）。"""
    sandbox = _sandbox_guard()
    if sandbox is None:
        return "（沙箱不可用）"
    try:
        content = sandbox.read_file(path)
        _audit("read_file", path, allowed=True)
        return content
    except SandboxError as exc:
        _audit("read_file", path, allowed=False, reason=str(exc))
        return f"（沙箱拦截）{exc}"


_WRITE_DESCRIPTION = """\
沙箱写文件工具：写入/追加沙箱工作目录内的文件。
当需要把内容保存到沙箱内文件（如生成报告、写配置）时使用。
append=True 追加到文件末尾；否则整体覆盖。
"""


@tool("write_file", description=_WRITE_DESCRIPTION, parse_docstring=False, return_direct=True)
def write_file(path: str, content: str, append: bool = False) -> str:
    """写入/追加沙箱内文件（越界被拦截，全程审计）。"""
    sandbox = _sandbox_guard()
    if sandbox is None:
        return "（沙箱不可用）"
    try:
        sandbox.write_file(path, content, append=append)
        _audit("write_file", path, allowed=True)
        return f"已写入: {path}" + ("（追加）" if append else "")
    except SandboxError as exc:
        _audit("write_file", path, allowed=False, reason=str(exc))
        return f"（沙箱拦截）{exc}"
