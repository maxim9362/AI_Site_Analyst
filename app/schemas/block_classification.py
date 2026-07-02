import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BlockClassificationCreate(BaseModel):
    site_id: uuid.UUID
    knowledge_chunk_id: uuid.UUID
    public_site_id: str
    path: str
    chunk_type: str
    category: str
    confidence: float
    reason: str
    detected_items: list[str] | None = None
    raw_ai_response: dict | None = None


class BlockClassificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    site_id: uuid.UUID
    knowledge_chunk_id: uuid.UUID
    public_site_id: str
    path: str
    chunk_type: str
    category: str
    confidence: float
    reason: str
    detected_items: list[str] | None = None
    raw_ai_response: dict | None = None
    created_at: datetime
    updated_at: datetime
