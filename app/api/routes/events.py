from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import check_rate_limit
from app.db.database import get_db
from app.schemas.event import EventCreate, EventRead
from app.services.event_service import EventService

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", response_model=EventRead, status_code=201)
async def create_event(data: EventCreate, request: Request, db: AsyncSession = Depends(get_db)):
    rate_key = f"events:{data.site_id}:{data.visitor_id}" if data.visitor_id else f"events:{request.client.host}"
    if not check_rate_limit(rate_key):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    service = EventService(db)
    result = await service.create_event(
        data,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    if not result:
        raise HTTPException(status_code=422, detail="Invalid event data or site not found/inactive")
    return result
