"""Add profile-level context window to Fusion."""
from alembic import op
import sqlalchemy as sa

revision = "o8p9q0r1s2t3"
down_revision = "n7o8p9q0r1s2"
branch_labels = None
depends_on = None


def upgrade():
    if "context_length" not in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("fusion_profiles")}:
        op.add_column("fusion_profiles", sa.Column("context_length", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("fusion_profiles", "context_length")
