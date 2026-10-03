"""Add judge_profiles, judge_candidates and allowed_judges.

Revision ID: h1i2j3k4l5m6
Revises: g1h2i3j4k5l6
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "h1i2j3k4l5m6"
down_revision: Union[str, Sequence[str], None] = "g1h2i3j4k5l6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create judge_profiles table
    op.create_table(
        "judge_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("strategy", sa.String(length=50), nullable=False, server_default="auto"),
        sa.Column("judge_type", sa.String(length=30), nullable=False, server_default="model"),
        sa.Column("judge_routing_profile_id", sa.Integer(), nullable=True),
        sa.Column("judge_provider_id", sa.Integer(), nullable=True),
        sa.Column("judge_credential_id", sa.Integer(), nullable=True),
        sa.Column("judge_credential_group", sa.String(length=100), nullable=True),
        sa.Column("judge_model_id", sa.Integer(), nullable=True),
        sa.Column("judge_thinking_effort", sa.String(length=50), nullable=True),
        sa.Column("judge_temperature", sa.Float(), nullable=True, server_default="0.1"),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("fallback_candidate_id", sa.Integer(), nullable=True),
        sa.Column("timeout_seconds", sa.Float(), nullable=False, server_default="60.0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["judge_routing_profile_id"], ["routing_profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["judge_provider_id"], ["providers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["judge_credential_id"], ["provider_credentials.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["judge_model_id"], ["discovered_models.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("judge_profiles") as batch_op:
        batch_op.create_index("ix_judge_profiles_slug", ["slug"], unique=True)

    # 2. Create judge_candidates table
    op.create_table(
        "judge_candidates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("candidate_type", sa.String(length=30), nullable=False, server_default="model"),
        sa.Column("target_profile_id", sa.Integer(), nullable=True),
        sa.Column("provider_id", sa.Integer(), nullable=True),
        sa.Column("credential_id", sa.Integer(), nullable=True),
        sa.Column("credential_group", sa.String(length=100), nullable=True),
        sa.Column("model_id", sa.Integer(), nullable=True),
        sa.Column("thinking_effort", sa.String(length=50), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("priority_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("label", sa.String(length=100), nullable=False, server_default="Candidate"),
        sa.Column("task_types", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("complexity_level", sa.String(length=50), nullable=False, server_default="all"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["profile_id"], ["judge_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_profile_id"], ["routing_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["provider_id"], ["providers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["credential_id"], ["provider_credentials.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["model_id"], ["discovered_models.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # 3. Add allowed_judges to router_api_keys
    with op.batch_alter_table("router_api_keys") as batch_op:
        batch_op.add_column(
            sa.Column("allowed_judges", sa.JSON(), nullable=False, server_default='["*"]')
        )


def downgrade() -> None:
    with op.batch_alter_table("router_api_keys") as batch_op:
        batch_op.drop_column("allowed_judges")
    op.drop_table("judge_candidates")
    op.drop_table("judge_profiles")
