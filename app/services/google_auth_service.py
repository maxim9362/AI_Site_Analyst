import hashlib
import hmac
import logging
import time
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class GoogleAuthError(ValueError):
    pass


def _get_state_secret() -> str:
    return settings.ADMIN_SESSION_SECRET or settings.ADMIN_DASHBOARD_PASSWORD


def _sign_state() -> str:
    payload = f"google-auth:{int(time.time())}"
    signature = hmac.new(_get_state_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{payload}:{signature}"


def _verify_state(state: str) -> bool:
    parts = state.split(":")
    if len(parts) != 3:
        return False
    prefix, ts_raw, signature = parts
    if prefix != "google-auth":
        return False
    try:
        timestamp = int(ts_raw)
    except ValueError:
        return False
    if time.time() - timestamp > 600:
        return False

    payload = f"{prefix}:{ts_raw}"
    expected = hmac.new(_get_state_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]
    return hmac.compare_digest(signature, expected)


class GoogleAuthService:
    def get_authorization_url(self) -> str | None:
        if not settings.google_login_configured:
            return None

        from google_auth_oauthlib.flow import Flow

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=[scope.strip() for scope in settings.GOOGLE_AUTH_SCOPES.split(",") if scope.strip()],
        )
        flow.redirect_uri = settings.GOOGLE_AUTH_REDIRECT_URI
        authorization_url, _ = flow.authorization_url(
            access_type="online",
            include_granted_scopes="true",
            prompt="select_account",
            state=_sign_state(),
        )
        return authorization_url

    def fetch_verified_profile(self, code: str, state: str) -> dict[str, Any]:
        if not _verify_state(state):
            raise GoogleAuthError("Invalid or expired Google auth state")
        if not settings.google_login_configured:
            raise GoogleAuthError("Google login is not configured")

        try:
            from google_auth_oauthlib.flow import Flow
            from googleapiclient.discovery import build

            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": settings.GOOGLE_CLIENT_ID,
                        "client_secret": settings.GOOGLE_CLIENT_SECRET,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                    }
                },
                scopes=[scope.strip() for scope in settings.GOOGLE_AUTH_SCOPES.split(",") if scope.strip()],
            )
            flow.redirect_uri = settings.GOOGLE_AUTH_REDIRECT_URI
            flow.fetch_token(code=code)

            oauth_service = build("oauth2", "v2", credentials=flow.credentials)
            profile = oauth_service.userinfo().get().execute()
        except Exception as exc:
            logger.exception("Google login failed")
            raise GoogleAuthError("Could not verify Google account") from exc

        email = (profile.get("email") or "").strip().lower()
        if not email or not profile.get("verified_email"):
            raise GoogleAuthError("Google account email is not verified")

        return profile
