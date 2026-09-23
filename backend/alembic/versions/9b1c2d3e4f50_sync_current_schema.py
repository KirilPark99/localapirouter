"""Synchronize routing and model columns with ORM metadata.

Revision ID: 9b1c2d3e4f50
Revises: f29aa816bb42
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "9b1c2d3e4f50"
down_revision: Union[str, Sequence[str], None] = "f29aa816bb42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(inspector: sa.Inspector, table: str) -> dict:
    return {column["name"]: column for column in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    discovered = _columns(inspector, "discovered_models")
    if "is_visible" not in discovered:
        op.add_column(
            "discovered_models",
            sa.Column("is_visible", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
    if "reasoning_effort" not in discovered:
        op.add_column(
            "discovered_models",
            sa.Column("reasoning_effort", sa.String(50), nullable=True),
        )

    profiles = _columns(inspector, "routing_profiles")
    if "thinking_effort" not in profiles:
        op.add_column(
            "routing_profiles",
            sa.Column("thinking_effort", sa.String(50), nullable=True),
        )

    candidates = _columns(inspector, "routing_candidates")
    target_fk_exists = any(
        fk.get("constrained_columns") == ["target_profile_id"]
        for fk in inspector.get_foreign_keys("routing_candidates")
    )
    needs_batch = (
        "candidate_type" not in candidates
        or "target_profile_id" not in candidates
        or "thinking_effort" not in candidates
        or not candidates["provider_id"]["nullable"]
        or not candidates["model_id"]["nullable"]
        or not target_fk_exists
    )
    if needs_batch:
        with op.batch_alter_table("routing_candidates", recreate="auto") as batch:
            if "candidate_type" not in candidates:
                batch.add_column(
                    sa.Column("candidate_type", sa.String(30), nullable=False, server_default="model")
                )
            if "target_profile_id" not in candidates:
                batch.add_column(sa.Column("target_profile_id", sa.Integer(), nullable=True))
            if "thinking_effort" not in candidates:
                batch.add_column(sa.Column("thinking_effort", sa.String(50), nullable=True))
            if not candidates["provider_id"]["nullable"]:
                batch.alter_column(
                    "provider_id", existing_type=candidates["provider_id"]["type"], nullable=True
                )
            if not candidates["model_id"]["nullable"]:
                batch.alter_column(
                    "model_id", existing_type=candidates["model_id"]["type"], nullable=True
                )
            if not target_fk_exists:
                batch.create_foreign_key(
                    "fk_routing_candidates_target_profile_id",
                    "routing_profiles",
                    ["target_profile_id"],
                    ["id"],
                    ondelete="CASCADE",
                )


def downgrade() -> None:
    raise RuntimeError("This schema synchronization migration is not safely reversible")
