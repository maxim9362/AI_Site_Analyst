import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import UUIDMixin


class PageSnapshot(UUIDMixin, Base):
    __tablename__ = "page_snapshots"

    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sites.id"), nullable=False, index=True)
    public_site_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    visitor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    headings: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    links: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    buttons: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    forms: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    contacts: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    text_blocks: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    site: Mapped["Site"] = relationship(back_populates="page_snapshots")
