"""Add compression stages and global settings tables.

Revision ID: l5m6n7o8p9q0
Revises: k4l5m6n7o8p9
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "l5m6n7o8p9q0"
down_revision: Union[str, Sequence[str], None] = "k4l5m6n7o8p9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "compression_global_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("trigger_token_threshold", sa.Integer(), nullable=False, server_default=sa.text("1000")),
        sa.Column("min_savings_bailout_percent", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("preserve_recent_turns", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("enable_telemetry", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("fail_open", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "compression_stages",
        sa.Column("id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("icon", sa.String(length=50), nullable=False, server_default=sa.text("'Zap'")),
        sa.Column("stage_type", sa.String(length=50), nullable=False, server_default=sa.text("'builtin'")),
        sa.Column("priority_order", sa.Integer(), nullable=False, server_default=sa.text("10")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("config_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("custom_rules", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("compression_stages")
    op.drop_table("compression_global_settings")
