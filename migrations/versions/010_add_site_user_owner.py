"""Add user owner to sites

Revision ID: 010
Revises: 009
Create Date: 2026-07-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sites", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index(op.f("ix_sites_user_id"), "sites", ["user_id"], unique=False)
    op.create_foreign_key("fk_sites_user_id_users", "sites", "users", ["user_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_sites_user_id_users", "sites", type_="foreignkey")
    op.drop_index(op.f("ix_sites_user_id"), table_name="sites")
    op.drop_column("sites", "user_id")
