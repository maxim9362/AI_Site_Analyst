"""Add partner client fields

Revision ID: 016
Revises: 015
Create Date: 2026-07-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("clients", sa.Column("contact_name", sa.String(length=255), nullable=True))
    op.add_column("clients", sa.Column("phone", sa.String(length=80), nullable=True))
    op.add_column("clients", sa.Column("notes", sa.Text(), nullable=True))
    op.create_index(op.f("ix_clients_user_id"), "clients", ["user_id"], unique=False)
    op.create_foreign_key("fk_clients_user_id_users", "clients", "users", ["user_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_clients_user_id_users", "clients", type_="foreignkey")
    op.drop_index(op.f("ix_clients_user_id"), table_name="clients")
    op.drop_column("clients", "notes")
    op.drop_column("clients", "phone")
    op.drop_column("clients", "contact_name")
    op.drop_column("clients", "user_id")
