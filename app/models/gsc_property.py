import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDMixin


class GSCProperty(UUIDMixin, TimestampMixin, Base):
    """Хранит подключенную Search Console property для конкретного сайта."""

    __tablename__ = "gsc_properties"

    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sites.id"), nullable=False, index=True)
    public_site_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    property_url: Mapped[str] = mapped_column(String(255), nullable=False)
    is_connected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # OAuth fields for real Google Search Console integration.
    # Tokens are encoded via app/core/token_crypto.py before storage.
    # In production, TOKEN_ENCRYPTION_KEY must be set for Fernet encryption.
    google_account_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scopes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    site: Mapped["Site"] = relationship(back_populates="gsc_properties")
