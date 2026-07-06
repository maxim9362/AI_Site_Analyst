from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.site_score_service import calculate_site_score

router = APIRouter(tags=["site_score"])


@router.get("/sites/{site_id}/score")
async def get_site_score(
    site_id: str,
    period: str = Query("7d"),
    db: AsyncSession = Depends(get_db),
):
    result = await calculate_site_score(db, site_id, period)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result
