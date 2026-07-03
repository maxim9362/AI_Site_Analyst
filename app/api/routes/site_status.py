from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.site_status_service import get_site_processing_status

router = APIRouter(tags=["site-status"])


@router.get("/sites/{site_id}/status")
async def get_site_status(site_id: str, db: AsyncSession = Depends(get_db)):
    # Endpoint возвращает простой статус обработки сайта без технических деталей пайплайна.
    status = await get_site_processing_status(db, site_id)
    if not status:
        raise HTTPException(status_code=404, detail="Site not found")

    return status
