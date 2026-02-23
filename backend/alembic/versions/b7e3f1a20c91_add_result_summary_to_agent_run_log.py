"""add result_summary to agent_run_log

Revision ID: b7e3f1a20c91
Revises: 13997c20c3c6
Create Date: 2026-02-23 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b7e3f1a20c91"
down_revision: Union[str, None] = "13997c20c3c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agent_run_log", sa.Column("result_summary", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("agent_run_log", "result_summary")
