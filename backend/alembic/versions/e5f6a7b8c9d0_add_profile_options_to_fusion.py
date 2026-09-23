"""Add profile options and credential flexibility to fusion tables.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("fusion_profiles") as batch_op:
        batch_op.add_column(sa.Column("judge_type", sa.String(length=30), nullable=False, server_default="model"))
        batch_op.add_column(sa.Column("judge_routing_profile_id", sa.Integer(), nullable=True))
        batch_op.alter_column("judge_provider_id", existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column("judge_model_id", existing_type=sa.Integer(), nullable=True)
        batch_op.create_foreign_key(
            "fk_fusion_profiles_judge_routing_profile_id",
            "routing_profiles",
            ["judge_routing_profile_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("fusion_participants") as batch_op:
        batch_op.add_column(sa.Column("participant_type", sa.String(length=30), nullable=False, server_default="model"))
        batch_op.add_column(sa.Column("target_profile_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("credential_group", sa.String(length=100), nullable=True))
        batch_op.alter_column("provider_id", existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column("credential_id", existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column("model_id", existing_type=sa.Integer(), nullable=True)
        batch_op.create_foreign_key(
            "fk_fusion_participants_target_profile_id",
            "routing_profiles",
            ["target_profile_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    with op.batch_alter_table("fusion_participants") as batch_op:
        batch_op.drop_constraint("fk_fusion_participants_target_profile_id", type_="foreignkey")
        batch_op.drop_column("credential_group")
        batch_op.drop_column("target_profile_id")
        batch_op.drop_column("participant_type")

    with op.batch_alter_table("fusion_profiles") as batch_op:
        batch_op.drop_constraint("fk_fusion_profiles_judge_routing_profile_id", type_="foreignkey")
        batch_op.drop_column("judge_routing_profile_id")
        batch_op.drop_column("judge_type")
