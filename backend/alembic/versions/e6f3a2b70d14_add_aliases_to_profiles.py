"""add aliases to profiles

Revision ID: e6f3a2b70d14
Revises: d5b2c8e41f03
Create Date: 2026-02-23 23:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = 'e6f3a2b70d14'
down_revision: Union[str, None] = 'd5b2c8e41f03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('profiles', sa.Column('aliases', JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column('profiles', 'aliases')
