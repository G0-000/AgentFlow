# ============================================================================
# AgentFlow · sandbox/local.py —— 本地目录沙箱（M4 自研）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/sandbox/local.py
# 对标来源: 原版无此实现（原版依赖远程容器）；M4 自研目录隔离沙箱。
# 里程碑: M4
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────────────┐
# │ LocalSandbox(Sandbox)                                │
# │   root: 沙箱根目录（所有路径必须落在其内）           │
# │   _resolve(path): realpath 后前缀校验                │
# │     ├─ 越界 → SandboxPermissionError（验收点 4）     │
# │   execute_command: subprocess cwd=root + 超时        │
# │   read_file / write_file / update_file / delete_file │
# │   → 先 _resolve 再操作                               │
# │                                                      │
# │ LocalSandboxProvider(SandboxProvider)                │
# │   acquire → 固定单例（root 默认 tmp 目录）           │
# └──────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 路径隔离：realpath 规范化后必须落在 root 内——写 /etc/xxx、
#    ../ 逃逸、软链逃逸全部被 _resolve 拦截（验收点 4 核心）。
# 2. 命令隔离：subprocess cwd=root + timeout；
#    ⚠️ 命令内部 `cd /etc && …` 可逃逸 cwd——完整 OS 级 jail
#    留 M5（execution security），M4 文档风险点如实标注。
# 3. 单例复用：测试注入 LocalSandboxProvider(tmp_path)，
#    所有沙箱操作都在临时目录内发生，不碰宿主。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. LocalSandbox / LocalSandboxProvider
# 🔒 内部私有函数
# 1. _resolve: 路径规范化 + 越界校验（核心安全闸）
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. _resolve 必须用 resolve()（软链/.. 都规范化）——用 normpath 会被软链绕过
# 2. execute_command 无 OS 级 jail：命令逃逸防护留 M5，勿声称已隔离
# 3. LocalSandbox 不缓存：每次操作实时 resolve，防 TOCTOU 竞态（M4 够用）
# ============================================================================

from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
from pathlib import Path

from agentflow.sandbox.exceptions import (
    SandboxCommandError,
    SandboxFileError,
    SandboxFileNotFoundError,
    SandboxPermissionError,
)
from agentflow.sandbox.sandbox import Sandbox
from agentflow.sandbox.sandbox_provider import SandboxProvider


class LocalSandbox(Sandbox):
    """本地目录沙箱：root 目录内可读写/执行，root 外一律拒绝。

    M4 定位：文件路径级隔离（验收点 4）。命令执行 cwd 限制 + 超时，
    但不做 OS 级进程 jail（`cd /etc && …` 可逃逸 cwd，见风险点 2）。
    """

    def __init__(self, root: str | Path):
        root_path = Path(root).resolve()
        root_path.mkdir(parents=True, exist_ok=True)
        super().__init__(id=f"local-{root_path.name or 'root'}")
        self._root = root_path

    # ---- 核心安全闸：路径校验 ----
    def _resolve(self, path: str | Path) -> Path:
        """规范化路径并校验落在 root 内；越界抛 SandboxPermissionError。

        相对路径以沙箱 root 为基准（沙箱内文件用相对路径写即可）。
        """
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = self._root / p
        p = p.resolve()
        if p != self._root and self._root not in p.parents:
            raise SandboxPermissionError(
                f"路径越界（沙箱外）: {path}",
                details=f"root={self._root}",
            )
        return p

    # ---- 命令执行 ----
    def execute_command(self, command: str, timeout: int = 30) -> str:
        """在沙箱根目录内执行命令（shell 字符串，cwd=root，超时控制）。"""
        try:
            proc = subprocess.run(
                command,
                shell=True,  # 沙箱设计如此：接受完整 shell 串，靠 cwd+超时限制
                check=False,  # 显式不抛：非零码走下方 returncode 分支转 SandboxCommandError
                cwd=self._root,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise SandboxCommandError(
                f"命令超时（>{timeout}s）: {shlex.quote(command)[:80]}"
            ) from None
        out = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0:
            raise SandboxCommandError(
                f"命令失败（exit={proc.returncode}）: {shlex.quote(command)[:80]}",
                details=out[:500],
            )
        return out.strip() or "(无输出)"

    # ---- 文件操作 ----
    def read_file(self, path: str) -> str:
        p = self._resolve(path)
        if not p.is_file():
            raise SandboxFileNotFoundError(f"文件不存在: {path}")
        try:
            return p.read_text(encoding="utf-8")
        except OSError as exc:
            raise SandboxFileError(f"读取失败: {path}（{exc}）") from exc

    def list_dir(self, path: str, max_depth: int = 2) -> list[str]:
        """列出目录内容（相对路径，最多 max_depth 层）。

        depth=1 只列直接子项；depth=2 再下一层；os.walk 到深度上限
        即 dirs[:] = [] 停止下钻（原 rglob 写法会无限递归，已修正）。
        """
        p = self._resolve(path)
        if not p.is_dir():
            raise SandboxFileNotFoundError(f"目录不存在: {path}")
        depth = max(1, int(max_depth))
        out: list[str] = []
        for root, dirs, files in os.walk(p):
            level = len(Path(root).relative_to(p).parts)  # 0 = p 本身
            if level >= depth:
                dirs[:] = []  # 到深度上限，不再下钻
            for name in sorted(dirs + files):
                if level < depth:
                    out.append(str(Path(root).relative_to(p) / name))
        return out[:500]  # 上限 500 条防爆炸

    def write_file(self, path: str, content: str, append: bool = False) -> None:
        p = self._resolve(path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)  # 父目录自动建（工具写 a/b.txt 不必先建目录）
            if append:
                with p.open("a", encoding="utf-8") as f:
                    f.write(content)
            else:
                p.write_text(content, encoding="utf-8")
        except OSError as exc:
            raise SandboxFileError(f"写入失败: {path}（{exc}）") from exc

    def update_file(self, path: str, content: bytes) -> None:
        p = self._resolve(path)
        try:
            p.write_bytes(content)
        except OSError as exc:
            raise SandboxFileError(f"更新失败: {path}（{exc}）") from exc

    def delete_file(self, path: str) -> None:
        p = self._resolve(path)
        if not p.exists():
            raise SandboxFileNotFoundError(f"文件不存在: {path}")
        try:
            p.unlink()
        except OSError as exc:
            raise SandboxFileError(f"删除失败: {path}（{exc}）") from exc


class LocalSandboxProvider(SandboxProvider):
    """本地目录沙箱提供者：固定返回单个 LocalSandbox。

    用法:
        provider = LocalSandboxProvider(tempfile.mkdtemp())
        set_sandbox_provider(provider)  # 测试注入
    """

    def __init__(self, root: str | Path | None = None):
        root = root or tempfile.mkdtemp(prefix="agentflow-sandbox-")
        self._sandbox = LocalSandbox(root)

    def acquire(self, thread_id: str | None = None) -> str:
        return self._sandbox.id

    def get(self, sandbox_id: str) -> Sandbox | None:
        return self._sandbox if sandbox_id == self._sandbox.id else None

    def release(self, sandbox_id: str) -> None:
        pass  # 单例沙箱无状态，无需归还
