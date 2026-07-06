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
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    logger = logging.getLogger("app")
    logger.info(f"Starting {settings.APP_NAME} in {settings.APP_ENV} mode")

    # В локальной консоли сразу показываем основные ссылки, чтобы запуск MVP было легко проверить вручную.
    logger.info(f"Admin clients: {settings.APP_BASE_URL}/admin/clients")
    logger.info(f"Demo site: {settings.APP_BASE_URL}/demo")
    logger.info(f"Tracker script: {settings.APP_BASE_URL}/static/tracker/tracker.js")
    logger.info(f"Health check: {settings.APP_BASE_URL}/health")
