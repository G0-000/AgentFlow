# ============================================================================
# AgentFlow · tools/builtins/terminal_tool.py —— 沙箱终端工具
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/tools/builtins/terminal_tool.py
# 对标来源: evoflow/tools/host_direct/terminal_tool.py（原版进程/会话管理，M4 简化为单命令）
# 里程碑: M4
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────────────┐
# │ terminal_run(command: str) -> str                    │
# │   @tool("terminal_run", return_direct=True)          │
# │   ① provider.acquire() 取沙箱                        │
# │   ② sandbox.execute_command(command)                 │
# │   ③ 审计 record（放行/拦截都记）                    │
# │   ④ 成功 → 命令输出；SandboxError → 友好提示        │
# └──────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 一切宿主命令必须走沙箱（Noop 时直接拒绝，Local 时目录隔离）——
#    工具层不提供任何"绕过沙箱"的路径。
# 2. 审计句柄用模块级注入（configure_sandbox_audit_repository），
#    对齐 knowledge_tool 的 configure_knowledge_service 模式。
# 3. return_direct=True：命令输出直接回给模型，不再二次加工。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. terminal_run: 沙箱终端工具（注册名 "terminal_run"）
# 2. configure_sandbox_audit_repository: CLI 装配时注入审计仓库
# 🔒 内部私有函数
# 1. _audit: 写审计记录（仓库未注入时静默跳过）
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. 不要提供绕过 get_sandbox_provider 的执行路径（安全闸唯一入口）
# 2. SandboxError 必须 catch → 拦截提示（不 catch 会炸模型工具循环）
# 3. 命令输出可能很长：LocalSandbox 已截断 500 字符详情
# ============================================================================

from __future__ import annotations

from langchain.tools import tool

from agentflow.persistence.sandbox_audit_repositories import SandboxAuditRepository
from agentflow.sandbox import SandboxError, get_sandbox_provider

# 审计仓库句柄（CLI 装配注入；未注入时审计静默跳过，不阻塞工具）
_audit_repo: SandboxAuditRepository | None = None


def configure_sandbox_audit_repository(repo: SandboxAuditRepository | None) -> None:
    """注入沙箱审计仓库（CLI main() 装配；None = 关闭审计）。"""
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
            subagent_name="terminal_run",
        )
    except Exception:  # noqa: BLE001,S110 —— 审计失败不影响工具主流程（调试期静默）
        pass


_TERMINAL_DESCRIPTION = """\
沙箱终端工具：在沙箱工作目录内执行 shell 命令并返回输出。
当需要查看系统状态、运行脚本、执行测试、批处理文件时使用。
注意: 命令在沙箱内执行，访问沙箱外路径会被拦截；命令需在超时（30s）内完成。
"""


@tool("terminal_run", description=_TERMINAL_DESCRIPTION, parse_docstring=False, return_direct=True)
def terminal_run(command: str) -> str:
    """在沙箱内执行命令（沙箱外访问被拦截，全程审计）。"""
    provider = get_sandbox_provider()
    sandbox = provider.get(provider.acquire())
    if sandbox is None:
        return "（沙箱不可用）"
    try:
        out = sandbox.execute_command(command)
        _audit("terminal_run", command, allowed=True)
        return out
    except SandboxError as exc:
        _audit("terminal_run", command, allowed=False, reason=str(exc))
        return f"（沙箱拦截）{exc}"
