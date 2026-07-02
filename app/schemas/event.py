import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EventCreate(BaseModel):
    site_id: str
    visitor_id: str
    session_id: str
    event_type: str
    url: str
    path: str
    title: str
    referrer: str | None = None
    metadata: dict | None = None


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    site_id: uuid.UUID
    public_site_id: str
    visitor_id: str
    session_id: str
    event_type: str
    url: str
    path: str
    title: str
    referrer: str | None = None
    event_metadata: dict | None = None
    created_at: datetime
