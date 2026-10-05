# ============================================================================
# AgentFlow · authz/http_guard.py —— 鉴权守卫：无 token → 401（M6）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/authz/http_guard.py
# 对标来源: evoflow/authz/http_guard.py（472 行裁剪：只学"从请求解析身份 + 拒绝"语义，
#   砍 20 个 require_*_visible 可见性守卫——那是 M7 组织级能力）
# 里程碑: M6
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────────────┐
# │ require_api_auth(headers, secret) → payload dict           │
# │   │                                                       │
# │   ├─ _extract_token(headers): Authorization: Bearer <t>  │
# │   │     缺 header / 非 Bearer / 空 token → None           │
# │   ├─ verify_jwt(token, secret): 签名+过期校验             │
# │   └─ 任一失败 → raise AuthRequiredError（401 语义）       │
# │      成功 → 返回 payload（sub/username/exp）              │
# └────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 守卫是纯函数：不绑定任何 HTTP 框架（FastAPI/Starlette 皆可适配）——
#    CLI 环境可测（验收点 3：无 token 拒 / 带 token 过）。
# 2. AuthRequiredError 表达 401 语义：调用方（HTTP 层）捕获后返回 401 JSON；
#    纯函数层只负责"判定 + 抛出"，不负责 HTTP 响应形状。
# 3. 只认 Bearer scheme：Authorization: Bearer <token> 是业界标准，
#    其他 scheme（Basic 等）一律拒绝（最小攻击面）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出】
# 1. AuthRequiredError: 鉴权失败异常（401 语义载体）
# 2. require_api_auth: 守卫入口（headers + secret → payload / 抛错）
# 3. resolve_auth_from_headers: 只解析不抛错（供需要"可选身份"的场景）
# ----------------------------------------------------------------------------

from __future__ import annotations

from typing import Any

from agentflow.webui.auth import verify_jwt


class AuthRequiredError(Exception):
    """鉴权失败（对应 HTTP 401）。message 是给用户的拒绝说明。"""


def _extract_token(headers: dict[str, str] | None) -> str | None:
    """从 headers 里取 Bearer token；缺/非 Bearer/空 → None。"""
    if not headers:
        return None
    auth = headers.get("authorization") or headers.get("Authorization") or ""
    parts = str(auth).split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token if token else None


def resolve_auth_from_headers(
    headers: dict[str, str] | None, secret: str
) -> dict[str, Any] | None:
    """从 headers 解析身份（不抛错）：有效 JWT → payload；否则 None。"""
    token = _extract_token(headers)
    if not token:
        return None
    return verify_jwt(token, secret)


def require_api_auth(headers: dict[str, str] | None, secret: str) -> dict[str, Any]:
    """鉴权守卫：无有效 JWT 抛 AuthRequiredError；否则返回 payload。

    入参:
        headers: 请求头（key 大小写不敏感取 authorization）
        secret:  JWT 签名密钥

    返回:
        payload dict（sub/username/iat/exp）

    异常:
        AuthRequiredError: 无 token / 非 Bearer / 签名无效 / 过期
    """
    token = _extract_token(headers)
    if not token:
        raise AuthRequiredError("Authentication required: missing Bearer token")
    payload = verify_jwt(token, secret)
    if payload is None:
        raise AuthRequiredError("Authentication required: invalid or expired token")
    return payload
