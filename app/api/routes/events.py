from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.event import EventCreate, EventRead
from app.services.event_service import EventService

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", response_model=EventRead, status_code=201)
async def create_event(data: EventCreate, db: AsyncSession = Depends(get_db)):
    service = EventService(db)
    result = await service.create_event(data)
    if not result:
        raise HTTPException(status_code=422, detail="Invalid event data or site not found/inactive")
    return result
