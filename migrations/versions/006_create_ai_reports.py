"""Create ai_reports table

Revision ID: 006
Revises: 005
Create Date: 2026-07-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ai_reports',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('site_id', UUID(as_uuid=True), sa.ForeignKey('sites.id'), nullable=False),
        sa.Column('public_site_id', sa.String(64), nullable=False),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('report_type', sa.String(50), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('main_problem', sa.Text(), nullable=False),
        sa.Column('recommendations', JSONB(), nullable=True),
        sa.Column('funnel', JSONB(), nullable=True),
        sa.Column('strengths', JSONB(), nullable=True),
        sa.Column('weaknesses', JSONB(), nullable=True),
        sa.Column('missing_information', JSONB(), nullable=True),
        sa.Column('raw_ai_response', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_ai_reports_site_id', 'ai_reports', ['site_id'])
    op.create_index('ix_ai_reports_public_site_id', 'ai_reports', ['public_site_id'])
    op.create_index('ix_ai_reports_report_type', 'ai_reports', ['report_type'])
    op.create_index('ix_ai_reports_period_start', 'ai_reports', ['period_start'])
    op.create_index('ix_ai_reports_period_end', 'ai_reports', ['period_end'])
    op.create_index('ix_ai_reports_created_at', 'ai_reports', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_ai_reports_created_at', 'ai_reports')
    op.drop_index('ix_ai_reports_period_end', 'ai_reports')
    op.drop_index('ix_ai_reports_period_start', 'ai_reports')
    op.drop_index('ix_ai_reports_report_type', 'ai_reports')
    op.drop_index('ix_ai_reports_public_site_id', 'ai_reports')
    op.drop_index('ix_ai_reports_site_id', 'ai_reports')
    op.drop_table('ai_reports')
