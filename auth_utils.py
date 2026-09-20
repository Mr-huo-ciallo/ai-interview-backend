import base64
import hashlib
import hmac
import json
import os
import secrets
import time


TOKEN_TTL_SECONDS = int(os.getenv("AUTH_TOKEN_TTL_SECONDS", str(60 * 60 * 24 * 7)))
AUTH_SECRET = os.getenv("AUTH_SECRET") or secrets.token_urlsafe(48)


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)
    return f"pbkdf2_sha256$310000${_base64url_encode(salt)}${_base64url_encode(digest)}"


def verify_password(password: str, password_hash: str) -> bool:
    if password_hash.startswith("pbkdf2_sha256$"):
        try:
            _, iterations, salt, expected = password_hash.split("$", 3)
            actual = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), _base64url_decode(salt), int(iterations)
            )
            return hmac.compare_digest(_base64url_encode(actual), expected)
        except (ValueError, TypeError):
            return False
    # 兼容已存在的旧账号；登录后会在服务层自动升级为 PBKDF2 哈希。
    legacy_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(legacy_hash, password_hash)


def is_legacy_password_hash(password_hash: str) -> bool:
    return not password_hash.startswith("pbkdf2_sha256$")


def create_access_token(user_id: int, username: str) -> str:
    header = _base64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _base64url_encode(json.dumps({
        "sub": str(user_id), "username": username, "exp": int(time.time()) + TOKEN_TTL_SECONDS
    }, separators=(",", ":")).encode())
    signature = hmac.new(AUTH_SECRET.encode("utf-8"), f"{header}.{payload}".encode("ascii"), hashlib.sha256).digest()
    return f"{header}.{payload}.{_base64url_encode(signature)}"


def decode_access_token(token: str) -> dict:
    try:
        header, payload, signature = token.split(".")
        expected = hmac.new(AUTH_SECRET.encode("utf-8"), f"{header}.{payload}".encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(_base64url_encode(expected), signature):
            raise ValueError("令牌签名无效")
        data = json.loads(_base64url_decode(payload))
        if not data.get("sub") or int(data["exp"]) < int(time.time()):
            raise ValueError("令牌已失效")
        return data
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("无效访问令牌") from error
