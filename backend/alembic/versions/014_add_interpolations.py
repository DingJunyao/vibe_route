"""add track_interpolations table and interpolated fields to track_points

Revision ID: 014_add_interpolations
Revises: 013_add_user_configs_and_share
Create Date: 2026-02-08

添加轨迹插值功能相关表结构。
兼容 SQLite / MySQL / PostgreSQL。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '014_add_interpolations'
down_revision = '013_add_user_configs_and_share'
branch_labels = None
depends_on = None


def upgrade():
    """
    创建插值表并添加插值标记字段
    """
    # 创建 track_interpolations 表
    op.create_table(
        'track_interpolations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('is_valid', sa.Boolean(), nullable=False, server_default='1'),

        sa.Column('track_id', sa.Integer(), nullable=False, comment='关联轨迹ID'),
        sa.Column('start_point_index', sa.Integer(), nullable=False, comment='起点索引'),
        sa.Column('end_point_index', sa.Integer(), nullable=False, comment='终点索引'),
        sa.Column('path_geometry', sa.Text(), nullable=False, comment='控制点数据(JSON格式)'),
        sa.Column('interpolation_interval_seconds', sa.Integer(), nullable=False, server_default='1', comment='插值间隔(秒)'),
        sa.Column('point_count', sa.Integer(), nullable=False, comment='插入的点数'),
        sa.Column('algorithm', sa.String(length=50), nullable=False, server_default='cubic_bezier', comment='插值算法'),

        sa.PrimaryKeyConstraint('id')
    )

    # 创建索引
    op.create_index('ix_track_interpolations_track_id', 'track_interpolations', ['track_id'])
    op.create_index('ix_track_interpolations_is_valid', 'track_interpolations', ['is_valid'])

    # 为 track_points 表添加插值相关字段
    op.add_column('track_points', sa.Column('is_interpolated', sa.Boolean(), nullable=False, server_default='0', comment='是否为插值点'))
    op.add_column('track_points', sa.Column('interpolation_id', sa.Integer(), nullable=True, comment='关联的插值ID'))

    # 创建外键（SQLite 不支持外键，会忽略）
    try:
        op.create_foreign_key('fk_track_interpolations_track_id', 'track_interpolations', 'tracks', ['track_id'], ['id'])
        op.create_foreign_key('fk_track_points_interpolation_id', 'track_points', 'track_interpolations', ['interpolation_id'], ['id'])
    except Exception:
        # SQLite 不支持外键，忽略错误
        pass


def downgrade():
    """
    回滚迁移
    """
    # 删除外键
    try:
        op.drop_constraint('fk_track_points_interpolation_id', 'track_points', type_='foreignkey')
        op.drop_constraint('fk_track_interpolations_track_id', 'track_interpolations', type_='foreignkey')
    except Exception:
        pass

    # 删除字段
    op.drop_column('track_points', 'interpolation_id')
    op.drop_column('track_points', 'is_interpolated')

    # 删除索引
    op.drop_index('ix_track_interpolations_is_valid', 'track_interpolations')
    op.drop_index('ix_track_interpolations_track_id', 'track_interpolations')

    # 删除表
    op.drop_table('track_interpolations')
