"""add live_recordings table

Revision ID: 005_add_live_recordings_table
Revises: 004_fix_road_sign_cache_id
Create Date: 2026-01-27

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '005_add_live_recordings_table'
down_revision = '004_fix_road_sign_cache_id'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'live_recordings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(64), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('track_count', sa.Integer(), nullable=False),
        sa.Column('last_upload_at', sa.DateTime(), nullable=True),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('current_track_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('is_valid', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['current_track_id'], ['tracks.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token')
    )
    op.create_index(op.f('ix_live_recordings_created_by'), 'live_recordings', ['created_by'])
    op.create_index(op.f('ix_live_recordings_is_valid'), 'live_recordings', ['is_valid'])
    op.create_index(op.f('ix_live_recordings_token'), 'live_recordings', ['token'])
    op.create_index(op.f('ix_live_recordings_updated_by'), 'live_recordings', ['updated_by'])
    op.create_index(op.f('ix_live_recordings_user_id'), 'live_recordings', ['user_id'])


def downgrade():
    op.drop_index(op.f('ix_live_recordings_user_id'), table_name='live_recordings')
    op.drop_index(op.f('ix_live_recordings_updated_by'), table_name='live_recordings')
    op.drop_index(op.f('ix_live_recordings_token'), table_name='live_recordings')
    op.drop_index(op.f('ix_live_recordings_is_valid'), table_name='live_recordings')
    op.drop_index(op.f('ix_live_recordings_created_by'), table_name='live_recordings')
    op.drop_table('live_recordings')
