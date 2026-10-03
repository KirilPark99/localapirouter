"""Add notes to providers.

Revision ID: i2j3k4l5m6n7
Revises: h1i2j3k4l5m6
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "i2j3k4l5m6n7"
down_revision: Union[str, Sequence[str], None] = "h1i2j3k4l5m6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("providers") as batch_op:
        batch_op.add_column(sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("providers") as batch_op:
        batch_op.drop_column("notes")
