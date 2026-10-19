# ============================================================================
# AgentFlow · app/gateway/routers/auth.py —— 登录端点（M8 配套）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/app/gateway/routers/auth.py
# 对标来源: evoflow/app/gateway/routers/auth.py（学习版最小：登录签发 JWT；
#   原版还含注册/refresh/用户管理，M8 只做"登录 + 会话保持"验收点）
# 里程碑: M8（前端界面配套）
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────────────┐
# │ POST /api/auth/login  body{username,password}              │
# │   ① 用户名比对（恒定时间比较，防用户枚举时序）              │
# │   ② verify_password(pw, stored_hash) ← M6 webui/auth.py   │
# │   ③ generate_jwt(sub, username, secret) → {token, username}│
# │   auth 未配置（state.auth_config is None）→ 503 诚实报错   │
# └────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 复用核心层 M6 组件（webui/auth.py 的 PBKDF2 + JWT），应用层只做编排——
#   符合 R1：核心层 auth 工具被应用层合法 import。
# 2. 配置来源：config.yaml 的 auth 段（AppConfig.raw 透传原始 dict），
#    明文密码在 create_app 时哈希一次（学习版；生产应预存 hash）。
# 3. JWT 7 天过期（exp 由 generate_jwt 默认控制）；前端存 localStorage。
# 4. 学习版不做 JWT 校验中间件（"登录后所有接口仍开放"），
#    校验中间件列 M8+ 增强——验收点 4 只要求登录/会话保持成立。
# ----------------------------------------------------------------------------

from __future__ import annotations

import secrets

from agentflow.webui.auth import generate_jwt, verify_password
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api", tags=["auth"])


class LoginBody(BaseModel):
    """登录请求体。"""

    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


@router.post("/auth/login")
async def login(request: Request, body: LoginBody) -> dict:
    """用户名 + 密码 → JWT token。失败统一 401（不区分"用户不存在/密码错"）。"""
    cfg = getattr(request.app.state, "auth_config", None)
    if cfg is None:
        # 诚实报错：后端未配置 auth 段时登录不可用，而不是假装成功
        raise HTTPException(status_code=503, detail="后端未配置登录（config.yaml 缺 auth 段）")

    expected_username = str(cfg["username"])
    if not secrets.compare_digest(body.username.encode(), expected_username.encode()):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not verify_password(body.password, str(cfg["password_hash"])):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = generate_jwt(
        subject=expected_username,
        username=expected_username,
        secret=str(cfg["jwt_secret"]),
    )
    return {"token": token, "username": expected_username, "expires_in": 7 * 24 * 3600}
