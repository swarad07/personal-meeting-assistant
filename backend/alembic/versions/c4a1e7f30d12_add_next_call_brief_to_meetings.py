"""add next_call_brief to meetings

Revision ID: c4a1e7f30d12
Revises: b7e3f1a20c91
Create Date: 2026-02-23 21:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4a1e7f30d12'
down_revision: Union[str, None] = 'b7e3f1a20c91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('meetings', sa.Column('next_call_brief', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('meetings', 'next_call_brief')
