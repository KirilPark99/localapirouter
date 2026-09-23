"""Add temperature and fusion candidate/judge options.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("routing_profiles") as batch_op:
        batch_op.add_column(sa.Column("temperature", sa.Float(), nullable=True))

    with op.batch_alter_table("routing_candidates") as batch_op:
        batch_op.add_column(sa.Column("temperature", sa.Float(), nullable=True))

    with op.batch_alter_table("fusion_profiles") as batch_op:
        batch_op.add_column(sa.Column("judge_credential_group", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("judge_thinking_effort", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("judge_temperature", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("temperature", sa.Float(), nullable=True))

    with op.batch_alter_table("fusion_participants") as batch_op:
        batch_op.add_column(sa.Column("thinking_effort", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("temperature", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("priority_order", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("fusion_participants") as batch_op:
        batch_op.drop_column("priority_order")
        batch_op.drop_column("temperature")
        batch_op.drop_column("thinking_effort")

    with op.batch_alter_table("fusion_profiles") as batch_op:
        batch_op.drop_column("temperature")
        batch_op.drop_column("judge_temperature")
        batch_op.drop_column("judge_thinking_effort")
        batch_op.drop_column("judge_credential_group")

    with op.batch_alter_table("routing_candidates") as batch_op:
        batch_op.drop_column("temperature")

    with op.batch_alter_table("routing_profiles") as batch_op:
        batch_op.drop_column("temperature")
