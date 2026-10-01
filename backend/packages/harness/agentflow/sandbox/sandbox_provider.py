# ============================================================================
# AgentFlow · sandbox/sandbox_provider.py —— 沙箱提供者（单例）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/sandbox/sandbox_provider.py
# 对标来源: evoflow/sandbox/sandbox_provider.py（原版单例 + set 注入）
# 里程碑: M4
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────────────┐
# │ SandboxProvider(ABC)                                 │
# │   acquire(thread_id?) -> id    取一个沙箱           │
# │   get(sandbox_id) -> Sandbox|None  按 id 取实例      │
# │   release(sandbox_id)         归还（可空实现）       │
# │                                                      │
# │ get_sandbox_provider() -> SandboxProvider（单例）    │
# │ set_sandbox_provider(p)     测试注入                 │
# │ reset_sandbox_provider()    重置回默认               │
# └──────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 单例 + 依赖注入：生产默认 Noop（桌面无真实沙箱），
#    测试 set_sandbox_provider(LocalSandboxProvider(tmp)) 注入。
# 2. 工具层只调 get_sandbox_provider()，不感知全局状态。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. SandboxProvider / get_sandbox_provider / set_sandbox_provider /
#    reset_sandbox_provider
# 🔒 内部私有函数
# 无
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. set 注入后要 reset（否则影响其他测试/会话）
# 2. 单例是模块级全局：多线程访问用锁保护
# ============================================================================

from __future__ import annotations

import threading
from abc import ABC, abstractmethod

from agentflow.sandbox.sandbox import Sandbox


class SandboxProvider(ABC):
    """沙箱提供者：负责创建/获取/归还沙箱实例。"""

    @abstractmethod
    def acquire(self, thread_id: str | None = None) -> str:
        """获取一个沙箱，返回其 id。"""

    @abstractmethod
    def get(self, sandbox_id: str) -> Sandbox | None:
        """按 id 取沙箱实例（无则 None）。"""

    @abstractmethod
    def release(self, sandbox_id: str) -> None:
        """归还沙箱（当前实现多为空操作）。"""


# ---- 单例状态 ----
_provider: SandboxProvider | None = None
_provider_lock = threading.Lock()


def get_sandbox_provider() -> SandboxProvider:
    """获取全局沙箱提供者（默认 NoopSandboxProvider，惰性创建）。"""
    global _provider
    with _provider_lock:
        if _provider is None:
            # 延迟导入：避免包级循环（noop 依赖 sandbox.py）
            from agentflow.sandbox.noop import NoopSandboxProvider

            _provider = NoopSandboxProvider()
        return _provider


def set_sandbox_provider(provider: SandboxProvider | None) -> None:
    """注入沙箱提供者（测试用）；传 None 表示恢复默认。"""
    global _provider
    with _provider_lock:
        _provider = provider


def reset_sandbox_provider() -> None:
    """重置为默认提供者（测试 teardown 用）。"""
    set_sandbox_provider(None)
