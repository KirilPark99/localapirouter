"""Add randomize_candidates and randomize_keys to routing_profiles.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(inspector: sa.Inspector, table: str) -> dict:
    return {column["name"]: column for column in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    rp_cols = _columns(inspector, "routing_profiles")
    if "randomize_candidates" not in rp_cols:
        op.add_column(
            "routing_profiles",
            sa.Column("randomize_candidates", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        )
    if "randomize_keys" not in rp_cols:
        op.add_column(
            "routing_profiles",
            sa.Column("randomize_keys", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    rp_cols = _columns(inspector, "routing_profiles")
    if "randomize_keys" in rp_cols:
        op.drop_column("routing_profiles", "randomize_keys")
    if "randomize_candidates" in rp_cols:
        op.drop_column("routing_profiles", "randomize_candidates")
