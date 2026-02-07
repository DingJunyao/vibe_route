"""add user_configs table and share fields to tracks

Revision ID: 013_add_user_configs_and_share
Revises: 012_add_geometry_to_admin_divisions
Create Date: 2026-02-06

此迁移创建用户配置表并为轨迹表添加分享相关字段。
兼容 SQLite / MySQL / PostgreSQL。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '013_add_user_configs_and_share'
down_revision = '012_add_geometry_to_admin_divisions'
branch_labels = None
depends_on = None


def upgrade():
    """
    创建用户配置表并添加分享字段
    """
    # 创建 user_configs 表
    op.create_table(
        'user_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('is_valid', sa.Boolean(), nullable=False, server_default='1'),

        sa.Column('user_id', sa.Integer(), nullable=False, comment='关联用户ID'),

        sa.Column('map_provider', sa.String(length=50), nullable=True, comment='默认地图提供商'),
        sa.Column('map_layers', sa.JSON(), nullable=True, comment='地图层配置'),

        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )

    # 创建索引
    op.create_index('ix_user_configs_user_id', 'user_configs', ['user_id'], unique=True)

    # 为 tracks 表添加分享相关字段
    op.add_column('tracks', sa.Column('share_token', sa.String(length=36), nullable=True, comment='分享令牌'))
    op.add_column('tracks', sa.Column('is_shared', sa.Boolean(), nullable=False, server_default='0', comment='是否开启分享'))

    # 创建分享令牌索引
    op.create_index('ix_tracks_share_token', 'tracks', ['share_token'], unique=True)


def downgrade():
    """
    回滚迁移
    """
    # 删除分享字段
    op.drop_index('ix_tracks_share_token', 'tracks')
    op.drop_column('tracks', 'is_shared')
    op.drop_column('tracks', 'share_token')

    # 删除 user_configs 表
    op.drop_table('user_configs')
