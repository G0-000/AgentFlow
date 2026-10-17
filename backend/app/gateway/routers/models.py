# ============================================================================
# AgentFlow · gateway/routers/models.py —— 模型管理 API（增删改查）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/app/gateway/routers/models.py
# 对标来源: evoflow/gateway/routers/models.py（裁剪：原版 1000+ 行/几十个端点）
#   M7 只保留：列表 / 创建 / 详情 / PATCH（含设为主模型）/ 删除。
# 里程碑: M7（Gateway 核心）
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────────────┐
# │ router(prefix="/api", tags=["models"])                      │
# │   GET    /api/models          → list_all() → [{model...}]   │
# │   POST   /api/models          → create() → 新建模型        │
# │   GET    /api/models/{name}   → get() → 单模型详情        │
# │   PATCH  /api/models/{name}   → update() + 可选 is_primary│
# │   DELETE /api/models/{name}   → delete()                  │
# │                                                            │
# │ 存储: request.app.state.model_store (ModelStore, SQLite)    │
# └────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 裁剪对齐：原版面板有大量探针/连接/降级端点，M7 只做"配置 CRUD"。
# 2. PATCH 传 is_primary=true 即"切换主模型"——runs 运行时现场读主模型，
#    写 SQLite 后下一次 run 就生效，不重启进程（验收点 4）。
# 3. api_key 对外默认打码（ModelStore.to_dict mask_key=True），不回显明文。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. router: 模型管理 APIRouter
# 🔒 内部私有函数
# 1. _store: 从 request.app.state 取 ModelStore
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. 路由顺序：/api/models/{name} 是动态段，勿在它之前再定义 /api/models/xxx 静态段
# 2. 重复创建同名 → 409；更新/删除不存在 → 404
# ============================================================================

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api", tags=["models"])


def _store(request: Request):
    return request.app.state.model_store


class ModelCreate(BaseModel):
    """创建模型请求体。"""

    name: str = Field(..., description="模型唯一标识")
    provider: str = Field(default="openai-compatible")
    base_url: str = Field(default="")
    model: str = Field(default="", description="真实模型名")
    api_key: str = Field(default="")
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    is_primary: bool = Field(
        default=False, description="是否设为主模型（首个模型自动主）"
    )


class ModelPatch(BaseModel):
    """局部更新请求体（全部可选）。传 is_primary=true 即切换主模型。"""

    provider: str | None = None
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    is_primary: bool | None = None


@router.get("/models")
async def list_models(request: Request) -> dict:
    """列出全部模型。"""
    store = _store(request)
    rows = store.list_all()
    return {"models": [store.to_dict(r) for r in rows], "total": len(rows)}


@router.post("/models", status_code=201)
async def create_model(request: Request, body: ModelCreate) -> dict:
    """新增模型；同名已存在返回 409。"""
    store = _store(request)
    try:
        row = store.create(
            name=body.name,
            provider=body.provider,
            base_url=body.base_url,
            model=body.model,
            api_key=body.api_key,
            temperature=body.temperature,
            make_primary=body.is_primary,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return store.to_dict(row)


@router.get("/models/{name}")
async def get_model(request: Request, name: str) -> dict:
    """单模型详情。"""
    store = _store(request)
    row = store.get(name)
    if row is None:
        raise HTTPException(status_code=404, detail=f"模型不存在: {name}")
    return store.to_dict(row)


@router.patch("/models/{name}")
async def update_model(request: Request, name: str, body: ModelPatch) -> dict:
    """局部更新模型配置；传 is_primary=true 切换为主模型（不重启生效）。"""
    store = _store(request)
    if store.get(name) is None:
        raise HTTPException(status_code=404, detail=f"模型不存在: {name}")

    # 先做字段更新
    fields = body.model_dump(exclude_unset=True, exclude={"is_primary"})
    try:
        row = store.update(name, **fields)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    # 再处理主模型切换（独立一步，与字段更新解耦）
    if body.is_primary is not None and body.is_primary:
        store.set_primary(name)
        row = store.get(name)

    return store.to_dict(row)


@router.delete("/models/{name}")
async def delete_model(request: Request, name: str) -> dict:
    """删除模型；删主模型会自动提一个替补。"""
    store = _store(request)
    try:
        store.delete(name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"deleted": name}
