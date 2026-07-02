import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Float, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDMixin


class BlockClassification(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "block_classifications"
    __table_args__ = (UniqueConstraint("knowledge_chunk_id", name="uq_block_classifications_chunk_id"),)

    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sites.id"), nullable=False, index=True)
    knowledge_chunk_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("knowledge_chunks.id"), nullable=False)
    public_site_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    path: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    chunk_type: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    detected_items: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    raw_ai_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    site: Mapped["Site"] = relationship(back_populates="block_classifications")
    knowledge_chunk: Mapped["KnowledgeChunk"] = relationship(back_populates="block_classification")
