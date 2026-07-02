from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.page_snapshot import PageSnapshotCreate, PageSnapshotRead
from app.services.page_snapshot_service import PageSnapshotService

router = APIRouter(prefix="/page-snapshots", tags=["page-snapshots"])


@router.post("", response_model=PageSnapshotRead, status_code=201)
async def create_page_snapshot(data: PageSnapshotCreate, db: AsyncSession = Depends(get_db)):
    service = PageSnapshotService(db)
    result = await service.create_snapshot(data)
    if not result:
        raise HTTPException(status_code=404, detail="Site not found or inactive")
    return result
