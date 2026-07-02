"""Create page_snapshots table

Revision ID: 003
Revises: 002
Create Date: 2026-07-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'page_snapshots',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('site_id', UUID(as_uuid=True), sa.ForeignKey('sites.id'), nullable=False),
        sa.Column('public_site_id', sa.String(64), nullable=False),
        sa.Column('visitor_id', sa.String(64), nullable=False),
        sa.Column('session_id', sa.String(64), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('path', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('language', sa.String(10), nullable=True),
        sa.Column('headings', JSONB(), nullable=True),
        sa.Column('links', JSONB(), nullable=True),
        sa.Column('buttons', JSONB(), nullable=True),
        sa.Column('forms', JSONB(), nullable=True),
        sa.Column('contacts', JSONB(), nullable=True),
        sa.Column('text_blocks', JSONB(), nullable=True),
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_page_snapshots_site_id', 'page_snapshots', ['site_id'])
    op.create_index('ix_page_snapshots_public_site_id', 'page_snapshots', ['public_site_id'])
    op.create_index('ix_page_snapshots_path', 'page_snapshots', ['path'])
    op.create_index('ix_page_snapshots_created_at', 'page_snapshots', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_page_snapshots_created_at', 'page_snapshots')
    op.drop_index('ix_page_snapshots_path', 'page_snapshots')
    op.drop_index('ix_page_snapshots_public_site_id', 'page_snapshots')
    op.drop_index('ix_page_snapshots_site_id', 'page_snapshots')
    op.drop_table('page_snapshots')
