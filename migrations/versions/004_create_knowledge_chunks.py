"""Create knowledge_chunks table

Revision ID: 004
Revises: 003
Create Date: 2026-07-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'knowledge_chunks',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('site_id', UUID(as_uuid=True), sa.ForeignKey('sites.id'), nullable=False),
        sa.Column('source_snapshot_id', UUID(as_uuid=True), sa.ForeignKey('page_snapshots.id'), nullable=False),
        sa.Column('public_site_id', sa.String(64), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('path', sa.Text(), nullable=False),
        sa.Column('chunk_type', sa.String(50), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('metadata', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('content_hash', name='uq_knowledge_chunks_content_hash'),
    )
    op.create_index('ix_knowledge_chunks_site_id', 'knowledge_chunks', ['site_id'])
    op.create_index('ix_knowledge_chunks_public_site_id', 'knowledge_chunks', ['public_site_id'])
    op.create_index('ix_knowledge_chunks_path', 'knowledge_chunks', ['path'])
    op.create_index('ix_knowledge_chunks_chunk_type', 'knowledge_chunks', ['chunk_type'])
    op.create_index('ix_knowledge_chunks_content_hash', 'knowledge_chunks', ['content_hash'])
    op.create_index('ix_knowledge_chunks_created_at', 'knowledge_chunks', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_knowledge_chunks_created_at', 'knowledge_chunks')
    op.drop_index('ix_knowledge_chunks_content_hash', 'knowledge_chunks')
    op.drop_index('ix_knowledge_chunks_chunk_type', 'knowledge_chunks')
    op.drop_index('ix_knowledge_chunks_path', 'knowledge_chunks')
    op.drop_index('ix_knowledge_chunks_public_site_id', 'knowledge_chunks')
    op.drop_index('ix_knowledge_chunks_site_id', 'knowledge_chunks')
    op.drop_table('knowledge_chunks')
