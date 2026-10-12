# ============================================================================
# AgentFlow · gateway/routers/threads.py —— 会话(threads) CRUD API
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/gateway/routers/threads.py
# 对标来源: evoflow/gateway/routers/threads.py（裁剪：原版含文件系统/产物端点）
#   M7 只保留会话本身的创建/列表/删除（业务会话，复用 SessionRepository）。
# 里程碑: M7（Gateway 核心）
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────────────┐
# │ router(prefix="/api", tags=["threads"])                    │
# │   POST   /api/threads            → 建会话（可指定 id/标题）│
# │   GET    /api/threads            → 列出全部会话            │
# │   DELETE /api/threads/{thread_id} → 删会话（连带消息）     │
# │                                                            │
# │ 存储: request.app.state.sessions (SessionRepository)       │
# └────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 会话即 LangGraph thread_id：创建会话=在 sessions 表插一行（幂等 INSERT OR IGNORE）。
# 2. 删除会话同时清 session_messages（外键未级联，repo.delete 已手动删）。
# 3. 列表查询走 sessions repo 自己的连接（不裸连，复用 persistence.db 配置）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. router: 会话 CRUD APIRouter
# 🔒 内部私有函数
# 1. _row_to_dict: session row → JSON dict
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. 删除会话不清 LangGraph checkpoint 表（M7 裁剪；恢复对话仍可走 --thread）
# 2. POST 不传 thread_id 时自动生成（os.urandom 16 hex）
# ============================================================================

from __future__ import annotations

import os
import sqlite3

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api", tags=["threads"])


class ThreadCreate(BaseModel):
    """创建会话请求体（都可选）。"""

    thread_id: str | None = Field(default=None, description="指定会话 id；缺省自动生成")
    title: str = Field(default="", description="会话标题")


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "thread_id": row["id"],
        "title": row["title"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@router.post("/threads", status_code=201)
async def create_thread(request: Request, body: ThreadCreate) -> dict:
    """创建会话；不传 thread_id 则自动生成。"""
    sessions = request.app.state.sessions
    thread_id = body.thread_id or os.urandom(8).hex()
    sessions.create(thread_id, title=body.title)
    row = sessions.get(thread_id)
    return _row_to_dict(row)  # type: ignore[arg-type]


@router.get("/threads")
async def list_threads(request: Request) -> dict:
    """列出全部会话（按更新时间倒序）。"""
    sessions = request.app.state.sessions
    rows = sessions.conn.execute(
        "SELECT * FROM sessions ORDER BY updated_at DESC"
    ).fetchall()
    return {"threads": [_row_to_dict(r) for r in rows], "total": len(rows)}


@router.delete("/threads/{thread_id}")
async def delete_thread(request: Request, thread_id: str) -> dict:
    """删除会话（连带其消息记录）。"""
    sessions = request.app.state.sessions
    sessions.delete(thread_id)
    return {"deleted": thread_id}
