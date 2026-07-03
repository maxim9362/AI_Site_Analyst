from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.simple_analytics_service import get_simple_site_analytics

router = APIRouter(tags=["simple-analytics"])


@router.get("/sites/{site_id}/simple-analytics")
async def get_site_simple_analytics(
    site_id: str,
    days: int = Query(7),
    db: AsyncSession = Depends(get_db),
):
    # Route только вызывает сервис: вся логика подсчетов остается в simple_analytics_service.
    analytics = await get_simple_site_analytics(db, site_id, days=days)
    if not analytics:
        raise HTTPException(status_code=404, detail="Site not found")

    return analytics
