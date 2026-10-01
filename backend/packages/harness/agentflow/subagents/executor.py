# ============================================================================
# AgentFlow · subagents/executor.py —— 子代理执行引擎
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/subagents/executor.py
# 对标来源: evoflow/subagents/executor.py（原版 911 行，M4 裁剪核心链路）
#   原版: 状态/结果/超时/后台任务/取消/流式回传；
#   M4:   状态/结果/同步执行/超时/重试/并行派发/后台任务。
# 里程碑: M4
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────────────┐
# │ SubagentStatus(Enum)                                        │
# │   PENDING / RUNNING / COMPLETED / FAILED / TIMED_OUT        │
# │                                                             │
# │ SubagentResult(@dataclass)                                  │
# │   task_id / status / result / error / started_at /          │
# │   completed_at                                              │
# │                                                             │
# │ SubagentExecutor                                            │
# │   __init__(config, tools, model=None)                       │
# │     → _filter_tools（白名单∩黑名单）                        │
# │   _build_agent() → create_agent（子代理专用）               │
# │   run(task, timeout) → SubagentResult（同步+超时）          │
# │   run_with_retry(task, max_retries) → 失败重试             │
# │   execute_async(task) → task_id（后台任务）                 │
# │   dispatch_parallel(tasks, max_parallel=3) → 并行≤3+回传   │
# │                                                             │
# │ 模块级: _background_tasks + get/list/cleanup                │
# └────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 子代理不挂 checkpointer：一次执行不持久化（M5 长任务再学）。
# 2. 并行控制 = ThreadPoolExecutor(max_workers) 天然排队：
#    派 5 个任务时第 4/5 个等空位（验收点 2：实际并行 ≤3）。
# 3. 超时 best-effort：future.result(timeout) 超时标记 TIMED_OUT，
#    底层线程无法真正中断（与原版一致，文档标注）。
# 4. 重试只针对 FAILED（模型调用异常可重试；TIMED_OUT 不重试——
#    超时重试只会再超时）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. SubagentStatus: 执行状态枚举
# 2. SubagentResult: 执行结果数据类
# 3. SubagentExecutor: 子代理执行器
# 4. get_background_task_result / list_background_tasks / cleanup_background_task
# 🔒 内部私有函数
# 1. _filter_tools: 工具过滤（白名单 + 黑名单）
# 2. _make_task_id: 生成任务 ID（uuid 短格式）
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. MAX_CONCURRENT_SUBAGENTS=3 是验收硬约束（并行 ≤3），勿放宽
# 2. 超时标记后底层任务仍可能在跑（best-effort），勿依赖强杀
# 3. dispatch_parallel 返回顺序 = 输入顺序（futures 按序取结果）
# ============================================================================

from __future__ import annotations

import logging
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from langchain.agents import create_agent
from langchain.tools import BaseTool
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage

from agentflow.subagents.config import SubagentConfig

logger = logging.getLogger(__name__)

# M4 验收硬约束：子代理并行上限（验收点 2：同时派 5 个 → 实际 ≤3）
MAX_CONCURRENT_SUBAGENTS = 3


