"""Persistent key period rules, counters and dispatch reservations."""
from alembic import op
import sqlalchemy as sa

revision = "p9q0r1s2t3u4"
down_revision = "o8p9q0r1s2t3"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if 'quota_rules' not in {c['name'] for c in sa.inspect(bind).get_columns('router_api_keys')}:
        op.add_column('router_api_keys', sa.Column('quota_rules', sa.JSON(), nullable=False, server_default='[]'))
    tables = set(sa.inspect(bind).get_table_names())
    if 'period_quota_counters' not in tables:
        op.create_table('period_quota_counters',
            sa.Column('key_id', sa.Integer(), sa.ForeignKey('router_api_keys.id', ondelete='CASCADE'), primary_key=True),
            sa.Column('rule_identity', sa.String(64), primary_key=True),
            sa.Column('window_start', sa.String(40), primary_key=True),
            sa.Column('requests', sa.Integer(), nullable=False),
            sa.Column('tokens', sa.Integer(), nullable=False),
            sa.Column('usd', sa.Float(), nullable=False))
    if 'period_quota_reservations' not in tables:
        op.create_table('period_quota_reservations',
            sa.Column('id', sa.String(32), primary_key=True),
            sa.Column('key_id', sa.Integer(), sa.ForeignKey('router_api_keys.id', ondelete='CASCADE'), nullable=False),
            sa.Column('allocations', sa.JSON(), nullable=False),
            sa.Column('prices', sa.JSON(), nullable=False),
            sa.Column('settled', sa.Boolean(), nullable=False))
        op.create_index('ix_period_quota_reservations_key_id', 'period_quota_reservations', ['key_id'])


def downgrade():
    op.drop_table('period_quota_reservations')
    op.drop_table('period_quota_counters')
    op.drop_column('router_api_keys', 'quota_rules')
