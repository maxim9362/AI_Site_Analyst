"""Create Google Search Console tables

Revision ID: 007
Revises: 006
Create Date: 2026-07-03 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "gsc_properties",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("site_id", UUID(as_uuid=True), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("public_site_id", sa.String(64), nullable=False),
        sa.Column("property_url", sa.String(255), nullable=False),
        sa.Column("is_connected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_gsc_properties_site_id", "gsc_properties", ["site_id"])
    op.create_index("ix_gsc_properties_public_site_id", "gsc_properties", ["public_site_id"])

    op.create_table(
        "gsc_search_metrics",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("site_id", UUID(as_uuid=True), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("public_site_id", sa.String(64), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("query", sa.String(500), nullable=True),
        sa.Column("page", sa.Text(), nullable=True),
        sa.Column("clicks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("impressions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ctr", sa.Float(), nullable=False, server_default="0"),
        sa.Column("position", sa.Float(), nullable=False, server_default="0"),
        sa.Column("device", sa.String(50), nullable=True),
        sa.Column("country", sa.String(10), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_gsc_search_metrics_site_id", "gsc_search_metrics", ["site_id"])
    op.create_index("ix_gsc_search_metrics_public_site_id", "gsc_search_metrics", ["public_site_id"])
    op.create_index("ix_gsc_search_metrics_date", "gsc_search_metrics", ["date"])
    op.create_index("ix_gsc_search_metrics_site_date", "gsc_search_metrics", ["site_id", "date"])
    op.create_index("ix_gsc_search_metrics_public_site_date", "gsc_search_metrics", ["public_site_id", "date"])
    op.create_index("ix_gsc_search_metrics_query", "gsc_search_metrics", ["query"])
    op.create_index("ix_gsc_search_metrics_page", "gsc_search_metrics", ["page"])


def downgrade() -> None:
    op.drop_index("ix_gsc_search_metrics_page", "gsc_search_metrics")
    op.drop_index("ix_gsc_search_metrics_query", "gsc_search_metrics")
    op.drop_index("ix_gsc_search_metrics_public_site_date", "gsc_search_metrics")
    op.drop_index("ix_gsc_search_metrics_site_date", "gsc_search_metrics")
    op.drop_index("ix_gsc_search_metrics_date", "gsc_search_metrics")
    op.drop_index("ix_gsc_search_metrics_public_site_id", "gsc_search_metrics")
    op.drop_index("ix_gsc_search_metrics_site_id", "gsc_search_metrics")
    op.drop_table("gsc_search_metrics")
    op.drop_index("ix_gsc_properties_public_site_id", "gsc_properties")
    op.drop_index("ix_gsc_properties_site_id", "gsc_properties")
    op.drop_table("gsc_properties")