class SubagentStatus(Enum):
    """子代理执行状态。"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


@dataclass
class SubagentResult:
    """子代理执行结果。

    字段:
        task_id: 本次执行唯一标识
        status: 终态/中间态（PENDING→RUNNING→COMPLETED/FAILED/TIMED_OUT）
        result: 完成时的最终文本
        error: 失败时的错误信息
        started_at / completed_at: 起止时间（UTC）
    """

    task_id: str
    status: SubagentStatus
    result: str | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


def _make_task_id() -> str:
    """生成任务 ID（uuid 前 12 位，AgentFlow 无 make_formatted_id）。"""
    return uuid.uuid4().hex[:12]


def _filter_tools(
    all_tools: list[BaseTool],
    allowed: list[str] | None,
    disallowed: list[str] | None,
) -> list[BaseTool]:
    """按子代理配置过滤工具（白名单 + 黑名单）。

    - allowed 非 None：只留白名单内工具（bash 子代理只有 terminal_run）
    - disallowed 非 None：剔除黑名单（防递归派发）
    """
    filtered = all_tools
    if allowed is not None:
        allowed_set = set(allowed)
        filtered = [t for t in filtered if t.name in allowed_set]
    if disallowed is not None:
        disallowed_set = set(disallowed)
        filtered = [t for t in filtered if t.name not in disallowed_set]
    return filtered


class SubagentExecutor:
    """子代理执行器（M4 最小版）。

    用法:
        executor = SubagentExecutor(config, tools, model=parent_model)
        result = executor.run("帮我查一下 x")
        results = executor.dispatch_parallel(["查 a", "写 b"], max_parallel=3)
    """

    def __init__(
        self,
        config: SubagentConfig,
        tools: list[BaseTool],
        model: BaseChatModel | None = None,
    ):
        """初始化执行器。

        参数:
            config: 子代理配置（name/system_prompt/tools 白黑名单…）
            tools: 父级全部工具（executor 按 config 过滤后给子代理）
            model: 父模型实例；config.model="inherit" 时直接用
        """
        self.config = config
        self.model = model
        self.tools = _filter_tools(tools, config.tools, config.disallowed_tools)
        logger.info("SubagentExecutor 初始化: %s（工具 %d 个）", config.name, len(self.tools))

    # ---- 内部：构建子代理 ----
    def _build_agent(self):
        """构建子代理 Agent（langchain create_agent，与 lead_agent 同 API）。

        无 checkpointer：子代理一次执行、不持久化（M5 长任务再学）。
        """
        if self.model is None:
            raise RuntimeError("子代理需要 model（父模型未注入）")
        return create_agent(
            model=self.model,
            tools=self.tools,
            system_prompt=self.config.system_prompt,
        )

    # ---- 内部：同步执行（不超时，供 run 包装） ----
    def _run_sync(self, task: str) -> SubagentResult:
        """真正执行子代理任务（线程内同步，无超时控制）。"""
        result = SubagentResult(
            task_id=_make_task_id(),
            status=SubagentStatus.RUNNING,
            started_at=datetime.now(UTC),
        )
        try:
            agent = self._build_agent()
            response = agent.invoke({"messages": [{"role": "user", "content": task}]})
            text = _extract_final_ai_text(response)
            result.result = text or "(子代理无文本输出)"
            result.status = SubagentStatus.COMPLETED
        except Exception as exc:  # noqa: BLE001 —— 模型调用异常统一收进 FAILED
            logger.warning("子代理 %s 执行失败: %s", self.config.name, exc)
            result.status = SubagentStatus.FAILED
            result.error = f"{type(exc).__name__}: {str(exc)[:200]}"
        result.completed_at = datetime.now(UTC)
        return result

    # ---- 对外：同步执行 + 超时 ----
    def run(self, task: str, timeout_seconds: int | None = None) -> SubagentResult:
        """同步执行子代理任务（带超时）。

        超时: future.result(timeout) 超时 → TIMED_OUT（best-effort，
        底层线程无法强杀，与原版一致）。

        注意: 超时路径必须 shutdown(wait=False)——`with ThreadPoolExecutor`
        退出时默认 wait=True 会等悬挂线程跑完，超时就不"及时返回"了。
        """
        timeout = timeout_seconds or self.config.timeout_seconds
        pool = ThreadPoolExecutor(max_workers=1)
        future: Future = pool.submit(self._run_sync, task)
        try:
            return future.result(timeout=timeout)
        except FuturesTimeoutError:
            logger.warning("子代理 %s 超时（%ss）", self.config.name, timeout)
            # 不等待悬挂线程：调用方及时拿 TIMED_OUT，底层线程由进程退出回收
            pool.shutdown(wait=False)
            return SubagentResult(
                task_id=_make_task_id(),
                status=SubagentStatus.TIMED_OUT,
                error=f"执行超时（{timeout} 秒）",
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )
        finally:
            # 正常路径（COMPLETED/FAILED）任务已结束，wait=False 无副作用；
            # 超时路径已提前 shutdown，重复调用无害
            pool.shutdown(wait=False)

    # ---- 对外：失败重试 ----
    def run_with_retry(
        self,
        task: str,
        max_retries: int = 2,
        timeout_seconds: int | None = None,
    ) -> SubagentResult:
        """执行并重试（只对 FAILED 重试；TIMED_OUT 不重试）。"""
        attempt = 0
        while True:
            result = self.run(task, timeout_seconds=timeout_seconds)
            if result.status != SubagentStatus.FAILED or attempt >= max_retries:
                return result
            attempt += 1
            logger.info("子代理 %s 第 %d 次重试（上次: %s）", self.config.name, attempt, result.error)

    # ---- 对外：后台任务 ----
    def execute_async(self, task: str, task_id: str | None = None) -> str:
        """后台启动子代理任务，立即返回 task_id（结果查 _background_tasks）。"""
        tid = task_id or _make_task_id()
        with _background_tasks_lock:
            _background_tasks[tid] = SubagentResult(
                task_id=tid,
                status=SubagentStatus.PENDING,
            )
        _scheduler_pool.submit(_run_background, self, tid, task)
        return tid

    # ---- 对外：并行派发（验收点 1/2/3 核心） ----
    def dispatch_parallel(
        self,
        tasks: list[str],
        max_parallel: int = MAX_CONCURRENT_SUBAGENTS,
    ) -> list[SubagentResult]:
        """把多个任务派给子代理并行执行，返回结果（按输入顺序）。

        并行控制: ThreadPoolExecutor(max_workers=min(max_parallel, 3))
        天然排队——派 5 个任务时，第 4/5 个等前序完成（验收点 2）。

        参数:
            tasks: 任务描述列表（每个都会被独立派发）
            max_parallel: 并行上限（硬约束 ≤3）

        返回:
            按输入顺序的 SubagentResult 列表（结果回传主 Agent）
        """
        workers = max(1, min(int(max_parallel), MAX_CONCURRENT_SUBAGENTS))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(self.run, t) for t in tasks]
            return [f.result() for f in futures]  # 按输入顺序取


# ---- 后台任务存储（模块级，进程内） ----
_background_tasks: dict[str, SubagentResult] = {}
_background_tasks_lock = threading.Lock()
# 调度线程池：execute_async 提交到这里（后台任务数量不限，执行仍受 run 超时控制）
_scheduler_pool = ThreadPoolExecutor(max_workers=5, thread_name_prefix="subagent-scheduler-")


def _run_background(executor: SubagentExecutor, task_id: str, task: str) -> None:
    """后台任务执行体：PENDING → RUNNING → 结果回写。"""
    with _background_tasks_lock:
        ent = _background_tasks.get(task_id)
        if ent is None:
            return
        ent.status = SubagentStatus.RUNNING
        ent.started_at = datetime.now(UTC)
    result = executor.run(task)
    with _background_tasks_lock:
        ent = _background_tasks.get(task_id)
        if ent is None:
            return
        ent.status = result.status
        ent.result = result.result
        ent.error = result.error
        ent.completed_at = result.completed_at


def get_background_task_result(task_id: str) -> SubagentResult | None:
    """查后台任务结果（None = 未知 task_id）。"""
    with _background_tasks_lock:
        return _background_tasks.get(task_id)


def list_background_tasks() -> list[SubagentResult]:
    """列出全部后台任务。"""
    with _background_tasks_lock:
        return list(_background_tasks.values())


def cleanup_background_task(task_id: str) -> None:
    """移除终态后台任务（防内存泄漏；非终态跳过避免竞态）。"""
    with _background_tasks_lock:
        ent = _background_tasks.get(task_id)
        if ent is None:
            return
        if ent.status in {
            SubagentStatus.COMPLETED,
            SubagentStatus.FAILED,
            SubagentStatus.TIMED_OUT,
        }:
            del _background_tasks[task_id]


def _extract_final_ai_text(response: object) -> str:
    """从 agent.invoke 返回里提取最后一条 assistant 文本。"""
    msgs = response.get("messages", []) if isinstance(response, dict) else []
    for m in reversed(msgs):
        if isinstance(m, AIMessage):
            c = getattr(m, "content", "")
            if isinstance(c, str) and c.strip():
                return c.strip()
    return ""
