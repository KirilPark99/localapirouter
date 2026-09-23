"""Add context_length column to routing_profiles.

Revision ID: a1b2c3d4e5f6
Revises: 9b1c2d3e4f50
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "9b1c2d3e4f50"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(inspector: sa.Inspector, table: str) -> dict:
    return {column["name"]: column for column in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    profiles = _columns(inspector, "routing_profiles")
    if "context_length" not in profiles:
        op.add_column(
            "routing_profiles",
            sa.Column("context_length", sa.Integer(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    profiles = _columns(inspector, "routing_profiles")
    if "context_length" in profiles:
        op.drop_column("routing_profiles", "context_length")
