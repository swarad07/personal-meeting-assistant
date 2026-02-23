"""add app_settings table

Revision ID: d5b2c8e41f03
Revises: c4a1e7f30d12
Create Date: 2026-02-23 22:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd5b2c8e41f03'
down_revision: Union[str, None] = 'c4a1e7f30d12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'app_settings',
        sa.Column('key', sa.String(128), primary_key=True),
        sa.Column('value', sa.Text(), nullable=False, server_default=''),
        sa.Column('is_secret', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('app_settings')
