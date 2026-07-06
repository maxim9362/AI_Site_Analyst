"""Create PageSpeed results

Revision ID: 012
Revises: 011
Create Date: 2026-07-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pagespeed_results",
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_site_id", sa.String(length=64), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("strategy", sa.String(length=16), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("performance_score", sa.Float(), nullable=True),
        sa.Column("accessibility_score", sa.Float(), nullable=True),
        sa.Column("best_practices_score", sa.Float(), nullable=True),
        sa.Column("seo_score", sa.Float(), nullable=True),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("opportunities", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("diagnostics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pagespeed_results_public_site_id"), "pagespeed_results", ["public_site_id"], unique=False)
    op.create_index(op.f("ix_pagespeed_results_site_id"), "pagespeed_results", ["site_id"], unique=False)
    op.create_index(op.f("ix_pagespeed_results_strategy"), "pagespeed_results", ["strategy"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_pagespeed_results_strategy"), table_name="pagespeed_results")
    op.drop_index(op.f("ix_pagespeed_results_site_id"), table_name="pagespeed_results")
    op.drop_index(op.f("ix_pagespeed_results_public_site_id"), table_name="pagespeed_results")
    op.drop_table("pagespeed_results")
