"""add geometry field to admin_divisions for shapely polygon query

Revision ID: 012_add_geometry_to_admin_divisions
Revises: 010_add_admin_divisions
Create Date: 2026-02-02

此迁移为 admin_divisions 表添加 geometry 字段，用于存储 GeoJSON 格式的多边形数据，
支持使用 shapely 库进行精确的多边形包含判断，替代原有的边界框查询。
兼容 SQLite / MySQL / PostgreSQL。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '012_add_geometry_to_admin_divisions'
down_revision = '010_add_admin_divisions'
branch_labels = None
depends_on = None


def upgrade():
    """
    添加 geometry 字段（通用语法）
    """
    # 添加 geometry 字段（TEXT 类型存储 GeoJSON 字符串）
    op.add_column(
        'admin_divisions',
        sa.Column('geometry', sa.Text(), nullable=True, comment='GeoJSON 多边形几何')
    )


def downgrade():
    """
    删除 geometry 字段
    """
    op.drop_column('admin_divisions', 'geometry')
