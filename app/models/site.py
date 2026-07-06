import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDMixin


class Site(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "sites"

    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    site_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    allowed_domains: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    google_client_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_client_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    client: Mapped["Client"] = relationship(back_populates="sites")
    user: Mapped["User | None"] = relationship(back_populates="sites")
    events: Mapped[list["Event"]] = relationship(back_populates="site")
    page_snapshots: Mapped[list["PageSnapshot"]] = relationship(back_populates="site")
    knowledge_chunks: Mapped[list["KnowledgeChunk"]] = relationship(back_populates="site")
    block_classifications: Mapped[list["BlockClassification"]] = relationship(back_populates="site")
    ai_reports: Mapped[list["AIReport"]] = relationship(back_populates="site")
    gsc_properties: Mapped[list["GSCProperty"]] = relationship(back_populates="site")
    gsc_search_metrics: Mapped[list["GSCSearchMetric"]] = relationship(back_populates="site")
    pagespeed_results: Mapped[list["PageSpeedResult"]] = relationship(back_populates="site")
