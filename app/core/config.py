from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "AI Site Analyst"
    APP_ENV: str = "local"
    DEBUG: bool = True
    APP_BASE_URL: str = "http://localhost:8000"

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@db:5432/ai_site_analyst"

    POSTGRES_DB: str = "ai_site_analyst"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
