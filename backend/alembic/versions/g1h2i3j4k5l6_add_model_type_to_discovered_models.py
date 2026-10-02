"""Add model_type to discovered_models.

Revision ID: g1h2i3j4k5l6
Revises: f6a7b8c9d0e1
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "g1h2i3j4k5l6"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("discovered_models") as batch_op:
        batch_op.add_column(
            sa.Column("model_type", sa.String(length=50), nullable=False, server_default="openai")
        )


def downgrade() -> None:
    with op.batch_alter_table("discovered_models") as batch_op:
        batch_op.drop_column("model_type")
