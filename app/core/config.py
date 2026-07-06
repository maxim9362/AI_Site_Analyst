from functools import lru_cache

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
    ENABLE_DEMO_ENDPOINTS: bool = True
    ALLOWED_ORIGINS: str = "*"
    TRACKER_RATE_LIMIT_PER_MINUTE: int = 120

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/gsc/oauth/callback"
    GOOGLE_SCOPES: str = "https://www.googleapis.com/auth/webmasters.readonly"

    PAGESPEED_API_KEY: str = ""

    TOKEN_ENCRYPTION_KEY: str = ""

    @property
    def google_oauth_configured(self) -> bool:
        return bool(self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET and self.GOOGLE_REDIRECT_URI)

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

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
        if self.ADMIN_LOGIN_RATE_LIMIT_PER_MINUTE < 1 or self.ADMIN_LOGIN_RATE_LIMIT_PER_MINUTE > 60:
            errors.append("ADMIN_LOGIN_RATE_LIMIT_PER_MINUTE must be between 1 and 60 in production")
        if self.ENABLE_DEMO_ENDPOINTS:
            errors.append("ENABLE_DEMO_ENDPOINTS must be false in production")
        if not self.ALLOWED_ORIGINS.strip() or self.ALLOWED_ORIGINS.strip() == "*":
            errors.append("ALLOWED_ORIGINS must list explicit client origins in production")
        if not self.TOKEN_ENCRYPTION_KEY:
            errors.append("TOKEN_ENCRYPTION_KEY is required in production")
        if self.APP_BASE_URL.startswith("http://"):
            errors.append("APP_BASE_URL should use https:// in production")

        if errors:
            formatted = "\n- ".join(errors)
            raise RuntimeError(f"Unsafe production settings:\n- {formatted}")

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
