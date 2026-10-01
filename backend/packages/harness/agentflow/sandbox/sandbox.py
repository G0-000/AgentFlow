# ============================================================================
# AgentFlow · sandbox/sandbox.py —— 沙箱抽象基类
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/sandbox/sandbox.py
# 对标来源: evoflow/sandbox/sandbox.py（原版 6 抽象方法，M4 同款）
# 里程碑: M4
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────────────┐
# │ Sandbox(ABC)                                         │
# │   id: str（沙箱唯一标识）                            │
# │   execute_command(command, timeout) -> str           │
# │   read_file(path) -> str                             │
# │   list_dir(path, max_depth=2) -> list[str]           │
# │   write_file(path, content, append=False)            │
# │   update_file(path, content: bytes)                  │
# │   delete_file(path)                                  │
# │   └── 实现: NoopSandbox（全拒绝）                   │
# │        LocalSandbox（目录隔离，M4 自研）             │
# └──────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. ABC 定义"沙箱能做什么"，Provider 决定"用哪个沙箱"——
#    工具只依赖接口，不感知实现（桌面 noop / 本地目录 / 远程容器）。
# 2. update_file 收 bytes（原版同款）：二进制安全，替换整个文件内容。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. Sandbox: 沙箱抽象基类（6 个抽象方法 + id）
# 🔒 内部私有函数
# 无
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. 新增能力 = 加抽象方法 → 所有实现（noop/local）都要同步
# 2. 方法签名保持 str/bytes 语义，勿混（append 布尔 vs 内容编码）
# ============================================================================

from __future__ import annotations

from abc import ABC, abstractmethod


class Sandbox(ABC):
    """沙箱抽象基类：子代理所有宿主系统操作都经这里。

    子类必须实现 6 个抽象方法；越界/权限问题抛 SandboxError。
    """

    def __init__(self, id: str):
        self._id = id

    @property
    def id(self) -> str:
        """沙箱唯一标识（Provider 查表键）。"""
        return self._id

    @abstractmethod
    def execute_command(self, command: str, timeout: int = 30) -> str:
        """在沙箱内执行命令，返回 stdout+stderr 文本。"""

    @abstractmethod
    def read_file(self, path: str) -> str:
        """读取沙箱内文件内容。"""

    @abstractmethod
    def list_dir(self, path: str, max_depth: int = 2) -> list[str]:
        """列出沙箱内目录（相对路径列表，深度限制防爆炸）。"""

    @abstractmethod
    def write_file(self, path: str, content: str, append: bool = False) -> None:
        """写入/追加沙箱内文件。"""

    @abstractmethod
    def update_file(self, path: str, content: bytes) -> None:
        """整体替换沙箱内文件内容（二进制安全）。"""

    @abstractmethod
    def delete_file(self, path: str) -> None:
        """删除沙箱内文件。"""
