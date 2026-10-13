# ============================================================================
# AgentFlow · gateway/routers/runs.py —— 对话运行(runs) API + SSE 流式
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/app/gateway/routers/runs.py
# 对标来源: evoflow/gateway/routers/runs.py + chat_session_service（裁剪）
#   原版 runs 偏"执行生命周期/取消"，对话流在 chat_session_service。
#   M7 合并裁剪：发起 run → 查状态 → SSE 流式拿回复，三件套。
# 里程碑: M7（Gateway 核心）
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌──────────────────────────────────────────────────────────────┐
# │ router(prefix="/api", tags=["runs"])                          │
# │   POST /api/runs              → 建 run（记消息/会话，返回 run_id）│
# │   GET  /api/runs/{run_id}     → 查 run 状态/回复             │
# │   GET  /api/runs/{run_id}/stream → SSE 逐块推回复          │
# │                                                              │
# │ 执行体: app.state.runner(thread_id, message) → 异步生成器产文本│
# │   （默认=真 agent；测试注入 fake，不联网）                    │
# │ run 注册表: app.state.runs[run_id] = {...,status,response}   │
# └──────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 三段式对齐验收：POST 只登记 run（返回 run_id）；GET 查状态；
#    stream 才真正跑 agent 并逐块推送——分离"发起"与"执行"。
# 2. runner 是注入点：app.state.runner 是 async(thread_id, message)->AsyncIterator[str]。
#    create_app 默认装真 agent；测试传 fake → 全程离线，不调真实模型 API。
# 3. run 注册表放内存（执行态）；业务记录（会话+明文消息）落 sessions SQLite，
#    图状态落 checkpointer——run 本身是临时执行句柄，重启后无需恢复。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. router: runs APIRouter
# 🔒 内部私有函数
# 1. _stream_run: 把 runner 的文本块包成 SSE 事件流（更新 run 状态）
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. run 注册表是进程内 dict：多副本/重启后 run_id 失效（M7 单进程够用）
# 2. SSE 客户端断开会中断生成器；这里 try 内已兜异常，finally 无需额外清理
# 3. GET stream 重复订阅会重跑一次 runner（每次调用独立执行）
# ============================================================================

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.gateway.sse import (
    EventSourceResponse,
    delta_event,
    done_event,
    error_event,
)

router = APIRouter(prefix="/api", tags=["runs"])


class RunCreate(BaseModel):
    """发起 run 请求体。"""

    message: str = Field(..., description="用户消息")
    thread_id: str | None = Field(default=None, description="复用会话；缺省新建")


def _new_run_id() -> str:
    return "r_" + os.urandom(6).hex()


@router.post("/runs", status_code=201)
async def create_run(request: Request, body: RunCreate) -> dict:
    """发起一次对话 run：登记会话/消息，返回 run_id（不立即执行）。"""
    state = request.app.state
    thread_id = body.thread_id or os.urandom(8).hex()
    run_id = _new_run_id()
    now = datetime.now(UTC).isoformat()

    # 会话业务记录落库（幂等建会话 + 记用户消息）
    state.sessions.create(thread_id)
    state.sessions.add_message(thread_id, "user", body.message)

    state.runs[run_id] = {
        "run_id": run_id,
        "thread_id": thread_id,
        "message": body.message,
        "status": "pending",
        "response": "",
        "error": "",
        "created_at": now,
        "updated_at": now,
    }
    return {"run_id": run_id, "thread_id": thread_id, "status": "pending"}


@router.get("/runs/{run_id}")
async def get_run(request: Request, run_id: str) -> dict:
    """查 run 状态（pending/running/success/failed）与回复。"""
    run = request.app.state.runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run 不存在: {run_id}")
    return run


async def _stream_run(request: Request, run: dict) -> AsyncIterator[dict]:
    """执行 runner 并把文本块包成 SSE 事件流，同时回写 run 状态。"""
    state = request.app.state
    run["status"] = "running"
    run["updated_at"] = datetime.now(UTC).isoformat()
    full = ""
    try:
        async for chunk in state.runner(run["thread_id"], run["message"]):
            if chunk:
                full += chunk
                yield delta_event(chunk)
        run["status"] = "success"
        run["response"] = full
        yield done_event(full)
    except Exception as exc:  # noqa: BLE001 —— run 失败回写状态并推 error 事件，不崩服务
        run["status"] = "failed"
        run["error"] = str(exc)[:300]
        yield error_event(str(exc)[:300])


@router.get("/runs/{run_id}/stream")
async def stream_run(request: Request, run_id: str):
    """SSE 流式：逐块推送该 run 的回复内容。"""
    run = request.app.state.runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run 不存在: {run_id}")
    return EventSourceResponse(_stream_run(request, run))
