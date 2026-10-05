# tests/test_auth.py — test_auth.py

> **文件路径**: `backend/packages/harness/tests/test_auth.py`
> **目录位置**: tests → test_auth.py
> **职责**: 登录鉴权测试（M6 验收点 3）——PBKDF2 密码 + JWT 签发/校验 + 401 守卫语义

## 📑 目录

- [📋 结构图](#📋-结构图)
- [📤 关键导出](#📤-关键导出)
- [💡 设计思想](#💡-设计思想)
- [🧩 代码解析（成块对照 test_auth.py）](#🧩-代码解析成块对照-test_authpy)
- [⚠️ 风险点](#⚠️-风险点)

## 📋 结构图

```text
tests/test_auth.py（13 用例 → 验收点 3：鉴权拦截）
├── 密码哈希（3）
│   ├── test_hash_verify_roundtrip              正确/错误密码往返
│   ├── test_hash_self_contained_format         格式 pbkdf2$sha256$100000$salt$hash
│   └── test_verify_bad_format_returns_false    坏格式 → False
├── JWT（4）
│   ├── test_jwt_roundtrip                      签发→校验 payload
│   ├── test_jwt_expired_returns_none           过期 → None
│   ├── test_jwt_wrong_secret_returns_none      伪造签名 → None
│   └── test_jwt_garbage_returns_none           非 JWT 串 → None
├── authz 守卫（4）
│   ├── test_guard_missing_token_raises         无 token/非 Bearer → AuthRequiredError
│   ├── test_guard_valid_token_returns_payload  带 token → payload
│   ├── test_guard_invalid_token_raises         伪造 → AuthRequiredError
│   └── test_resolve_auth_no_raise              只解析不抛错
└── webui middleware（3）
    ├── test_webui_guard_public_path_allows_without_token  /health 放行
    ├── test_webui_guard_protected_path_denied_without_token  /api 无 token 拒
    ├── test_webui_guard_protected_path_allowed_with_token   /api 带 token 过
    └── test_webui_guard_require_api_raises_when_denied  require_api 拒绝抛错

被测对象: agentflow/webui/auth.py + authz/http_guard.py + webui/middleware.py
```

## 📤 关键导出

无独立导出（测试文件）。覆盖的被测契约：

- `hash_password / verify_password`：PBKDF2-HMAC-SHA256 自含格式 + 恒定时间比较
- `generate_jwt / verify_jwt`：HS256 签发，exp 自动校验，失败 None 不抛
- `require_api_auth`：无/伪 token → AuthRequiredError（401 语义）；有效 → payload
- `WebuiAuthGuard`：public path 白名单放行 + 受保护路径 401

## 💡 设计思想

1. **测试即契约**：每个失败路径（过期/伪造/垃圾串/缺头/非 Bearer）都显式测——鉴权系统"默认拒绝"是安全底线，宁可测多不可漏。
2. **纯函数直测**：不依赖 HTTP 框架——守卫是纯逻辑，任何人可断言 401/200 语义（M6 D7 设计使然）。
3. **密钥 ≥32 字节**：避免 PyJWT 弱密钥告警（RFC 7518 对 HS256 最小密钥长度建议）。
4. **require_api 与 check 双入口都测**：中间件既有"白名单放行"的宽松路径，也有"API 入口拒绝抛错"的严格路径。

## 🧩 代码解析（成块对照 test_auth.py）

### 块 1：JWT 过期与伪造

```python
def test_jwt_expired_returns_none():
    token = generate_jwt("u1", "alice", _SECRET, expires_in=-1)  # 立即过期
    assert verify_jwt(token, _SECRET) is None


def test_jwt_wrong_secret_returns_none():
    token = generate_jwt("u1", "alice", _SECRET)
    assert verify_jwt(token, "another-secret-0123456789abcdef01234567") is None
```

**整块解析**（参数逐条）：

| 测试 | 输入 | 断言 | 验证点 |
|---|---|---|---|
| `test_jwt_expired_returns_none` | `expires_in=-1` 签发 | `verify_jwt` 返回 None | exp 过期由 jwt.decode 自动判拒 |
| `test_jwt_wrong_secret_returns_none` | 正确 token + 错误密钥 | None | 签名不符 → HMAC 校验失败 |

**关键细节**：`expires_in=-1` 让 `exp = now - 1`——PyJWT 的 `jwt.decode` 对过期 token 抛 `ExpiredSignatureError`，被 `verify_jwt` 的 except 统一吞成 None（不抛异常是守卫层的契约）。

### 块 2：守卫 401 语义

```python
def test_guard_missing_token_raises():
    with pytest.raises(AuthRequiredError, match="missing Bearer"):
        require_api_auth({}, _SECRET)
    with pytest.raises(AuthRequiredError, match="missing Bearer"):
        require_api_auth(None, _SECRET)
    # 非 Bearer scheme
    with pytest.raises(AuthRequiredError, match="missing Bearer"):
        require_api_auth({"Authorization": "Basic abc"}, _SECRET)
```

**整块解析**（参数逐条）：

| 入参 | 行为 | 理由 |
|---|---|---|
| `{}` | 无 authorization 头 → 拒绝 | 缺凭证即拒绝 |
| `None` | headers 为 None → 拒绝 | 空请求兜底 |
| `"Authorization: Basic abc"` | 非 Bearer scheme → 拒绝 | 只认 Bearer，最小攻击面 |

**关键细节**：三种缺 token 形态统一抛 `AuthRequiredError("missing Bearer token")`——HTTP 层捕获后返回 401 JSON，纯函数层不关心响应形状。

## ⚠️ 风险点

1. **密钥长度敏感**：HS256 弱密钥会触发 PyJWT InsecureKeyLengthWarning——测试固定 ≥32 字节；生产 secret 必须更长的随机串。
2. **exp 语义**：`expires_in=-1` 依赖"签发即过期"——若 PyJWT 版本把 iat/exp 关系校验变严可能行为变化（当前版本通过）。
3. **AuthRequiredError 消息耦合**：`match="missing Bearer"` 断言绑定错误文案——改文案需同步改测试。

---
_2026-10-05 M6 新增：结构图 + 设计思想 + 成块代码解析（参数逐条表）+ 风险点。_
