import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class KnowledgeChunkCreate(BaseModel):
    site_id: uuid.UUID
    source_snapshot_id: uuid.UUID
    public_site_id: str
    url: str
    path: str
    chunk_type: str
    title: str
    content: str
    content_hash: str
    chunk_metadata: dict | None = None


class KnowledgeChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    site_id: uuid.UUID
    source_snapshot_id: uuid.UUID
    public_site_id: str
    url: str
    path: str
    chunk_type: str
    title: str
    content: str
    content_hash: str
    chunk_metadata: dict | None = None
    created_at: datetime
    updated_at: datetime
