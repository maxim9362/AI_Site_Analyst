"""Create events table

Revision ID: 002
Revises: 001
Create Date: 2026-07-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'events',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('site_id', UUID(as_uuid=True), sa.ForeignKey('sites.id'), nullable=False),
        sa.Column('public_site_id', sa.String(64), nullable=False),
        sa.Column('visitor_id', sa.String(64), nullable=False),
        sa.Column('session_id', sa.String(64), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('path', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('referrer', sa.Text(), nullable=True),
        sa.Column('metadata', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_events_site_id', 'events', ['site_id'])
    op.create_index('ix_events_public_site_id', 'events', ['public_site_id'])
    op.create_index('ix_events_visitor_id', 'events', ['visitor_id'])
    op.create_index('ix_events_session_id', 'events', ['session_id'])
    op.create_index('ix_events_event_type', 'events', ['event_type'])
    op.create_index('ix_events_created_at', 'events', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_events_created_at', 'events')
    op.drop_index('ix_events_event_type', 'events')
    op.drop_index('ix_events_session_id', 'events')
    op.drop_index('ix_events_visitor_id', 'events')
    op.drop_index('ix_events_public_site_id', 'events')
    op.drop_index('ix_events_site_id', 'events')
    op.drop_table('events')
