"""add admin_divisions table for local geocoding

Revision ID: 010_add_admin_divisions
Revises: 009_add_is_live_recording_flag
Create Date: 2026-02-01

此迁移创建本地地理编码所需的行政区划表。
兼容 SQLite / MySQL / PostgreSQL。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '010_add_admin_divisions'
down_revision = '009_add_is_live_recording_flag'
branch_labels = None
depends_on = None


def upgrade():
    """
    创建行政区划表（通用语法）
    """
    op.create_table(
        'admin_divisions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('is_valid', sa.Boolean(), nullable=False, server_default='1'),

        sa.Column('code', sa.String(length=12), nullable=False, comment='行政区划代码'),
        sa.Column('name', sa.String(length=100), nullable=False, comment='中文名称'),
        sa.Column('name_en', sa.String(length=200), nullable=True, comment='英文名称'),
        sa.Column('level', sa.String(length=10), nullable=False, comment='层级：province/city/area'),
        sa.Column('parent_code', sa.String(length=12), nullable=True, comment='上级行政区划代码'),

        sa.Column('min_lat', sa.Integer(), nullable=True, comment='最小纬度 * 1e6'),
        sa.Column('max_lat', sa.Integer(), nullable=True, comment='最大纬度 * 1e6'),
        sa.Column('min_lon', sa.Integer(), nullable=True, comment='最小经度 * 1e6'),
        sa.Column('max_lon', sa.Integer(), nullable=True, comment='最大经度 * 1e6'),

        sa.Column('province_code', sa.String(length=12), nullable=True, comment='省代码'),
        sa.Column('city_code', sa.String(length=12), nullable=True, comment='市代码'),

        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )

    # 创建索引
    op.create_index(op.f('ix_admin_divisions_code'), 'admin_divisions', ['code'], unique=True)
    op.create_index(op.f('ix_admin_divisions_level'), 'admin_divisions', ['level'], unique=False)
    op.create_index(op.f('ix_admin_divisions_parent_code'), 'admin_divisions', ['parent_code'], unique=False)
    op.create_index(op.f('ix_admin_divisions_province_code'), 'admin_divisions', ['province_code'], unique=False)
    op.create_index(op.f('ix_admin_divisions_city_code'), 'admin_divisions', ['city_code'], unique=False)
    op.create_index(op.f('ix_admin_divisions_is_valid'), 'admin_divisions', ['is_valid'], unique=False)

    # 尝试创建 PostGIS 空间表（仅在 PostgreSQL 环境下生效）
    # 使用 op.execute 可以安全地在非 PostgreSQL 环境下忽略错误
    try:
        op.execute("""
            CREATE TABLE IF NOT EXISTS admin_divisions_spatial (
                division_id INTEGER PRIMARY KEY REFERENCES admin_divisions(id) ON DELETE CASCADE,
                geom GEOMETRY(POLYGON, 4326)
            );

            CREATE INDEX IF NOT EXISTS idx_admin_divisions_spatial_geom
                ON admin_divisions_spatial USING GIST(geom);
        """)
    except Exception:
        # 非 PostgreSQL 环境或没有 PostGIS 扩展，忽略
        pass


def downgrade():
    """
    删除行政区划表
    """
    # 先删除 PostGIS 表（如果存在）
    try:
        op.execute("DROP TABLE IF EXISTS admin_divisions_spatial")
    except Exception:
        pass

    op.drop_table('admin_divisions')
