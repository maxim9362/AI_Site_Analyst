import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDMixin


class PageSpeedResult(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "pagespeed_results"

    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sites.id"), nullable=False, index=True)
    public_site_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    strategy: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    performance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    accessibility_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    best_practices_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    seo_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    opportunities: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    diagnostics: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    site: Mapped["Site"] = relationship(back_populates="pagespeed_results")
