import hashlib
import hmac
import time

from fastapi import Header, HTTPException, Request, status

from app.core.config import settings

ADMIN_COOKIE = "admin_access"


def _get_signing_secret() -> str:
    return settings.ADMIN_SESSION_SECRET or settings.ADMIN_DASHBOARD_PASSWORD


def sign_admin_session(timestamp: int) -> str:
    payload = f"admin:{timestamp}"
    secret = _get_signing_secret()
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{payload}:{signature}"


def verify_admin_session(cookie_value: str) -> bool:
    if not cookie_value:
        return False

    parts = cookie_value.split(":")
    if len(parts) != 3:
        return False

    prefix, ts_str, signature = parts
    if prefix != "admin":
        return False

    try:
        ts = int(ts_str)
    except ValueError:
        return False

    if time.time() - ts > settings.ADMIN_SESSION_TTL_SECONDS:
        return False

    expected_payload = f"admin:{ts_str}"
    secret = _get_signing_secret()
    expected_sig = hmac.new(secret.encode(), expected_payload.encode(), hashlib.sha256).hexdigest()[:32]
    return hmac.compare_digest(signature, expected_sig)


def is_admin_authenticated(request: Request) -> bool:
    return verify_admin_session(request.cookies.get(ADMIN_COOKIE, ""))


def verify_admin_password(password: str) -> bool:
    return hmac.compare_digest(password, settings.ADMIN_DASHBOARD_PASSWORD)


def _verify_admin_api_key(api_key: str | None) -> bool:
    if not settings.ADMIN_API_KEY or not api_key:
        return False
    return hmac.compare_digest(api_key, settings.ADMIN_API_KEY)


async def require_admin_api_access(
    request: Request,
    x_admin_api_key: str | None = Header(default=None, alias="X-Admin-API-Key"),
) -> None:
    if is_admin_authenticated(request) or _verify_admin_api_key(x_admin_api_key):
        return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Admin authentication required",
    )
