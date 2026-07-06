import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PageSpeedResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    site_id: uuid.UUID
    public_site_id: str
    url: str
    strategy: str
    fetched_at: datetime
    performance_score: float | None = None
    accessibility_score: float | None = None
    best_practices_score: float | None = None
    seo_score: float | None = None
    metrics: dict | None = None
    opportunities: list | None = None
    diagnostics: list | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime
