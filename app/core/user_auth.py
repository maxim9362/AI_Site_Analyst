import hashlib
import hmac
import time
import uuid

from fastapi import Request

from app.core.config import settings

USER_COOKIE = "user_session"


def _get_signing_secret() -> str:
    return settings.ADMIN_SESSION_SECRET or settings.ADMIN_DASHBOARD_PASSWORD


def sign_user_session(user_id: uuid.UUID, timestamp: int) -> str:
    payload = f"user:{user_id}:{timestamp}"
    signature = hmac.new(_get_signing_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{payload}:{signature}"


def verify_user_session_with_timestamp(cookie_value: str) -> tuple[uuid.UUID, int] | None:
    if not cookie_value:
        return None

    parts = cookie_value.split(":")
    if len(parts) != 4:
        return None

    prefix, user_id_raw, ts_raw, signature = parts
    if prefix != "user":
        return None

    try:
        user_id = uuid.UUID(user_id_raw)
        timestamp = int(ts_raw)
    except ValueError:
        return None

    if time.time() - timestamp > settings.ADMIN_SESSION_TTL_SECONDS:
        return None

    payload = f"user:{user_id}:{ts_raw}"
    expected_signature = hmac.new(_get_signing_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(signature, expected_signature):
        return None

    return user_id, timestamp


def verify_user_session(cookie_value: str) -> uuid.UUID | None:
    verified = verify_user_session_with_timestamp(cookie_value)
    if not verified:
        return None
    return verified[0]


def get_authenticated_user_id(request: Request) -> uuid.UUID | None:
    return verify_user_session(request.cookies.get(USER_COOKIE, ""))
