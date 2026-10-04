"""Add security_configs table.

Revision ID: n7o8p9q0r1s2
Revises: m6n7o8p9q0r1
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "n7o8p9q0r1s2"
down_revision: Union[str, Sequence[str], None] = "m6n7o8p9q0r1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "security_configs",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("injection_guard_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("injection_mode", sa.String(length=20), nullable=False, server_default=sa.text("'warn'")),
        sa.Column("injection_threshold", sa.String(length=20), nullable=False, server_default=sa.text("'high'")),
        sa.Column("max_injection_scan_bytes", sa.Integer(), nullable=False, server_default=sa.text("16384")),
        sa.Column("custom_injection_patterns", sa.JSON(), nullable=True),
        sa.Column("credential_masking_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("mask_inbound", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("mask_outbound", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("custom_credential_patterns", sa.JSON(), nullable=True),
        sa.Column("duckduckgo_fallback_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("oidc_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("oidc_disable_password_login", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("oidc_issuer", sa.String(length=500), nullable=True, server_default=sa.text("''")),
        sa.Column("oidc_client_id", sa.String(length=255), nullable=True, server_default=sa.text("''")),
        sa.Column("oidc_client_secret", sa.String(length=500), nullable=True, server_default=sa.text("''")),
        sa.Column("oidc_scopes", sa.JSON(), nullable=True),
        sa.Column("oidc_allowed_emails", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("security_configs")
