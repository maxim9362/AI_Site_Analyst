"""Add OAuth fields to gsc_properties

Revision ID: 008
Revises: 007
Create Date: 2026-07-03 01:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("gsc_properties", sa.Column("google_account_email", sa.String(255), nullable=True))
    op.add_column("gsc_properties", sa.Column("access_token", sa.Text(), nullable=True))
    op.add_column("gsc_properties", sa.Column("refresh_token", sa.Text(), nullable=True))
    op.add_column("gsc_properties", sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("gsc_properties", sa.Column("scopes", sa.String(500), nullable=True))
    op.add_column("gsc_properties", sa.Column("last_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("gsc_properties", "last_error")
    op.drop_column("gsc_properties", "scopes")
    op.drop_column("gsc_properties", "token_expires_at")
    op.drop_column("gsc_properties", "refresh_token")
    op.drop_column("gsc_properties", "access_token")
    op.drop_column("gsc_properties", "google_account_email")
