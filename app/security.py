import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass

from fastapi import Request

from .config import get_settings


ADMIN_ROLES = {"admin", "owner", "system"}
PASSWORD_ITERATIONS = 210_000


@dataclass(frozen=True)
class RequestContext:
    user_id: str
    user_name: str
    role: str
    department_id: int | None

    @property
    def is_admin(self) -> bool:
        return self.role in ADMIN_ROLES


def system_context() -> RequestContext:
    return RequestContext(user_id="system", user_name="系统用户", role="admin", department_id=None)


def get_request_context(request: Request) -> RequestContext:
    token_context = _context_from_authorization(request.headers.get("authorization"))
    if token_context:
        return token_context
    department_id = _parse_department_id(request.headers.get("x-department-id"))
    return RequestContext(
        user_id=request.headers.get("x-user-id") or "system",
        user_name=request.headers.get("x-user-name") or "系统用户",
        role=(request.headers.get("x-user-role") or "admin").lower(),
        department_id=department_id,
    )


def _parse_department_id(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt, expected = password_hash.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations))
    return hmac.compare_digest(digest.hex(), expected)


def create_access_token(context: RequestContext) -> str:
    settings = get_settings()
    payload = {
        "sub": context.user_id,
        "name": context.user_name,
        "role": context.role,
        "department_id": context.department_id,
        "exp": int(time.time()) + settings.access_token_ttl_minutes * 60,
    }
    payload_text = _base64url_encode(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    signature = _sign(payload_text)
    return f"{payload_text}.{signature}"


def parse_access_token(token: str) -> RequestContext | None:
    try:
        payload_text, signature = token.split(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(_sign(payload_text), signature):
        return None
    try:
        payload = json.loads(_base64url_decode(payload_text).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return RequestContext(
        user_id=str(payload["sub"]),
        user_name=str(payload.get("name") or payload["sub"]),
        role=str(payload.get("role") or "user"),
        department_id=payload.get("department_id"),
    )


def _context_from_authorization(authorization: str | None) -> RequestContext | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return parse_access_token(authorization.split(" ", 1)[1].strip())


def _sign(payload_text: str) -> str:
    settings = get_settings()
    digest = hmac.new(settings.auth_token_secret.encode("utf-8"), payload_text.encode("utf-8"), hashlib.sha256).digest()
    return _base64url_encode(digest)


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _base64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)
