"""Create block_classifications table

Revision ID: 005
Revises: 004
Create Date: 2026-07-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'block_classifications',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('site_id', UUID(as_uuid=True), sa.ForeignKey('sites.id'), nullable=False),
        sa.Column('knowledge_chunk_id', UUID(as_uuid=True), sa.ForeignKey('knowledge_chunks.id'), nullable=False),
        sa.Column('public_site_id', sa.String(64), nullable=False),
        sa.Column('path', sa.Text(), nullable=False),
        sa.Column('chunk_type', sa.String(50), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('detected_items', JSONB(), nullable=True),
        sa.Column('raw_ai_response', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('knowledge_chunk_id', name='uq_block_classifications_chunk_id'),
    )
    op.create_index('ix_block_classifications_site_id', 'block_classifications', ['site_id'])
    op.create_index('ix_block_classifications_public_site_id', 'block_classifications', ['public_site_id'])
    op.create_index('ix_block_classifications_category', 'block_classifications', ['category'])
    op.create_index('ix_block_classifications_path', 'block_classifications', ['path'])
    op.create_index('ix_block_classifications_created_at', 'block_classifications', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_block_classifications_created_at', 'block_classifications')
    op.drop_index('ix_block_classifications_path', 'block_classifications')
    op.drop_index('ix_block_classifications_category', 'block_classifications')
    op.drop_index('ix_block_classifications_public_site_id', 'block_classifications')
    op.drop_index('ix_block_classifications_site_id', 'block_classifications')
    op.drop_table('block_classifications')
