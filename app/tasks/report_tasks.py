import logging

from app.db.database import async_session_factory
from app.services.ai_report_service import AIReportService

logger = logging.getLogger(__name__)


async def generate_ai_report_task(
    public_site_id: str,
    report_type: str = "manual",
    days: int = 7,
) -> None:
    # Задача открывает собственную DB session, чтобы не зависеть от HTTP-запроса.
    logger.info(
        "Starting background AI report generation for site %s (%s, %s days)",
        public_site_id,
        report_type,
        days,
    )

    try:
        async with async_session_factory() as session:
            report_service = AIReportService(session)
            report = await report_service.generate_site_report(
                public_site_id,
                report_type=report_type,
                days=days,
            )
            if not report:
                logger.error("Background AI report was not created for site %s", public_site_id)
                return

            logger.info(
                "Background AI report created for site %s: %s",
                public_site_id,
                report.id,
            )
    except Exception:
        logger.exception("Background AI report generation failed for site %s", public_site_id)
