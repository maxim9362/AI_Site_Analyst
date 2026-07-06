from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import check_rate_limit
from app.db.database import get_db
from app.schemas.page_snapshot import PageSnapshotAcceptedResponse, PageSnapshotCreate
from app.services.page_snapshot_service import PageSnapshotService
from app.tasks.page_processing_tasks import process_page_snapshot_task

router = APIRouter(prefix="/page-snapshots", tags=["page-snapshots"])


@router.post("", response_model=PageSnapshotAcceptedResponse, status_code=201)
async def create_page_snapshot(
    data: PageSnapshotCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    rate_key = f"snapshots:{data.site_id}:{data.visitor_id}" if data.visitor_id else f"snapshots:{request.client.host}"
    if not check_rate_limit(rate_key):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    service = PageSnapshotService(db)
    result = await service.create_snapshot(data)
    if not result:
        raise HTTPException(status_code=404, detail="Site not found or inactive")

    # После быстрого сохранения snapshot запускаем тяжелую обработку в фоне.
    background_tasks.add_task(process_page_snapshot_task, str(result.id))

    return {
        "status": "accepted",
        "message": "Page snapshot saved and background processing started",
        "snapshot_id": result.id,
        "data": result,
    }
