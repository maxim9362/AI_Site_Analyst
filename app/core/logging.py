import logging
import sys

from app.core.config import settings


def setup_logging() -> None:
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    sqlalchemy_level = logging.INFO if settings.SQL_ECHO else logging.WARNING
    logging.getLogger("sqlalchemy.engine").setLevel(sqlalchemy_level)
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)

    logger = logging.getLogger("app")
    logger.info(f"Starting {settings.APP_NAME} in {settings.APP_ENV} mode")

    local_base_url = settings.LOCAL_APP_BASE_URL.rstrip("/")
    public_base_url = settings.APP_BASE_URL.rstrip("/")
    logger.info(f"Open locally: {local_base_url}/")
    logger.info(f"Local login: {local_base_url}/login")
    logger.info(f"Local register: {local_base_url}/register")
    logger.info(f"Local admin: {local_base_url}/admin/clients")
    logger.info(f"Admin clients: {public_base_url}/admin/clients")
    if settings.ENABLE_DEMO_ENDPOINTS:
        logger.info(f"Demo site: {public_base_url}/demo")
    logger.info(f"Tracker script: {public_base_url}/static/tracker/tracker.js")
    logger.info(f"Health check: {public_base_url}/health")
