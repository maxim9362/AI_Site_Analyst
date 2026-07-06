import logging

from app.db.database import async_session_factory
from app.services.ai_report_service import AIReportService
from app.services.classification_service import ClassificationService
from app.services.knowledge_service import KnowledgeService

logger = logging.getLogger(__name__)


async def run_site_analysis_task(public_site_id: str, days: int = 7) -> None:
    logger.info("Starting manual site analysis for %s", public_site_id)

    try:
        async with async_session_factory() as session:
            knowledge_service = KnowledgeService(session)
            chunks = await knowledge_service.build_latest_knowledge_by_site(public_site_id)

            if chunks:
                classification_service = ClassificationService(session)
                classifications = await classification_service.classify_site_knowledge(public_site_id)
                logger.info(
                    "Manual analysis classified %s chunks for %s",
                    len(classifications),
                    public_site_id,
                )

            report_service = AIReportService(session)
            report = await report_service.generate_site_report(public_site_id, report_type="manual", days=days)
            if not report:
                logger.error("Manual site analysis did not create report for %s", public_site_id)
                return

            logger.info("Manual site analysis report created for %s: %s", public_site_id, report.id)
    except Exception:
        logger.exception("Manual site analysis failed for %s", public_site_id)
