"""Add group_name to provider_credentials and credential_group to routing_candidates.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(inspector: sa.Inspector, table: str) -> dict:
    return {column["name"]: column for column in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    cred_cols = _columns(inspector, "provider_credentials")
    if "group_name" not in cred_cols:
        op.add_column(
            "provider_credentials",
            sa.Column("group_name", sa.String(length=100), nullable=True),
        )

    cand_cols = _columns(inspector, "routing_candidates")
    if "credential_group" not in cand_cols:
        op.add_column(
            "routing_candidates",
            sa.Column("credential_group", sa.String(length=100), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    cred_cols = _columns(inspector, "provider_credentials")
    if "group_name" in cred_cols:
        op.drop_column("provider_credentials", "group_name")

    cand_cols = _columns(inspector, "routing_candidates")
    if "credential_group" in cand_cols:
        op.drop_column("routing_candidates", "credential_group")
