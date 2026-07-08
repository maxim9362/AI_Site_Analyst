import hashlib
import hmac
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.token_crypto import decode_token, encode_token
from app.repositories.gsc_repository import GSCRepository
from app.repositories.site_repository import SiteRepository
from app.services.url_normalization import normalize_gsc_property_url

logger = logging.getLogger(__name__)


def _get_state_secret() -> str:
    return settings.ADMIN_SESSION_SECRET or settings.ADMIN_DASHBOARD_PASSWORD


def _sign_state(public_site_id: str, user_id: uuid.UUID | None = None) -> str:
    """Create signed state with public_site_id, optional user_id and timestamp."""
    user_part = str(user_id) if user_id else "-"
    payload = f"{public_site_id}:{user_part}:{int(time.time())}"
    secret = _get_state_secret()
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{payload}:{signature}"


def _verify_state(state: str) -> tuple[str, uuid.UUID | None] | None:
    """Verify signed state and extract public_site_id/user_id. Returns None if invalid."""
    parts = state.split(":")
    if len(parts) == 3:
        public_site_id, ts_str, signature = parts
        user_part = "-"
        expected_payload = f"{public_site_id}:{ts_str}"
    elif len(parts) == 4:
        public_site_id, user_part, ts_str, signature = parts
        expected_payload = f"{public_site_id}:{user_part}:{ts_str}"
    else:
        return None

    secret = _get_state_secret()
    expected_sig = hmac.new(secret.encode(), expected_payload.encode(), hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(signature, expected_sig):
        return None
    try:
        ts = int(ts_str)
    except ValueError:
        return None
    if time.time() - ts > 600:
        return None

    user_id = None
    if user_part != "-":
        try:
            user_id = uuid.UUID(user_part)
        except ValueError:
            return None

    return public_site_id, user_id


class GSCOAuthService:
    """Handles Google OAuth flow for Search Console integration."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.site_repository = SiteRepository(session)
        self.gsc_repository = GSCRepository(session)

    def get_authorization_url(self, public_site_id: str, user_id: uuid.UUID | None = None) -> str | None:
        """Generate Google OAuth authorization URL with signed state.

        Returns None if Google credentials are not configured.
        """
        if not settings.google_oauth_configured:
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
            scopes=settings.GOOGLE_SCOPES.split(","),
            autogenerate_code_verifier=False,
        )
        flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
        state = _sign_state(public_site_id, user_id=user_id)
        authorization_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            state=state,
        )
        return authorization_url

    async def handle_callback(self, code: str, state: str) -> dict[str, Any]:
        """Exchange authorization code for tokens and save to GSC property."""
        verified_state = _verify_state(state)
        if not verified_state:
            return {"status": "error", "message": "Invalid or expired OAuth state"}
        public_site_id, state_user_id = verified_state

        if not settings.google_oauth_configured:
            return {"status": "error", "message": "Google OAuth credentials are not configured"}

        site = await self.site_repository.get_site_by_site_id(public_site_id)
        if not site:
            return {"status": "error", "message": "Site not found"}
        if state_user_id and site.user_id != state_user_id:
            return {"status": "error", "message": "Site does not belong to OAuth user"}

        try:
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
                scopes=settings.GOOGLE_SCOPES.split(","),
                autogenerate_code_verifier=False,
            )
            flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
            flow.fetch_token(code=code)
            credentials = flow.credentials
        except Exception as e:
            logger.error(f"OAuth token exchange failed: {e}")
            return {"status": "error", "message": f"Token exchange failed: {str(e)[:200]}"}

        google_email = None
        credential_scopes = set(credentials.scopes or [])
        if credential_scopes.intersection({"openid", "email", "profile", "https://www.googleapis.com/auth/userinfo.email"}):
            try:
                from googleapiclient.discovery import build
                oauth_service = build("oauth2", "v2", credentials=credentials)
                user_info = oauth_service.userinfo().get().execute()
                google_email = user_info.get("email")
            except Exception:
                logger.warning("Could not fetch Google user email")

        property_obj = await self.gsc_repository.get_property_by_site(site.id)
        if not property_obj:
            property_url = normalize_gsc_property_url(site.domain if "." in site.domain else "localhost")
            property_obj = await self.gsc_repository.create_or_update_property(site.id, site.site_id, property_url)
        else:
            normalized_property_url = normalize_gsc_property_url(property_obj.property_url)
            if normalized_property_url != property_obj.property_url:
                property_obj.property_url = normalized_property_url

        await self.gsc_repository.update_oauth_tokens(
            property_obj,
            access_token=encode_token(credentials.token),
            refresh_token=encode_token(credentials.refresh_token),
            token_expires_at=credentials.expiry,
            scopes=",".join(credentials.scopes or []),
            google_account_email=google_email,
        )

        logger.info(f"GSC OAuth completed for site {public_site_id}, email: {google_email}")

        return {
            "status": "ok",
            "message": "Google Search Console connected successfully",
            "site_id": public_site_id,
            "google_account_email": google_email,
            "property_url": property_obj.property_url,
            "redirect_to": f"/sites/{public_site_id}" if state_user_id else None,
        }

    async def refresh_token_if_needed(self, site_id) -> bool:
        """Refresh access_token if expired. Returns True if successful."""
        property_obj = await self.gsc_repository.get_property_by_site(site_id)
        if not property_obj or not property_obj.refresh_token:
            return False

        needs_refresh = (
            not property_obj.token_expires_at
            or property_obj.token_expires_at <= datetime.now(timezone.utc) + timedelta(minutes=5)
        )
        if not needs_refresh:
            return True

        if not settings.google_oauth_configured:
            return False

        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials

            credentials = Credentials(
                token=decode_token(property_obj.access_token),
                refresh_token=decode_token(property_obj.refresh_token),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=settings.GOOGLE_CLIENT_ID,
                client_secret=settings.GOOGLE_CLIENT_SECRET,
            )
            credentials.refresh(Request())

            await self.gsc_repository.update_oauth_tokens(
                property_obj,
                access_token=encode_token(credentials.token),
                refresh_token=encode_token(credentials.refresh_token),
                token_expires_at=credentials.expiry,
                scopes=property_obj.scopes,
                google_account_email=property_obj.google_account_email,
            )
            return True
        except Exception as e:
            logger.error(f"Token refresh failed for site {site_id}: {e}")
            await self.gsc_repository.update_last_error(property_obj, f"Token refresh failed: {str(e)[:200]}")
            return False

    async def get_credentials(self, site_id):
        """Get valid Google credentials for a site, refreshing if needed."""
        refreshed = await self.refresh_token_if_needed(site_id)
        if not refreshed:
            return None

        property_obj = await self.gsc_repository.get_property_by_site(site_id)
        if not property_obj or not property_obj.access_token:
            return None

        from google.oauth2.credentials import Credentials

        return Credentials(
            token=decode_token(property_obj.access_token),
            refresh_token=decode_token(property_obj.refresh_token),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            scopes=property_obj.scopes.split(",") if property_obj.scopes else [],
        )

    async def disconnect(self, public_site_id: str) -> dict[str, Any]:
        """Disconnect GSC by clearing tokens."""
        site = await self.site_repository.get_site_by_site_id(public_site_id)
        if not site:
            return {"status": "error", "message": "Site not found"}

        property_obj = await self.gsc_repository.get_property_by_site(site.id)
        if not property_obj:
            return {"status": "error", "message": "GSC property not found"}

        await self.gsc_repository.update_oauth_tokens(
            property_obj,
            access_token=None,
            refresh_token=None,
            token_expires_at=None,
            scopes=None,
            google_account_email=None,
        )
        # update_oauth_tokens sets is_connected=True, override it.
        property_obj.is_connected = False
        await self.session.commit()

        return {"status": "ok", "message": "Google Search Console disconnected"}
