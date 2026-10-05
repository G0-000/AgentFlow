# ============================================================================
# AgentFlow · tests/test_auth.py —— 登录鉴权：JWT + 守卫（M6）
# 验收项：③鉴权拦截——无 token 401；带 token 通过；过期/伪造拒绝。
# 纯函数直测，不依赖任何 HTTP 框架与网络。
# ============================================================================
import pytest

from agentflow.authz.http_guard import (
    AuthRequiredError,
    require_api_auth,
    resolve_auth_from_headers,
)
from agentflow.webui.auth import (
    generate_jwt,
    hash_password,
    verify_jwt,
    verify_password,
)
from agentflow.webui.middleware import WebuiAuthGuard

_SECRET = "test-secret-key-0123456789abcdef"  # ≥32 字节，避免 PyJWT 弱密钥告警


# ── 密码哈希（PBKDF2）──────────────────────────────────────


def test_hash_verify_roundtrip():
    h = hash_password("s3cret-pw")
    assert verify_password("s3cret-pw", h) is True
    assert verify_password("wrong-pw", h) is False


def test_hash_self_contained_format():
    h = hash_password("pw")
    parts = h.split("$")
    assert len(parts) == 5
    assert parts[0] == "pbkdf2"
    assert parts[1] == "sha256"
    assert int(parts[2]) == 100_000


def test_verify_bad_format_returns_false():
    assert verify_password("pw", "not-a-hash") is False
    assert verify_password("pw", "") is False
    assert verify_password("pw", "pbkdf2$sha256$x$y") is False  # 分段不足


# ── JWT ────────────────────────────────────────────────────


def test_jwt_roundtrip():
    token = generate_jwt("u1", "alice", _SECRET)
    payload = verify_jwt(token, _SECRET)
    assert payload is not None
    assert payload["sub"] == "u1"
    assert payload["username"] == "alice"
    assert payload["exp"] > payload["iat"]


def test_jwt_expired_returns_none():
    token = generate_jwt("u1", "alice", _SECRET, expires_in=-1)  # 立即过期
    assert verify_jwt(token, _SECRET) is None


def test_jwt_wrong_secret_returns_none():
    token = generate_jwt("u1", "alice", _SECRET)
    assert verify_jwt(token, "another-secret-0123456789abcdef01234567") is None


def test_jwt_garbage_returns_none():
    assert verify_jwt("not-a-jwt", _SECRET) is None


# ── authz 守卫（401 语义）───────────────────────────────────


def test_guard_missing_token_raises():
    with pytest.raises(AuthRequiredError, match="missing Bearer"):
        require_api_auth({}, _SECRET)
    with pytest.raises(AuthRequiredError, match="missing Bearer"):
        require_api_auth(None, _SECRET)
    # 非 Bearer scheme
    with pytest.raises(AuthRequiredError, match="missing Bearer"):
        require_api_auth({"Authorization": "Basic abc"}, _SECRET)


def test_guard_valid_token_returns_payload():
    token = generate_jwt("u1", "alice", _SECRET)
    payload = require_api_auth({"Authorization": f"Bearer {token}"}, _SECRET)
    assert payload["sub"] == "u1"


def test_guard_invalid_token_raises():
    token = generate_jwt("u1", "alice", "wrong-secret-0123456789abcdef0123456789")
    with pytest.raises(AuthRequiredError, match="invalid or expired"):
        require_api_auth({"Authorization": f"Bearer {token}"}, _SECRET)


def test_resolve_auth_no_raise():
    assert resolve_auth_from_headers({}, _SECRET) is None
    token = generate_jwt("u1", "alice", _SECRET)
    assert resolve_auth_from_headers({"Authorization": f"Bearer {token}"}, _SECRET) is not None


# ── webui middleware（public path + 401）────────────────────


def test_webui_guard_public_path_allows_without_token():
    guard = WebuiAuthGuard(_SECRET)
    result = guard.check("/health")
    assert result["allowed"] is True
    assert result["user"] is None


def test_webui_guard_protected_path_denied_without_token():
    guard = WebuiAuthGuard(_SECRET)
    result = guard.check("/api/runs")
    assert result["allowed"] is False
    assert "401" in result["error"]


def test_webui_guard_protected_path_allowed_with_token():
    guard = WebuiAuthGuard(_SECRET)
    token = generate_jwt("u1", "alice", _SECRET)
    result = guard.check("/api/runs", headers={"Authorization": f"Bearer {token}"})
    assert result["allowed"] is True
    assert result["user"]["username"] == "alice"


def test_webui_guard_require_api_raises_when_denied():
    guard = WebuiAuthGuard(_SECRET)
    with pytest.raises(AuthRequiredError):
        guard.require_api({})
