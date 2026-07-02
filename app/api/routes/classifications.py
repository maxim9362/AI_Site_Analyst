from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.block_classification import BlockClassificationRead
from app.services.classification_service import ClassificationService

router = APIRouter(tags=["classifications"])


@router.post("/sites/{site_id}/classify", response_model=list[BlockClassificationRead])
async def classify_site(site_id: str, db: AsyncSession = Depends(get_db)):
    service = ClassificationService(db)
    return await service.classify_site_knowledge(site_id)


@router.get("/sites/{site_id}/classifications", response_model=list[BlockClassificationRead])
async def get_site_classifications(site_id: str, limit: int = 100, offset: int = 0, db: AsyncSession = Depends(get_db)):
    service = ClassificationService(db)
    return await service.list_classifications_by_site(site_id, limit, offset)
