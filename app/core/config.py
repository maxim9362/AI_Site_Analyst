from functools import lru_cache
from urllib.parse import urlparse

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "AI Site Analyst"
    APP_ENV: str = "local"
    DEBUG: bool = True
    SQL_ECHO: bool = False
    APP_BASE_URL: str = "http://localhost:8000"
    DEMO_SITE_ID: str = ""

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@db:5432/ai_site_analyst"

    POSTGRES_DB: str = "ai_site_analyst"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"

    ADMIN_DASHBOARD_PASSWORD: str = "change_me"
    ADMIN_SESSION_SECRET: str = "change_me_admin_session_secret"
    ADMIN_API_KEY: str = ""
    ADMIN_SESSION_TTL_SECONDS: int = 86400
    ADMIN_LOGIN_RATE_LIMIT_PER_MINUTE: int = 10
    PASSWORD_RESET_TOKEN_TTL_MINUTES: int = 30
    ENABLE_DEMO_ENDPOINTS: bool = True
    ALLOWED_ORIGINS: str = "*"
    TRACKER_RATE_LIMIT_PER_MINUTE: int = 120

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/gsc/oauth/callback"
    GOOGLE_SCOPES: str = "https://www.googleapis.com/auth/webmasters.readonly"
    GOOGLE_AUTH_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"
    GOOGLE_AUTH_SCOPES: str = "openid,email,profile"

    PAGESPEED_API_KEY: str = ""

    TOKEN_ENCRYPTION_KEY: str = ""

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_USE_TLS: bool = True

    REQUIRE_EXTERNAL_INTEGRATIONS: bool = False

    @property
    def google_oauth_configured(self) -> bool:
        return bool(self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET and self.GOOGLE_REDIRECT_URI)

    @property
    def google_login_configured(self) -> bool:
        return bool(self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET and self.GOOGLE_AUTH_REDIRECT_URI)

    @property
    def pagespeed_configured(self) -> bool:
        return bool(self.PAGESPEED_API_KEY)

    @property
    def gemini_configured(self) -> bool:
        return bool(self.GEMINI_API_KEY)

    @property
    def smtp_configured(self) -> bool:
        return bool(self.SMTP_HOST and self.SMTP_FROM_EMAIL)

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

    def integration_status(self) -> dict[str, dict[str, str | bool]]:
        return {
            "google": {
                "label": "Google Search Console OAuth",
                "configured": self.google_oauth_configured,
                "detail": "GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI",
            },
            "google_login": {
                "label": "Вход через Google",
                "configured": self.google_login_configured,
                "detail": "GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_AUTH_REDIRECT_URI",
            },
            "pagespeed": {
                "label": "PageSpeed Insights",
                "configured": self.pagespeed_configured,
                "detail": "PAGESPEED_API_KEY",
            },
            "gemini": {
                "label": "Gemini AI",
                "configured": self.gemini_configured,
                "detail": "GEMINI_API_KEY",
            },
            "smtp": {
                "label": "Email для восстановления пароля",
                "configured": self.smtp_configured,
                "detail": "SMTP_HOST, SMTP_FROM_EMAIL, SMTP_USERNAME/SMTP_PASSWORD если нужны",
            },
            "token_encryption": {
                "label": "Шифрование OAuth-токенов",
                "configured": bool(self.TOKEN_ENCRYPTION_KEY),
                "detail": "TOKEN_ENCRYPTION_KEY",
            },
        }

    def validate_production_settings(self) -> None:
        if not self.is_production:
            return

        errors: list[str] = []

        def is_placeholder_secret(value: str) -> bool:
            normalized = value.strip().lower()
            return not normalized or "change_me" in normalized or normalized.startswith("local_")

        if self.DEBUG:
            errors.append("DEBUG must be false in production")
        if self.SQL_ECHO:
            errors.append("SQL_ECHO must be false in production")
        if is_placeholder_secret(self.ADMIN_DASHBOARD_PASSWORD):
            errors.append("ADMIN_DASHBOARD_PASSWORD must be changed in production")
        if is_placeholder_secret(self.ADMIN_SESSION_SECRET) or self.ADMIN_SESSION_SECRET == self.ADMIN_DASHBOARD_PASSWORD:
            errors.append("ADMIN_SESSION_SECRET must be unique and changed in production")
        if self.ADMIN_API_KEY and is_placeholder_secret(self.ADMIN_API_KEY):
            errors.append("ADMIN_API_KEY must be changed or left empty in production")
        if is_placeholder_secret(self.POSTGRES_PASSWORD) or self.POSTGRES_PASSWORD == "postgres":
            errors.append("POSTGRES_PASSWORD must be changed in production")
        if self.ADMIN_LOGIN_RATE_LIMIT_PER_MINUTE < 1 or self.ADMIN_LOGIN_RATE_LIMIT_PER_MINUTE > 60:
            errors.append("ADMIN_LOGIN_RATE_LIMIT_PER_MINUTE must be between 1 and 60 in production")
        if self.PASSWORD_RESET_TOKEN_TTL_MINUTES < 5 or self.PASSWORD_RESET_TOKEN_TTL_MINUTES > 120:
            errors.append("PASSWORD_RESET_TOKEN_TTL_MINUTES must be between 5 and 120")
        if self.ENABLE_DEMO_ENDPOINTS:
            errors.append("ENABLE_DEMO_ENDPOINTS must be false in production")
        if not self.ALLOWED_ORIGINS.strip() or self.ALLOWED_ORIGINS.strip() == "*":
            errors.append("ALLOWED_ORIGINS must list explicit client origins in production")
        if not self.TOKEN_ENCRYPTION_KEY:
            errors.append("TOKEN_ENCRYPTION_KEY is required in production")
        else:
            try:
                from cryptography.fernet import Fernet

                Fernet(self.TOKEN_ENCRYPTION_KEY.encode())
            except Exception:
                errors.append("TOKEN_ENCRYPTION_KEY must be a valid Fernet key")
        if self.APP_BASE_URL.startswith("http://"):
            errors.append("APP_BASE_URL should use https:// in production")
        parsed_base_url = urlparse(self.APP_BASE_URL)
        if not parsed_base_url.netloc:
            errors.append("APP_BASE_URL must be an absolute public URL")
        if not self.GOOGLE_REDIRECT_URI.startswith(self.APP_BASE_URL.rstrip("/")):
            errors.append("GOOGLE_REDIRECT_URI must use APP_BASE_URL in production")
        if self.google_login_configured and not self.GOOGLE_AUTH_REDIRECT_URI.startswith(self.APP_BASE_URL.rstrip("/")):
            errors.append("GOOGLE_AUTH_REDIRECT_URI must use APP_BASE_URL in production")
        if not self.smtp_configured:
            errors.append("SMTP_HOST and SMTP_FROM_EMAIL are required in production for password reset")
        if self.SMTP_PORT < 1 or self.SMTP_PORT > 65535:
            errors.append("SMTP_PORT must be between 1 and 65535")
        if self.REQUIRE_EXTERNAL_INTEGRATIONS:
            if not self.google_oauth_configured:
                errors.append("Google OAuth credentials are required when REQUIRE_EXTERNAL_INTEGRATIONS=true")
            if not self.google_login_configured:
                errors.append("Google login credentials are required when REQUIRE_EXTERNAL_INTEGRATIONS=true")
            if not self.pagespeed_configured:
                errors.append("PAGESPEED_API_KEY is required when REQUIRE_EXTERNAL_INTEGRATIONS=true")
            if not self.gemini_configured:
                errors.append("GEMINI_API_KEY is required when REQUIRE_EXTERNAL_INTEGRATIONS=true")

        if errors:
            formatted = "\n- ".join(errors)
            raise RuntimeError(f"Unsafe production settings:\n- {formatted}")

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
