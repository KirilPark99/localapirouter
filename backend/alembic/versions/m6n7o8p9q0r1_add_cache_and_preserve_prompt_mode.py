"""Add response_cache_entries, cache_metrics and preserve_system_prompt_mode.

Revision ID: m6n7o8p9q0r1
Revises: l5m6n7o8p9q0
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "m6n7o8p9q0r1"
down_revision: Union[str, Sequence[str], None] = "l5m6n7o8p9q0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add preserve_system_prompt_mode to compression_global_settings
    with op.batch_alter_table("compression_global_settings") as batch_op:
        batch_op.add_column(
            sa.Column(
                "preserve_system_prompt_mode",
                sa.String(length=50),
                nullable=False,
                server_default=sa.text("'when_caching'"),
            )
        )

    # 2. Create response_cache_entries table
    op.create_table(
        "response_cache_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("signature", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=150), nullable=False),
        sa.Column("response_json", sa.JSON(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("last_hit_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("signature"),
    )
    op.create_index("ix_response_cache_entries_signature", "response_cache_entries", ["signature"], unique=True)
    op.create_index("ix_response_cache_entries_model", "response_cache_entries", ["model"])

    # 3. Create cache_metrics table
    op.create_table(
        "cache_metrics",
        sa.Column("key", sa.String(length=50), nullable=False),
        sa.Column("value", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("cache_metrics")
    op.drop_index("ix_response_cache_entries_model", table_name="response_cache_entries")
    op.drop_index("ix_response_cache_entries_signature", table_name="response_cache_entries")
    op.drop_table("response_cache_entries")
    with op.batch_alter_table("compression_global_settings") as batch_op:
        batch_op.drop_column("preserve_system_prompt_mode")
