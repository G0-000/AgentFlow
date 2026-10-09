# sandbox/local.py — local.py

> **文件路径**: `backend/packages/harness/agentflow/sandbox/local.py`
> **目录位置**: sandbox → local.py
> **职责**: 本地目录沙箱（M4 自研）——所有路径落在 root 内才放行，root 外一律拦截；root 内 cwd 执行命令 + 超时

## 📑 目录

- [📋 结构图](#📋-结构图)
- [📤 关键导出](#📤-关键导出)
- [💡 设计思想](#💡-设计思想)
- [🎯 实用场景](#🎯-实用场景)
- [📊 顺序执行链流程图](#📊-顺序执行链流程图)
- [🧩 代码解析（成块对照 local.py）](#🧩-代码解析成块对照-localpy)
- [❓ Q&A / 知识点](#❓-qa--知识点)
- [⚠️ 风险点](#⚠️-风险点)

## 📋 结构图

```text
┌──────────────────────────────────────────────────────┐
│ LocalSandbox(Sandbox)                                  │
│   root: Path（构造时 resolve + mkdir，所有操作基准）    │
│   _resolve(path): 核心安全闸                            │
│     expanduser → 相对路径拼 root → resolve() 规范化     │
│     → 前缀校验：p == root 或 root in p.parents         │
│     → 越界 raise SandboxPermissionError                │
│   execute_command: subprocess cwd=root + timeout        │
│   read_file / list_dir / write_file /                  │
│   update_file / delete_file：先 _resolve 再操作        │
│                                                      │
│ LocalSandboxProvider(SandboxProvider)                  │
│   root 默认 tempfile.mkdtemp(prefix=agentflow-sandbox-)│
│   固定返回单个 LocalSandbox，release 空操作             │
└──────────────────────────────────────────────────────┘
```

## 📤 关键导出

**类**

- `LocalSandbox`
- `LocalSandboxProvider`

**内部方法**

- `LocalSandbox._resolve(path)` —— 路径规范化 + 越界校验（核心安全闸）

## 💡 设计思想

1. **路径隔离靠规范化后的前缀校验**：任何路径先 `resolve()` 转成真实绝对路径
   （软链、`..`、`~` 全部归一），再校验它是否落在 root 内——写 `/etc/xxx`、
   `../` 逃逸、软链逃逸都在 `_resolve` 被拦（验收点 4 核心）。
2. **命令没有隔离**：`cwd=root` 只设置启动目录，`timeout` 只限制运行时间；
   `shell=True` 命令仍以当前 AgentFlow 进程权限运行，可读写宿主机可访问路径。
   `.sandbox` 不是 OS 级 jail。切勿向不可信用户开放命令执行。
3. **单例复用**：Provider 固定一个沙箱；测试注入临时目录，所有操作只碰临时目录。
4. **不缓存解析结果**：每次操作实时 resolve，防 TOCTOU 竞态（M4 够用）。

## 🎯 实用场景

1. CLI 生产装配：cli/main.py:175-176 `sandbox_root = project_root / ".sandbox"`
   → `set_sandbox_provider(LocalSandboxProvider(sandbox_root))`——子代理/终端操作
   落在项目 `.sandbox/` 内，宿主目录访问被 `_resolve` 拦截。
2. 测试注入：test_sandbox_guard.py:70-71 `LocalSandboxProvider(tmp_path / "sandbox-root")`
   + set，finally reset。
3. 工具消费：terminal_run → execute_command；read_file/write_file → 对应文件方法，
   全部经 `provider.get(provider.acquire())` 取到本类实例。

## 📊 顺序执行链流程图

以一次文件操作为例（命令执行链在块 4 单独说明）：

```text
工具调沙箱文件操作（request：read_file/write_file/delete_file…）
│
▼
先过 _resolve(path)              ← 所有文件操作的统一前置
│
▼
expanduser → 相对路径拼 root → resolve() 规范化为真实绝对路径
│
▼
前缀校验：p == root 或 root in p.parents？
│   ├─ 否 → raise SandboxPermissionError（越界拦截，验收点 4）
│   └─ 是 → 返回规范化路径 p
▼
在 p 上执行真实文件操作（read_text / write_bytes / unlink …）
│
▼
OSError → 包装为 SandboxFileError / SandboxFileNotFoundError
│
▼
工具层 except SandboxError → "（沙箱拦截）…" + 审计 allowed=False
```

**Mermaid 版（GitHub / 飞书渲染；VSCode 需装插件）**：

```mermaid
flowchart TD
    A["工具调用沙箱文件操作"] --> B["先过 _resolve 路径校验"]
    B --> C{"规范化后是否落在 root 内"}
    C -->|"否"| D["抛 SandboxPermissionError 拦截"]
    C -->|"是"| E["在真实路径上执行读写删"]
    E --> F{"是否发生 OSError"}
    F -->|"是"| G["包装为 SandboxFileError 或 NotFound"]
    F -->|"否"| H["返回内容或成功提示"]
```

## 🧩 代码解析（成块对照 local.py）

> 读法：每块先贴**完整代码**，再看块下方的整块解析。代码与文件一致，仅省略头部规范注释。

### 块 1：imports —— subprocess/shlex/tempfile + 4 个异常

```python
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
```

**结构简析**：标准库五件——`os`（list_dir 的 os.walk 按层遍历）、`shlex`（引用命令文本，错误消息里安全打印）、`subprocess`（执行命令）、`tempfile`（Provider 默认 root）、`pathlib.Path`（路径规范化核心工具）。异常侧把 exceptions.py 的 4 个子类全部 import，并继承 `Sandbox` / `SandboxProvider` 两个基类。

本块无可逐条解释的函数（仅 import）。

**补充**：LocalSandbox 是全项目唯一"按错误语义细分抛错"的实现——越界抛 Permission、缺文件抛 NotFound、OSError 包装成 File、超时/非零码抛 Command。

### 块 2：`LocalSandbox.__init__` —— root 规范化 + 建目录 + id 命名

```python
class LocalSandbox(Sandbox):
    """本地文件 API 以 root 为边界；命令执行并不受该路径边界限制。

    M4 定位：read/write/list 等文件 API 做路径校验（验收点 4）。
    execute_command 使用宿主机 shell，cwd 只是初始目录；没有 OS 级进程隔离。
    """

    def __init__(self, root: str | Path):
        root_path = Path(root).resolve()
        root_path.mkdir(parents=True, exist_ok=True)
        super().__init__(id=f"local-{root_path.name or 'root'}")
        self._root = root_path
```

**结构简析**：`LocalSandbox(Sandbox)` 子类。构造时就把 root 钉死——root 自身先 resolve 规范化、自动建目录、生成 id。docstring 自曝短板：不做 OS 级进程 jail。

**`__init__()` 参数逐条解释**：

| 参数 | 类型 | 默认值 | 含义 |
|---|---|---|---|
| `root` | `str \| Path` | 必填 | 沙箱根目录；构造时 `Path(root).resolve()` 规范化成绝对路径（后续所有前缀校验都拿它做基准），再 `mkdir(parents=True, exist_ok=True)` 自动建（CLI 的 `.sandbox`、测试 tmp 目录都自动就绪） |

**落库要点**：id 取 `local-{root名}`（根目录无名时兜底 `'root'`），如 `.sandbox` 目录即 id=`local-.sandbox`；`self._root` 存已 resolve 的绝对路径。

### 块 3：`_resolve` —— 核心安全闸（越界拦截全靠它）

```python
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
```

**结构简析**：核心安全闸，四步走，每步对应一类逃逸手法——① `expanduser()` 展开 `~`；② 相对路径拼 root；③ `p.resolve()` 规范化（`..` 向上逃逸、软链指向沙箱外都在这步归一）；④ 前缀校验，不在 root 内抛 Permission。

**`_resolve()` 参数逐条解释**：

| 参数 | 类型 | 默认值 | 含义 |
|---|---|---|---|
| `path` | `str \| Path` | 必填 | 调用方给的路径，可能是相对/`../`/`~/`/软链/绝对宿主路径；相对路径以沙箱 root 为基准拼（而非调用时进程 cwd） |

校验规则：`p != self._root and self._root not in p.parents` 为真即越界——`p == self._root`（访问根目录本身）放行，其余必须 `root in p.parents`。

**落库要点**：越界抛 `SandboxPermissionError`，details 带 `root={self._root}` 便于审计定位。必须用 `resolve()` 而非 `normpath()`——后者不解析软链，会被软链逃逸骗过。

### 块 4：`execute_command` —— cwd 限制 + 超时，无 OS jail

```python
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
```

**结构简析**：`shell=True` 接受完整 shell 串，并以 AgentFlow 进程权限执行。`cwd=self._root` 只指定起始工作目录，`timeout` 只限制执行时长；二者都不限制命令访问宿主机文件或启动子进程。错误分两路：超时 → `SandboxCommandError`（`from None` 不串栈）；非零退出码 → 同样抛 Command，details 带输出前 500 字符。

**`execute_command()` 参数逐条解释**：

| 参数 | 类型 | 默认值 | 含义 |
|---|---|---|---|
| `command` | `str` | 必填 | 以宿主机进程权限执行的 shell 字符串；`cwd=self._root` 只设置启动目录，不构成访问控制 |
| `timeout` | `int` | `30` | 超时秒数；超时抛 `SandboxCommandError("命令超时（>{timeout}s）…")` |

**落库要点**：输出合并 `stdout+stderr`、strip，空输出返回 `"(无输出)"`；非零码 `check=False` 不自动抛，走 returncode 分支转 Command。`execute_command` 不经 `_resolve`，绝对路径和 shell 操作均可触及该进程有权访问的宿主机资源；项目没有提供 OS 级隔离实现。

### 块 5：`read_file` / `list_dir` —— 读向操作

```python
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
```

**结构简析**：两个读向方法，每个第一行都是 `p = self._resolve(path)`——文件类操作没有例外，先过安全闸再谈业务。read_file 固定 utf-8 读文本；list_dir 用 `os.walk` 按层遍历，到深度上限 `dirs[:] = []` 停止下钻，结果排序后 `[:500]` 截断防目录爆炸。OSError 一律 `from exc` 包装成 SandboxFileError（保留原始异常链）。

**`read_file()` 参数逐条解释**：

| 参数 | 类型 | 默认值 | 含义 |
|---|---|---|---|
| `path` | `str` | 必填 | 要读的文件路径，先过 `_resolve`；不是文件（`is_file()` 假）抛 `SandboxFileNotFoundError`；utf-8 读文本返回 |

**`list_dir()` 参数逐条解释**：

| 参数 | 类型 | 默认值 | 含义 |
|---|---|---|---|
| `path` | `str` | 必填 | 要列的目录路径，先过 `_resolve`；不是目录抛 `SandboxFileNotFoundError` |
| `max_depth` | `int` | `2` | 最多下钻层数；`depth = max(1, int(max_depth))` 保底 1，level≥depth 即 `dirs[:]=[]` 停钻；depth=1 只列直接子项 |

**落库要点**：list_dir 返回相对路径字符串列表，`[:500]` 硬截断防目录爆炸（超 500 条只看到前 500，非错误）。

### 块 6：`write_file` / `update_file` / `delete_file` —— 写向操作

```python
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
```

**结构简析**：三个写向方法结构同构——先 `_resolve`，再 try 真实 IO，OSError 包装成 SandboxFileError。差异在语义：write_file 文本（utf-8，append 决定追加/覆盖，写前自动建父目录）；update_file 二进制整体替换（`write_bytes`，不做编码）；delete_file 先 `exists()` 再 `unlink()`。

**`write_file()` 参数逐条解释**：

| 参数 | 类型 | 默认值 | 含义 |
|---|---|---|---|
| `path` | `str` | 必填 | 要写的文件路径，先过 `_resolve`；写前 `p.parent.mkdir(parents=True, exist_ok=True)` 自动建父目录（模型写 `a/b.txt` 不必先建目录） |
| `content` | `str` | 必填 | 文本内容，utf-8 写 |
| `append` | `bool` | `False` | True 时 `open("a")` 追加；False 时 `write_text` 覆盖 |

**`update_file()` 参数逐条解释**：

| 参数 | 类型 | 默认值 | 含义 |
|---|---|---|---|
| `path` | `str` | 必填 | 要更新的文件路径，先过 `_resolve` |
| `content` | `bytes` | 必填 | 二进制内容，`write_bytes` 整体替换（不做编码） |

**`delete_file()` 参数逐条解释**：

| 参数 | 类型 | 默认值 | 含义 |
|---|---|---|---|
| `path` | `str` | 必填 | 要删的文件路径，先过 `_resolve`；`exists()` 为假抛 `SandboxFileNotFoundError`，否则 `unlink()` |

**落库要点**：越界在三个方法里被同一道 `_resolve` 闸统一拦截——测试 test_sandbox_guard.py:33 写 `/etc/agentflow_should_not_write.txt` 被拒、:43 写 `../escape.txt` 被拒。

### 块 7：`LocalSandboxProvider` —— 固定单例，root 默认临时目录

```python
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
```

**结构简析**：`LocalSandboxProvider(SandboxProvider)`——固定返回单个 LocalSandbox 的单例 Provider。`root=None` 时自动建 `agentflow-sandbox-` 前缀临时目录（裸用也能跑，测试友好）；CLI 则显式传项目 `.sandbox`。三个接口方法与 NoopSandboxProvider 同构（固定单例、id 匹配查表、release 空操作），区别只在背后那个 LocalSandbox 真的读写磁盘。

**`__init__()` 参数逐条解释**：

| 参数 | 类型 | 默认值 | 含义 |
|---|---|---|---|
| `root` | `str \| Path \| None` | `None` | 沙箱根；None 时 `tempfile.mkdtemp(prefix="agentflow-sandbox-")` 自动建临时目录；构造即 `LocalSandbox(root)` |

**`acquire()` 参数逐条解释**：

| 参数 | 类型 | 默认值 | 含义 |
|---|---|---|---|
| `thread_id` | `str \| None` | `None` | 线程标识（基类契约参数，本实现单例不用它）；直接返回 `self._sandbox.id` |

**`get()` 参数逐条解释**：

| 参数 | 类型 | 默认值 | 含义 |
|---|---|---|---|
| `sandbox_id` | `str` | 必填 | 要取的沙箱 id；等于 `self._sandbox.id` 返回该单例，否则 `None` |

**`release()` 参数逐条解释**：

| 参数 | 类型 | 默认值 | 含义 |
|---|---|---|---|
| `sandbox_id` | `str` | 必填 | 要归还的沙箱 id；本实现空操作 `pass`——单例沙箱无状态，无需归还 |

**落库要点**：默认 root 是临时目录，裸用（未显式传 root）时文件落系统临时区、重启即失；CLI 生产装配务必显式传项目 `.sandbox`。

## ❓ Q&A / 知识点

### 1. 沙箱越界怎么拦的？（2026-10-01 用户提问）

**一句话**：全靠 `_resolve` 一道闸——相对路径以 root 为基准拼好，再 `resolve()`
规范化成真实绝对路径，最后做前缀校验：不在 root 内就抛 `SandboxPermissionError`。

四步拦截链（local.py:77-91）：

```text
调用方给的 path（可能是相对/../~/软链/绝对宿主路径）
│
▼ expanduser()      展开 ~
▼ 相对路径 → self._root / path   ← 相对路径一律以沙箱 root 为基准，
│                                   不按"调用时进程 cwd"算（关键）
▼ resolve()         .. 归一、软链解析成真实路径
▼ 前缀校验          p == root 或 root in p.parents？
└─ 否则 → raise SandboxPermissionError（details 带 root）
```

测试佐证（tests/test_sandbox_guard.py）：

| 逃逸手法 | 测试 | 结果 |
|---|---|---|
| 绝对宿主路径 `/etc/...` | :32-36 | SandboxPermissionError |
| `../` 向上逃逸 | :39-43 | SandboxPermissionError |
| 沙箱内正常写读 | :21-25 | 放行 |

**注意边界**：这是**文件 API 路径级**隔离；`execute_command` 不经过 `_resolve`，
可以访问当前进程有权限访问的宿主机资源。CLI 默认使用 `.sandbox` 作为文件 API 的
root，不代表 shell 被限制在 `.sandbox` 中。

### 2. 为什么用 `resolve()` 而不是 `normpath()` 做规范化？

**一句话**：`normpath` 只做字符串归一（处理 `..`），不解析软链——沙箱里放一个
指向 `/etc` 的符号链接，normpath 会被骗过；`resolve()` 实时把路径解析成真实位置，
软链逃逸同样落网。源码头部风险点 1 即此告诫。

### 3. `execute_command` 只设了 cwd=root，命令会被限制在 root 内吗？

不会。M4 的路径边界只适用于 read/write/list 等文件 API。shell 命令以 AgentFlow
进程权限执行；`cwd` 是启动目录，命令可以访问进程有权限访问的宿主机资源。当前代码
没有实现 OS 级进程隔离，也不能把未来里程碑当作现有保护。

## ⚠️ 风险点

1. **execute_command 可访问宿主机资源**：shell 以 AgentFlow 进程权限运行；`.sandbox`
   只约束文件 API 的路径解析，不约束 shell。对不可信输入开放该工具前必须增加真正的
   OS/容器级隔离和权限边界；当前实现没有这些保护。
2. `_resolve` 必须用 `resolve()`（软链/`..` 全规范化）——改用 `normpath` 会被软链绕过。
3. LocalSandbox 不缓存解析结果，每次操作实时 resolve——防 TOCTOU 竞态，M4 够用；
   高频调用时可留意重复 resolve 开销。
4. list_dir 结果 `[:500]` 硬截断——超 500 条的目录只看到前 500（排序后），不是错误。
5. Provider 默认 root 是 `tempfile.mkdtemp()` 临时目录——裸用（未显式传 root）时
   文件落在系统临时区，重启即失；CLI 生产装配务必显式传项目 `.sandbox`。

---
_2026-10-01 M4 补齐：目录 + 顺序执行链流程图 + 成块代码解析（+Q&A）。_
_2026-10-03 重构：代码解析段按「结构简析 + 参数逐条表格 + 落库要点」规范化（代码块零改动）。_
