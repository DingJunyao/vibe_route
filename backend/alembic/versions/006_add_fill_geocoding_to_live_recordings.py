"""add fill_geocoding to live_recordings

Revision ID: 006_add_fill_geocoding_to_live_recordings
Revises: 005_add_live_recordings_table
Create Date: 2026-01-28

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006_add_fill_geocoding_to_live_recordings'
down_revision = '005_add_live_recordings_table'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('live_recordings', sa.Column('fill_geocoding', sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    op.drop_column('live_recordings', 'fill_geocoding')
