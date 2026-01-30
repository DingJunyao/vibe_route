"""add postgis spatial extension table

Revision ID: 008_add_postgis_spatial_extension
Revises: 007_change_track_points_to_double
Create Date: 2026-01-30

此迁移创建可选的 PostGIS 空间扩展表。

注意：此迁移仅在 PostgreSQL + PostGIS 环境中需要。
对于 SQLite 或 MySQL，此迁移不会执行（使用 op.execute 的条件执行）。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '008_add_postgis_spatial_extension'
down_revision = '007_change_track_points_to_double'
branch_labels = None
depends_on = None


def upgrade():
    """
    创建 PostGIS 空间扩展表（可选）

    使用 IF EXISTS 确保在非 PostgreSQL 环境中不会报错。
    """
    # 创建 PostGIS 空间扩展表（可选表，仅 PostgreSQL）
    # 使用 PostgreSQL 特定语法，在其他数据库中会跳过
    op.execute("""
        -- 仅在 PostgreSQL 中执行
        CREATE TABLE IF NOT EXISTS track_points_spatial (
            point_id INTEGER PRIMARY KEY REFERENCES track_points(id) ON DELETE CASCADE,
            geom GEOGRAPHY(POINT, 4326) NOT NULL
        );

        -- 创建 GIST 空间索引
        CREATE INDEX IF NOT EXISTS idx_track_points_spatial_geom
            ON track_points_spatial USING GIST(geom);
    """)

    # 为现有数据创建 geometry（如果表已存在且有数据）
    op.execute("""
        -- 为现有轨迹点创建 geometry 记录
        INSERT INTO track_points_spatial (point_id, geom)
        SELECT id, ST_MakePoint(longitude_wgs84, latitude_wgs84)::geography
        FROM track_points
        WHERE id NOT IN (SELECT point_id FROM track_points_spatial)
        ON CONFLICT (point_id) DO NOTHING;
    """)


def downgrade():
    """删除 PostGIS 空间扩展表"""
    op.execute("""
        DROP TABLE IF EXISTS track_points_spatial;
    """)
