"""add is_live_recording flag to tracks

Revision ID: 009_add_is_live_recording_flag
Revises: 008_add_postgis_spatial_extension
Create Date: 2026-01-31

此迁移添加 is_live_recording 字段到 tracks 表，
用于标记实时记录的轨迹，避免与普通轨迹混合显示。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '009_add_is_live_recording_flag'
down_revision = '008_add_postgis_spatial_extension'
branch_labels = None
depends_on = None


def upgrade():
    """
    添加 is_live_recording 列到 tracks 表
    """
    # SQLite, MySQL, PostgreSQL 通用语法
    with op.batch_alter_table('tracks') as batch_op:
        batch_op.add_column(sa.Column('is_live_recording', sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    """
    删除 is_live_recording 列
    """
    with op.batch_alter_table('tracks') as batch_op:
        batch_op.drop_column('is_live_recording')
