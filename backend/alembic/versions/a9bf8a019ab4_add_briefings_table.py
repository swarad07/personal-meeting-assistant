"""add briefings table

Revision ID: a9bf8a019ab4
Revises: 48ed63022bdd
Create Date: 2026-02-23 14:38:00.326809
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'a9bf8a019ab4'
down_revision: Union[str, None] = '48ed63022bdd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'briefings',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('meeting_id', sa.Uuid(), sa.ForeignKey('meetings.id'), nullable=True),
        sa.Column('calendar_event_id', sa.String(), nullable=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('topics', postgresql.JSONB(), nullable=True),
        sa.Column('attendee_context', postgresql.JSONB(), nullable=True),
        sa.Column('action_items_context', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('briefings')
