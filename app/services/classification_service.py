import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import CLASSIFICATION_MAX_AI_TEXT_LENGTH
from app.repositories.block_classification_repository import BlockClassificationRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.site_repository import SiteRepository
from app.schemas.block_classification import BlockClassificationRead
from app.services.ai_service import ai_service

logger = logging.getLogger(__name__)


class ClassificationService:
    MAX_AI_TEXT_LENGTH = CLASSIFICATION_MAX_AI_TEXT_LENGTH

    def __init__(self, session: AsyncSession):
        self.session = session
        self.classification_repository = BlockClassificationRepository(session)
        self.knowledge_repository = KnowledgeRepository(session)
        self.site_repository = SiteRepository(session)

    async def classify_site_knowledge(self, public_site_id: str) -> list[BlockClassificationRead]:
        site = await self.site_repository.get_site_by_site_id(public_site_id)
        if not site:
            return []

        chunks = await self.knowledge_repository.list_chunks_by_site(site.id, limit=1000)

        results = []
        for chunk in chunks:
            chunk_id = chunk.id
            chunk_content = chunk.content or ""
            chunk_path = chunk.path
            chunk_type = chunk.chunk_type

            if not chunk_content or len(chunk_content.strip()) < 10:
                continue

            existing = await self.classification_repository.get_classification_by_chunk(chunk_id)
            if existing:
                await self.classification_repository.delete_classification_by_chunk(chunk_id)

            ai_result = await ai_service.classify_text(chunk_content)

            classification_data = {
                "site_id": site.id,
                "knowledge_chunk_id": chunk_id,
                "public_site_id": public_site_id,
                "path": chunk_path,
                "chunk_type": chunk_type,
                "category": ai_result.get("category", "unknown"),
                "confidence": ai_result.get("confidence", 0.0),
                "reason": ai_result.get("reason", ""),
                "detected_items": ai_result.get("detected_items", []),
                "raw_ai_response": ai_result,
            }

            try:
                classification = await self.classification_repository.create_classification(classification_data)
                results.append(BlockClassificationRead.model_validate(classification))
            except Exception as e:
                # Если knowledge пересобрали параллельно, chunk мог исчезнуть между чтением и записью классификации.
                await self.session.rollback()
                logger.error(f"Failed to create classification for chunk {chunk_id}: {e}")
                continue

        return results

    async def list_classifications_by_site(self, public_site_id: str, limit: int = 100, offset: int = 0) -> list[BlockClassificationRead]:
        site = await self.site_repository.get_site_by_site_id(public_site_id)
        if not site:
            return []

        classifications = await self.classification_repository.list_classifications_by_site(site.id, limit, offset)
        return [BlockClassificationRead.model_validate(c) for c in classifications]
