# ============================================================================
# AgentFlow · sandbox/__init__.py —— 沙箱包入口
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/sandbox/__init__.py
# 对标来源: evoflow/sandbox/__init__.py
# 里程碑: M4
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────────────┐
# │ sandbox/ 对外导出:                                     │
# │   Sandbox / SandboxProvider（接口）                  │
# │   NoopSandbox / NoopSandboxProvider（默认拒绝）       │
# │   LocalSandbox / LocalSandboxProvider（目录隔离）     │
# │   SandboxError 及其子类（统一异常）                   │
# │   get/set/reset_sandbox_provider（单例管理）          │
# └──────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 包入口 re-export 全部公共符号，工具层一个 import 拿全。
# 2. 注意：sandbox_provider 的单例函数在 __init__ 直接导出，
#    工具层用 get_sandbox_provider() 拿当前沙箱。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. 接口类 / 实现类 / 异常类 / 单例管理函数（见 __all__）
# 🔒 内部私有函数
# 无
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. 新增实现类记得导出；单例函数名保持（工具层依赖）
# ============================================================================

from __future__ import annotations

from agentflow.sandbox.exceptions import (
    SandboxCommandError,
    SandboxError,
    SandboxFileError,
    SandboxFileNotFoundError,
    SandboxPermissionError,
)
from agentflow.sandbox.local import LocalSandbox, LocalSandboxProvider
from agentflow.sandbox.noop import NoopSandbox, NoopSandboxProvider
from agentflow.sandbox.sandbox import Sandbox
from agentflow.sandbox.sandbox_provider import (
    SandboxProvider,
    get_sandbox_provider,
    reset_sandbox_provider,
    set_sandbox_provider,
)

__all__ = [
    "LocalSandbox",
    "LocalSandboxProvider",
    "NoopSandbox",
    "NoopSandboxProvider",
    "Sandbox",
    "SandboxCommandError",
    "SandboxError",
    "SandboxFileError",
    "SandboxFileNotFoundError",
    "SandboxPermissionError",
    "SandboxProvider",
    "get_sandbox_provider",
    "reset_sandbox_provider",
    "set_sandbox_provider",
]
