"""Add country and country_code columns to proxies.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(inspector: sa.Inspector, table: str) -> dict:
    return {column["name"]: column for column in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    proxies_cols = _columns(inspector, "proxies")
    if "country" not in proxies_cols:
        op.add_column(
            "proxies",
            sa.Column("country", sa.String(length=100), nullable=True),
        )
    if "country_code" not in proxies_cols:
        op.add_column(
            "proxies",
            sa.Column("country_code", sa.String(length=10), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    proxies_cols = _columns(inspector, "proxies")
    if "country_code" in proxies_cols:
        op.drop_column("proxies", "country_code")
    if "country" in proxies_cols:
        op.drop_column("proxies", "country")
