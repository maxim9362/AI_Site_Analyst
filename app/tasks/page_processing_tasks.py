import logging
import uuid

from app.db.database import async_session_factory
from app.repositories.page_snapshot_repository import PageSnapshotRepository
from app.services.classification_service import ClassificationService
from app.services.knowledge_service import KnowledgeService

logger = logging.getLogger(__name__)


async def process_page_snapshot_task(snapshot_id: str) -> None:
    # Задача сама открывает DB session, чтобы не зависеть от жизненного цикла HTTP-запроса.
    try:
        parsed_snapshot_id = uuid.UUID(snapshot_id)
    except ValueError:
        logger.error("Invalid snapshot_id for background processing: %s", snapshot_id)
        return

    logger.info("Starting background processing for page snapshot %s", parsed_snapshot_id)

    try:
        async with async_session_factory() as session:
            snapshot_repository = PageSnapshotRepository(session)
            snapshot = await snapshot_repository.get_snapshot(parsed_snapshot_id)
            if not snapshot:
                logger.warning("Page snapshot %s was not found for background processing", parsed_snapshot_id)
                return

            knowledge_service = KnowledgeService(session)
            chunks = await knowledge_service.build_knowledge_from_snapshot(parsed_snapshot_id)
            if not chunks:
                logger.warning(
                    "Knowledge build produced no chunks for snapshot %s; classification skipped",
                    parsed_snapshot_id,
                )
                return

            logger.info(
                "Knowledge build completed for snapshot %s: %s chunks",
                parsed_snapshot_id,
                len(chunks),
            )

            try:
                classification_service = ClassificationService(session)
                classifications = await classification_service.classify_site_knowledge(snapshot.public_site_id)
                logger.info(
                    "AI classification completed for site %s: %s classifications",
                    snapshot.public_site_id,
                    len(classifications),
                )
            except Exception:
                logger.exception("AI classification failed for snapshot %s", parsed_snapshot_id)
    except Exception:
        logger.exception("Page snapshot background processing failed for snapshot %s", parsed_snapshot_id)
    finally:
        logger.info("Finished background processing for page snapshot %s", parsed_snapshot_id)
