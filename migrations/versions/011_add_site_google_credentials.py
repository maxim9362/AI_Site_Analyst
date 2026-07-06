"""Add Google credentials to sites

Revision ID: 011
Revises: 010
Create Date: 2026-07-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sites", sa.Column("google_client_id", sa.String(length=255), nullable=True))
    op.add_column("sites", sa.Column("google_client_secret", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("sites", "google_client_secret")
    op.drop_column("sites", "google_client_id")
