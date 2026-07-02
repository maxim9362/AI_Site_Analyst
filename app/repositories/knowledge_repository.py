import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.block_classification import BlockClassification
from app.models.knowledge_chunk import KnowledgeChunk


class KnowledgeRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_chunk(self, chunk_data: dict) -> KnowledgeChunk:
        chunk = KnowledgeChunk(**chunk_data)
        self.session.add(chunk)
        await self.session.commit()
        await self.session.refresh(chunk)
        return chunk

    async def create_chunks_bulk(self, chunks_data: list[dict]) -> list[KnowledgeChunk]:
        chunks = [KnowledgeChunk(**data) for data in chunks_data]
        self.session.add_all(chunks)
        await self.session.commit()
        for chunk in chunks:
            await self.session.refresh(chunk)
        return chunks

    async def list_chunks_by_site(self, site_id: uuid.UUID, limit: int = 100, offset: int = 0) -> list[KnowledgeChunk]:
        result = await self.session.execute(
            select(KnowledgeChunk).where(KnowledgeChunk.site_id == site_id).order_by(KnowledgeChunk.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    async def list_chunks_by_site_and_path(self, site_id: uuid.UUID, path: str) -> list[KnowledgeChunk]:
        result = await self.session.execute(
            select(KnowledgeChunk).where(KnowledgeChunk.site_id == site_id, KnowledgeChunk.path == path).order_by(KnowledgeChunk.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_chunk_by_hash(self, content_hash: str) -> KnowledgeChunk | None:
        result = await self.session.execute(select(KnowledgeChunk).where(KnowledgeChunk.content_hash == content_hash))
        return result.scalar_one_or_none()

    async def delete_chunks_by_snapshot(self, snapshot_id: uuid.UUID) -> None:
        # Сначала удаляем классификации, потому что они ссылаются на knowledge chunks.
        chunk_ids = select(KnowledgeChunk.id).where(KnowledgeChunk.source_snapshot_id == snapshot_id)
        await self.session.execute(delete(BlockClassification).where(BlockClassification.knowledge_chunk_id.in_(chunk_ids)))
        await self.session.execute(delete(KnowledgeChunk).where(KnowledgeChunk.source_snapshot_id == snapshot_id))
        await self.session.commit()

    async def delete_chunks_by_site_path(self, site_id: uuid.UUID, path: str) -> None:
        # Перед пересборкой страницы удаляем старые знания этого URL, чтобы не ловить конфликт content_hash.
        chunk_ids = select(KnowledgeChunk.id).where(KnowledgeChunk.site_id == site_id, KnowledgeChunk.path == path)
        await self.session.execute(delete(BlockClassification).where(BlockClassification.knowledge_chunk_id.in_(chunk_ids)))
        await self.session.execute(delete(KnowledgeChunk).where(KnowledgeChunk.site_id == site_id, KnowledgeChunk.path == path))
        await self.session.commit()

    async def list_recent_chunks_by_site(self, site_id: uuid.UUID, limit: int = 5) -> list[KnowledgeChunk]:
        result = await self.session.execute(
            select(KnowledgeChunk).where(KnowledgeChunk.site_id == site_id).order_by(KnowledgeChunk.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())
