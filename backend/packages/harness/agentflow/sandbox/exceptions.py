# ============================================================================
# AgentFlow · sandbox/exceptions.py —— 沙箱异常
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/sandbox/exceptions.py
# 对标来源: evoflow/sandbox/exceptions.py（原版 8 类，M4 裁剪 5 类）
# 里程碑: M4
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────────────┐
# │ SandboxError(Exception)        沙箱异常基类            │
# │   ├─ SandboxPermissionError  越界/权限拒绝            │
# │   ├─ SandboxFileError        文件操作失败             │
# │   ├─ SandboxFileNotFoundError 文件不存在              │
# │   └─ SandboxCommandError     命令执行失败             │
# └──────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 工具层 catch SandboxError → 友好提示；不 catch 到
#    非沙箱异常（模型/网络错误走各自路径）。
# 2. 细分类型让工具能区分"被拦截（权限）"与"真失败（IO）"。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. SandboxError 及其 4 个子类
# 🔒 内部私有函数
# 无
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. 工具层必须 catch SandboxError（不 catch 会炸模型工具循环）
# 2. details 可选：携带命令/路径上下文，不塞敏感信息
# ============================================================================

from __future__ import annotations


class SandboxError(Exception):
    """沙箱操作异常基类（工具层统一 catch 此类）。"""

    def __init__(self, message: str, details: str | None = None):
        super().__init__(message)
        self.details = details


class SandboxPermissionError(SandboxError):
    """沙箱权限拒绝：路径越界 / 操作不允许。"""


class SandboxFileError(SandboxError):
    """沙箱内文件操作失败（读写删等）。"""


class SandboxFileNotFoundError(SandboxFileError):
    """沙箱内文件不存在。"""


class SandboxCommandError(SandboxError):
    """沙箱内命令执行失败（非零退出码/超时）。"""
