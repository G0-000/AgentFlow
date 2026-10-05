# ============================================================================
# AgentFlow · webui/auth.py —— 登录鉴权：密码哈希 + JWT（M6）
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/webui/auth.py
# 对标来源: evoflow/webui/auth.py（731 行裁剪：只留密码哈希 + JWT 四函数，
#   砍 admin 用户管理/QR token/secret 持久化——M6 用配置 secret 直签）
# 里程碑: M6
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────────────────┐
# │ hash_password(pw) → "pbkdf2$sha256$100000$<salt>$<hash>"  │
# │ verify_password(pw, stored) → bool（恒定时间比较）         │
# │ generate_jwt(sub, username, secret) → token                │
# │ verify_jwt(token, secret) → payload dict | None           │
# └────────────────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. PBKDF2-HMAC-SHA256（标准库 hashlib）：100000 次迭代抗暴力破解，
#    格式自含（算法/迭代数/salt 随哈希一起存），未来可升级迭代数不破旧哈希。
# 2. secrets.compare_digest 恒定时间比较：防时序攻击（直接 == 会泄漏长度/内容信息）。
# 3. JWT 用 PyJWT：payload 带 sub/username/iat/exp（签发时间/过期时间），
#    过期校验由 jwt.decode 自动完成（exp 过期抛异常 → 返回 None）。
# 4. 容错：任何校验失败返回 None/False，绝不抛异常（守卫层统一处理 401）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出】
# 1. hash_password / verify_password: PBKDF2 密码哈希与校验
# 2. generate_jwt / verify_jwt: JWT 签发与校验
# ----------------------------------------------------------------------------

from __future__ import annotations

import hashlib
import os
import secrets
import time
from typing import Any

_PBKDF2_ALGO = "sha256"
_PBKDF2_ITERATIONS = 100_000
_SALT_BYTES = 16
_HASH_FORMAT = "pbkdf2${algo}${iterations}${salt_hex}${hash_hex}"

_JWT_ALGORITHM = "HS256"
_JWT_EXPIRY_SECONDS = 7 * 24 * 3600  # 7 天


def hash_password(password: str) -> str:
    """PBKDF2-HMAC-SHA256 哈希密码，返回自含格式字符串。

    格式: pbkdf2$sha256$100000$<salt_hex>$<hash_hex>
    """
    salt = os.urandom(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(_PBKDF2_ALGO, password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return _HASH_FORMAT.format(
        algo=_PBKDF2_ALGO,
        iterations=_PBKDF2_ITERATIONS,
        salt_hex=salt.hex(),
        hash_hex=dk.hex(),
    )


def verify_password(password: str, stored_hash: str) -> bool:
    """校验明文密码是否匹配存储哈希。恒定时间比较，失败返回 False。"""
    try:
        parts = stored_hash.split("$")
        if len(parts) != 5 or parts[0] != "pbkdf2":
            return False
        algo = parts[1]
        iterations = int(parts[2])
        salt = bytes.fromhex(parts[3])
        expected_hash = bytes.fromhex(parts[4])
        dk = hashlib.pbkdf2_hmac(algo, password.encode("utf-8"), salt, iterations)
        return secrets.compare_digest(dk, expected_hash)
    except (ValueError, IndexError):
        return False


def generate_jwt(
    subject: str,
    username: str,
    secret: str,
    *,
    expires_in: int = _JWT_EXPIRY_SECONDS,
) -> str:
    """签发 JWT（HS256）。subject 通常是用户/主体 id，username 便于展示。"""
    import jwt

    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": subject,
        "username": username,
        "iat": now,
        "exp": now + expires_in,
    }
    return jwt.encode(payload, secret, algorithm=_JWT_ALGORITHM)


def verify_jwt(token: str, secret: str) -> dict[str, Any] | None:
    """校验 JWT：签名有效 + 未过期 → payload dict；否则 None（不抛异常）。"""
    import jwt

    try:
        payload = jwt.decode(token, secret, algorithms=[_JWT_ALGORITHM])
        return payload if isinstance(payload, dict) else None
    except Exception:  # noqa: BLE001 —— 任何 JWT 异常（过期/伪造/格式错）统一 None
        return None
