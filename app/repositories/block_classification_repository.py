import uuid

from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.block_classification import BlockClassification


class BlockClassificationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_classification(self, classification_data: dict) -> BlockClassification:
        classification = BlockClassification(**classification_data)
        self.session.add(classification)
        await self.session.commit()
        await self.session.refresh(classification)
        return classification

    async def list_classifications_by_site(self, site_id: uuid.UUID, limit: int = 100, offset: int = 0) -> list[BlockClassification]:
        result = await self.session.execute(
            select(BlockClassification).where(BlockClassification.site_id == site_id).order_by(BlockClassification.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    async def get_classification_by_chunk(self, chunk_id: uuid.UUID) -> BlockClassification | None:
        result = await self.session.execute(select(BlockClassification).where(BlockClassification.knowledge_chunk_id == chunk_id))
        return result.scalar_one_or_none()

    async def delete_classification_by_chunk(self, chunk_id: uuid.UUID) -> None:
        await self.session.execute(delete(BlockClassification).where(BlockClassification.knowledge_chunk_id == chunk_id))
        await self.session.commit()

    async def list_recent_classifications_by_site(self, site_id: uuid.UUID, limit: int = 5) -> list[BlockClassification]:
        result = await self.session.execute(
            select(BlockClassification).where(BlockClassification.site_id == site_id).order_by(BlockClassification.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def count_classifications_by_site(self, site_id: uuid.UUID) -> int:
        result = await self.session.execute(select(func.count()).select_from(BlockClassification).where(BlockClassification.site_id == site_id))
        return result.scalar_one() or 0

    async def get_latest_created_at_by_site(self, site_id: uuid.UUID) -> datetime | None:
        # Статус показывает готовность AI-классификации, не раскрывая технические детали блоков.
        result = await self.session.execute(select(func.max(BlockClassification.created_at)).where(BlockClassification.site_id == site_id))
        return result.scalar_one_or_none()
