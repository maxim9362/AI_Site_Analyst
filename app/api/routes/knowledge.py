import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.knowledge_chunk import KnowledgeChunkRead
from app.services.knowledge_service import KnowledgeService

router = APIRouter(tags=["knowledge"])


@router.post("/page-snapshots/{snapshot_id}/build-knowledge", response_model=list[KnowledgeChunkRead])
async def build_knowledge(snapshot_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = KnowledgeService(db)
    chunks = await service.build_knowledge_from_snapshot(snapshot_id)
    if not chunks:
        raise HTTPException(status_code=404, detail="Snapshot not found or no chunks created")
    return chunks


@router.post("/sites/{site_id}/knowledge/build-latest", response_model=list[KnowledgeChunkRead])
async def build_latest_site_knowledge(site_id: str, db: AsyncSession = Depends(get_db)):
    # Удобный MVP-эндпоинт: пересобирает базу знаний из последнего snapshot сайта.
    service = KnowledgeService(db)
    chunks = await service.build_latest_knowledge_by_site(site_id)
    if not chunks:
        raise HTTPException(status_code=404, detail="Site or snapshot not found, or no chunks created")
    return chunks


@router.get("/sites/{site_id}/knowledge", response_model=list[KnowledgeChunkRead])
async def get_site_knowledge(site_id: str, limit: int = 100, offset: int = 0, db: AsyncSession = Depends(get_db)):
    service = KnowledgeService(db)
    chunks = await service.list_chunks_by_site(site_id, limit, offset)
    return chunks
