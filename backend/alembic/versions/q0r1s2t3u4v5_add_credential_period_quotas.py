"""Add provider-credential budgets without changing router-key quota tables."""
from alembic import op
import sqlalchemy as sa

revision = "q0r1s2t3u4v5"
down_revision = "p9q0r1s2t3u4"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if 'quota_rules' not in {c['name'] for c in sa.inspect(bind).get_columns('provider_credentials')}:
        op.add_column('provider_credentials', sa.Column('quota_rules', sa.JSON(), nullable=False, server_default='[]'))
    tables = set(sa.inspect(bind).get_table_names())
    if 'credential_period_quota_counters' not in tables:
        op.create_table('credential_period_quota_counters',
            sa.Column('key_id', sa.Integer(), sa.ForeignKey('provider_credentials.id', ondelete='CASCADE'), primary_key=True),
            sa.Column('rule_identity', sa.String(64), primary_key=True),
            sa.Column('window_start', sa.String(40), primary_key=True),
            sa.Column('requests', sa.Integer(), nullable=False),
            sa.Column('tokens', sa.Integer(), nullable=False),
            sa.Column('usd', sa.Float(), nullable=False))
    if 'credential_period_quota_reservations' not in tables:
        op.create_table('credential_period_quota_reservations',
            sa.Column('id', sa.String(32), primary_key=True),
            sa.Column('key_id', sa.Integer(), sa.ForeignKey('provider_credentials.id', ondelete='CASCADE'), nullable=False),
            sa.Column('allocations', sa.JSON(), nullable=False),
            sa.Column('prices', sa.JSON(), nullable=False),
            sa.Column('settled', sa.Boolean(), nullable=False))
        op.create_index('ix_credential_period_quota_reservations_key_id', 'credential_period_quota_reservations', ['key_id'])


def downgrade():
    op.drop_table('credential_period_quota_reservations')
    op.drop_table('credential_period_quota_counters')
    op.drop_column('provider_credentials', 'quota_rules')
