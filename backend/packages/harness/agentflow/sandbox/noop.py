# ============================================================================
# AgentFlow · sandbox/noop.py —— 空沙箱（桌面默认）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/sandbox/noop.py
# 对标来源: evoflow/sandbox/noop.py（同款：全操作拒绝）
# 里程碑: M4
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────────────┐
# │ NoopSandbox(Sandbox)                                 │
# │   所有方法 → raise SandboxError("未配置沙箱")        │
# │ NoopSandboxProvider(SandboxProvider)                 │
# │   acquire → "noop"（固定单例 id）                     │
# │   get("noop") → NoopSandbox 单例                      │
# │   release → 空                                        │
# └──────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 桌面环境默认无真实沙箱：任何宿主操作直接拒绝（fail-closed），
#    不让子代理静默跑在宿主上（安全默认值）。
# 2. CLI 不配沙箱时 terminal_run 等工具返回"沙箱未配置"，
#    比"偷偷跑在用户机器上"安全。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. NoopSandbox / NoopSandboxProvider
# 🔒 内部私有函数
# 无
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. fail-closed：宁可拒绝不可放行，勿给 Noop 加"透传"行为
# 2. 单例：每次 get 返回同一实例（无状态，安全）
# ============================================================================

from __future__ import annotations

from agentflow.sandbox.exceptions import SandboxError
from agentflow.sandbox.sandbox import Sandbox
from agentflow.sandbox.sandbox_provider import SandboxProvider


class NoopSandbox(Sandbox):
    """空沙箱：所有操作抛 SandboxError（桌面默认，无真实沙箱）。"""

    def __init__(self):
        super().__init__(id="noop")
        self._deny_msg = "沙箱未配置（NoopSandbox）：宿主系统操作被拒绝"

    def execute_command(self, command: str, timeout: int = 30) -> str:
        raise SandboxError(self._deny_msg, details=f"command={command[:80]}")

    def read_file(self, path: str) -> str:
        raise SandboxError(self._deny_msg, details=f"path={path}")

    def list_dir(self, path: str, max_depth: int = 2) -> list[str]:
        raise SandboxError(self._deny_msg, details=f"path={path}")

    def write_file(self, path: str, content: str, append: bool = False) -> None:
        raise SandboxError(self._deny_msg, details=f"path={path}")

    def update_file(self, path: str, content: bytes) -> None:
        raise SandboxError(self._deny_msg, details=f"path={path}")

    def delete_file(self, path: str) -> None:
        raise SandboxError(self._deny_msg, details=f"path={path}")


class NoopSandboxProvider(SandboxProvider):
    """空沙箱提供者：固定返回单个 NoopSandbox（id="noop"）。"""

    def __init__(self):
        self._sandbox = NoopSandbox()

    def acquire(self, thread_id: str | None = None) -> str:
        return self._sandbox.id

    def get(self, sandbox_id: str) -> Sandbox | None:
        return self._sandbox if sandbox_id == self._sandbox.id else None

    def release(self, sandbox_id: str) -> None:
        pass  # 单例无状态，无需归还
