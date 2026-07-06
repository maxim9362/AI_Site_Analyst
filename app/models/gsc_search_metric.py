import uuid
from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDMixin


class GSCSearchMetric(UUIDMixin, TimestampMixin, Base):
    """Строка поисковой статистики Google Search Console по запросу и странице."""

    __tablename__ = "gsc_search_metrics"
    __table_args__ = (
        Index("ix_gsc_search_metrics_site_date", "site_id", "date"),
        Index("ix_gsc_search_metrics_public_site_date", "public_site_id", "date"),
        Index("ix_gsc_search_metrics_query", "query"),
        Index("ix_gsc_search_metrics_page", "page"),
    )

    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sites.id"), nullable=False, index=True)
    public_site_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    query: Mapped[str | None] = mapped_column(String(500), nullable=True)
    page: Mapped[str | None] = mapped_column(Text, nullable=True)
    clicks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    impressions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ctr: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    position: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    device: Mapped[str | None] = mapped_column(String(50), nullable=True)
    country: Mapped[str | None] = mapped_column(String(10), nullable=True)

    site: Mapped["Site"] = relationship(back_populates="gsc_search_metrics")
