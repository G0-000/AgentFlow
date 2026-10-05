# ============================================================================
# AgentFlow · webui/middleware.py —— 鉴权中间件逻辑（纯函数，M6）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/webui/middleware.py
# 对标来源: evoflow/webui/middleware.py（190 行裁剪：去掉 Starlette BaseHTTPMiddleware
#   依赖，把"public path 放行 / token 校验 / 401"语义抽成纯函数——D7）
# 里程碑: M6
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────────────┐
# │ WebuiAuthGuard                                             │
# │   check(path, method, headers) -> CheckResult              │
# │   ├─ public path 白名单 → allow(public)                    │
# │   ├─ 有有效 JWT → allow(user=payload)                      │
# │   └─ 无/无效 token → deny(AuthRequiredError)              │
# │ 封装: check_api(headers) → payload / 401                   │
# └────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. 纯逻辑可测：不依赖 Starlette/FastAPI，任何人可对 check() 断言 401/200 语义。
# 2. 白名单先行：公开路径（/login /health /静态资源）不鉴权，其余全拦。
# 3. 单层守卫：M6 只有 JWT 一层（M7 加主体/ACL 时在此扩展 check 分支）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出】
# 1. WebuiAuthGuard: 守卫类（public 白名单 + token 校验 + 401 语义）
# ----------------------------------------------------------------------------

from __future__ import annotations

from typing import Any

from agentflow.authz.http_guard import AuthRequiredError, resolve_auth_from_headers

# 公开路径白名单（不鉴权）：登录/健康检查/静态资源
_PUBLIC_PATHS = {"/login", "/health", "/static", "/favicon.ico", "/"}


class WebuiAuthGuard:
    """登录鉴权守卫（纯逻辑版）。

    用法:
        guard = WebuiAuthGuard(secret)
        result = guard.check(path, method, headers)
        # result == {"allowed": True, "user": payload | None} 放行
        # result == {"allowed": False, "error": "..."}        拒绝（401 语义）
    """

    def __init__(self, secret: str) -> None:
        self._secret = secret

    def check(
        self,
        path: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """核心判定：路径/方法/headers → 放行或拒绝。

        规则顺序:
            1. public path 白名单 → 直接放行（user=None）
            2. 有有效 JWT → 放行（user=payload）
            3. 其余 → 拒绝（401 语义）
        """
        normalized_path = (path or "").split("?")[0].rstrip("/") or "/"
        if normalized_path in _PUBLIC_PATHS:
            return {"allowed": True, "user": None}
        user = resolve_auth_from_headers(headers, self._secret)
        if user is not None:
            return {"allowed": True, "user": user}
        return {"allowed": False, "error": "Authentication required (401)"}

    def require_api(
        self,
        headers: dict[str, str] | None,
        *,
        path: str = "/api",
        method: str = "GET",
    ) -> dict[str, Any]:
        """API 入口封装：拒绝时抛 AuthRequiredError（HTTP 层捕获返 401 JSON）。"""
        result = self.check(path, method, headers)
        if not result["allowed"]:
            raise AuthRequiredError(result.get("error", "Authentication required"))
        return result["user"] or {}
