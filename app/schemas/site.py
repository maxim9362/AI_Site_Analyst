import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SiteBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    domain: str = Field(min_length=1, max_length=255)
    allowed_domains: list[str] | None = None


class SiteCreate(SiteBase):
    pass


class UserSiteCreate(SiteBase):
    google_client_id: str = Field(min_length=1, max_length=255)
    google_client_secret: str = Field(min_length=1, max_length=500)


class SiteRead(SiteBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    user_id: uuid.UUID | None = None
    site_id: str
    google_client_id: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
