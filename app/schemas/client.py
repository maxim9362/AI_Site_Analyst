import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ClientBase(BaseModel):
    name: str
    email: str | None = None


class ClientCreate(ClientBase):
    pass


class ClientRead(ClientBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
