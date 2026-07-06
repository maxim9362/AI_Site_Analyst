"""Add bot fields to events

Revision ID: 013
Revises: 012
Create Date: 2026-07-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("events", sa.Column("user_agent", sa.Text(), nullable=True))
    op.add_column("events", sa.Column("ip_address", sa.String(length=64), nullable=True))
    op.add_column("events", sa.Column("is_bot", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("events", sa.Column("bot_name", sa.String(length=120), nullable=True))
    op.add_column("events", sa.Column("bot_category", sa.String(length=80), nullable=True))
    op.create_index(op.f("ix_events_is_bot"), "events", ["is_bot"], unique=False)
    op.create_index(op.f("ix_events_bot_name"), "events", ["bot_name"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_events_bot_name"), table_name="events")
    op.drop_index(op.f("ix_events_is_bot"), table_name="events")
    op.drop_column("events", "bot_category")
    op.drop_column("events", "bot_name")
    op.drop_column("events", "is_bot")
    op.drop_column("events", "ip_address")
    op.drop_column("events", "user_agent")
