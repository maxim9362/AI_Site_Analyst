"""Add user account plan

Revision ID: 015
Revises: 014
Create Date: 2026-07-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("account_plan", sa.String(length=32), server_default="partner", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "account_plan")
