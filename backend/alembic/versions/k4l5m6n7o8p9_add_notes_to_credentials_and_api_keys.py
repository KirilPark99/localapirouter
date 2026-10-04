"""Add notes to credentials and router api keys.

Revision ID: k4l5m6n7o8p9
Revises: j3k4l5m6n7o8
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "k4l5m6n7o8p9"
down_revision: Union[str, Sequence[str], None] = "j3k4l5m6n7o8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("provider_credentials") as batch_op:
        batch_op.add_column(sa.Column("notes", sa.Text(), nullable=True))

    with op.batch_alter_table("router_api_keys") as batch_op:
        batch_op.add_column(sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("router_api_keys") as batch_op:
        batch_op.drop_column("notes")

    with op.batch_alter_table("provider_credentials") as batch_op:
        batch_op.drop_column("notes")
