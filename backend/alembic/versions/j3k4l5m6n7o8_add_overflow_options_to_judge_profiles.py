"""Add overflow options to judge profiles.

Revision ID: j3k4l5m6n7o8
Revises: i2j3k4l5m6n7
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "j3k4l5m6n7o8"
down_revision: Union[str, Sequence[str], None] = "i2j3k4l5m6n7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("judge_profiles") as batch_op:
        batch_op.add_column(sa.Column("fallback_strongest_on_overflow", sa.Boolean(), server_default=sa.text("0"), nullable=False))
        batch_op.add_column(sa.Column("context_length", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("judge_profiles") as batch_op:
        batch_op.drop_column("context_length")
        batch_op.drop_column("fallback_strongest_on_overflow")
