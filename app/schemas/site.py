import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SiteBase(BaseModel):
    name: str
    domain: str
    allowed_domains: list[str] | None = None


class SiteCreate(SiteBase):
    pass


class SiteRead(SiteBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    site_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
