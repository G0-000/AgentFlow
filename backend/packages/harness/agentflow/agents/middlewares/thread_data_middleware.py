# ============================================================================
# AgentFlow · agents/middlewares/thread_data_middleware.py —— 线程数据目录中间件
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/agents/middlewares/thread_data_middleware.py
# 对标来源: evoflow/agents/middlewares/thread_data_middleware.py
#   原版：为每个 thread 创建 user-data/{workspace,uploads,outputs} 目录，
#   lazy_init 思想 + Paths/workspace_context；M2 简化【同步建目录】。
# 里程碑: M2
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────────────┐
# │ ThreadDataMiddlewareState(AgentState)                       │
# │   thread_data: NotRequired[dict | None]                     │
# │                                                             │
# │ ThreadDataMiddleware(AgentMiddleware)                       │
# │   before_agent(state, runtime) → dict | None                │
# │     ① 从 runtime 取 thread_id（get_config）                 │
# │     ② 路径 = {base}/threads/{thread_id}/user-data/          │
# │              workspace / uploads / outputs                   │
# │     ③ 同步 mkdir（M2 eager；原版 lazy 按需创建）             │
# │     ④ 返回 {"thread_data": {...}} → merge 进 state          │
# └────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 参考文档：doc/doc-dev/01-里程碑/M2-工具与中间件.md §2
# 2. 原版思想：每个会话有独立工作目录（文件类工具的输出落这里），
#    是后续文件读写工具（M3+）的"地盘"。目录结构对齐原版命名。
# 3. M2 简化：去掉 Paths 解析，直接用 data/ 相对路径；
#    建目录用 eager（一次建好）而非 lazy（按需创建），代码更简单。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. ThreadDataMiddlewareState: 中间件状态（挂 thread_data 字段）
# 2. ThreadDataMiddleware: 线程数据目录中间件（before_agent 钩子）
# 🔒 内部私有函数
# 1. _thread_id_from_runtime: 从 langgraph 运行时配置取 thread_id
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. _DEFAULT_BASE_DIR="data" 是线程数据根；改它会让会话工作区整体迁移
# 2. 拿不到 thread_id 时静默跳过（before_agent 返回 None），不报错
# 3. M2 为 eager 建目录；改回 lazy 需同步调整 M3 文件工具的调用时机
# ============================================================================
from __future__ import annotations

from pathlib import Path
from typing import Any, NotRequired

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langgraph.config import get_config

# 默认线程数据根（相对项目 data 目录；对齐原版 base_dir 语义）
_DEFAULT_BASE_DIR = "data"


class ThreadDataMiddlewareState(AgentState):
    """与 ThreadState 兼容：额外挂 thread_data 字段。"""

    thread_data: NotRequired[dict[str, Any] | None]


class ThreadDataMiddleware(AgentMiddleware[ThreadDataMiddlewareState]):
    """为每个线程创建独立数据目录（workspace/uploads/outputs）。"""

    state_schema = ThreadDataMiddlewareState

    def __init__(self, base_dir: str = _DEFAULT_BASE_DIR) -> None:
        """初始化。

        Args:
            base_dir: 线程数据根目录（默认 data/）。
        """
        self.base_dir = base_dir

    @staticmethod
    def _thread_id_from_runtime(runtime) -> str | None:
        """从 langgraph 运行时配置取 thread_id。"""
        try:
            config = get_config()
            return str((config.get("configurable") or {}).get("thread_id") or "")
        except Exception:  # noqa: BLE001 —— 拿不到 thread_id 时静默跳过
            return None

    def thread_paths(self, thread_id: str) -> dict[str, str]:
        """计算线程数据目录（不建目录，供调用方决定）。"""
        root = Path(self.base_dir) / "threads" / thread_id / "user-data"
        return {
            "thread_dir": str(root),
            "workspace": str(root / "workspace"),
            "uploads": str(root / "uploads"),
            "outputs": str(root / "outputs"),
        }

    def before_agent(self, state: ThreadDataMiddlewareState, runtime) -> dict[str, Any] | None:
        """图开始前建好线程目录（M2 eager 模式），路径信息写入 state。"""
        thread_id = self._thread_id_from_runtime(runtime)
        if not thread_id:
            return None
        paths = self.thread_paths(thread_id)
        # M2：直接建目录（原版 lazy 按需，简化版 eager 一次建好）
        for p in paths.values():
            Path(p).mkdir(parents=True, exist_ok=True)
        return {"thread_data": {"thread_id": thread_id, **paths}}
