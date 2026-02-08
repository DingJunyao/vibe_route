"""change track points to double for precision

Revision ID: 007_change_track_points_to_double
Revises: 006_add_fill_geocoding_to_live_recordings
Create Date: 2026-01-30

SQLite 不支持 ALTER COLUMN，需要批量模式处理。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007_change_track_points_to_double'
down_revision = '006_add_fill_geocoding_to_live_recordings'
branch_labels = None
depends_on = None


def upgrade():
    """
    将 track_points 表中的浮点列改为 DOUBLE 类型以提高精度
    SQLite 需要重建表
    """
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == 'sqlite':
        # SQLite: 需要重建表
        # 1. 创建新表（使用 DOUBLE 类型）
        op.execute("""
            CREATE TABLE track_points_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id INTEGER NOT NULL,
                point_index INTEGER NOT NULL,
                time DATETIME,
                latitude_wgs84 DOUBLE,
                longitude_wgs84 DOUBLE,
                latitude_gcj02 DOUBLE,
                longitude_gcj02 DOUBLE,
                latitude_bd09 DOUBLE,
                longitude_bd09 DOUBLE,
                elevation DOUBLE,
                speed DOUBLE,
                province VARCHAR(50),
                city VARCHAR(50),
                district VARCHAR(50),
                road_name VARCHAR(200),
                road_number VARCHAR(50),
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                created_by INTEGER,
                updated_by INTEGER,
                is_valid BOOLEAN DEFAULT 1 NOT NULL,
                bearing DOUBLE,
                province_en VARCHAR(100),
                city_en VARCHAR(100),
                district_en VARCHAR(100),
                road_name_en VARCHAR(200),
                memo TEXT
            )
        """)

        # 2. 复制数据
        op.execute("""
            INSERT INTO track_points_new (
                id, track_id, point_index, time,
                latitude_wgs84, longitude_wgs84,
                latitude_gcj02, longitude_gcj02,
                latitude_bd09, longitude_bd09,
                elevation, speed,
                province, city, district, road_name, road_number,
                created_at, updated_at, created_by, updated_by, is_valid,
                bearing, province_en, city_en, district_en, road_name_en, memo
            )
            SELECT
                id, track_id, point_index, time,
                latitude_wgs84, longitude_wgs84,
                latitude_gcj02, longitude_gcj02,
                latitude_bd09, longitude_bd09,
                elevation, speed,
                province, city, district, road_name, road_number,
                created_at, updated_at, created_by, updated_by, is_valid,
                bearing, province_en, city_en, district_en, road_name_en, memo
            FROM track_points
        """)

        # 3. 删除旧表
        op.execute("DROP TABLE track_points")

        # 4. 重命名新表
        op.execute("ALTER TABLE track_points_new RENAME TO track_points")

        # 5. 重建索引
        op.create_index('ix_track_points_track_id', 'track_points', ['track_id'])
    else:
        # MySQL / PostgreSQL: 直接 ALTER COLUMN
        op.alter_column('track_points', 'latitude_wgs84',
                        existing_type=sa.Float(),
                        type_=sa.Double())
        op.alter_column('track_points', 'longitude_wgs84',
                        existing_type=sa.Float(),
                        type_=sa.Double())
        op.alter_column('track_points', 'latitude_gcj02',
                        existing_type=sa.Float(),
                        type_=sa.Double())
        op.alter_column('track_points', 'longitude_gcj02',
                        existing_type=sa.Float(),
                        type_=sa.Double())
        op.alter_column('track_points', 'latitude_bd09',
                        existing_type=sa.Float(),
                        type_=sa.Double())
        op.alter_column('track_points', 'longitude_bd09',
                        existing_type=sa.Float(),
                        type_=sa.Double())
        op.alter_column('track_points', 'elevation',
                        existing_type=sa.Float(),
                        type_=sa.Double())
        op.alter_column('track_points', 'speed',
                        existing_type=sa.Float(),
                        type_=sa.Double())
        op.alter_column('track_points', 'bearing',
                        existing_type=sa.Float(),
                        type_=sa.Double())


def downgrade():
    """
    回滚：将 DOUBLE 改回 FLOAT
    """
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == 'sqlite':
        # SQLite: 需要重建表
        op.execute("""
            CREATE TABLE track_points_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id INTEGER NOT NULL,
                point_index INTEGER NOT NULL,
                time DATETIME,
                latitude_wgs84 FLOAT,
                longitude_wgs84 FLOAT,
                latitude_gcj02 FLOAT,
                longitude_gcj02 FLOAT,
                latitude_bd09 FLOAT,
                longitude_bd09 FLOAT,
                elevation FLOAT,
                speed FLOAT,
                province VARCHAR(50),
                city VARCHAR(50),
                district VARCHAR(50),
                road_name VARCHAR(200),
                road_number VARCHAR(50),
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                created_by INTEGER,
                updated_by INTEGER,
                is_valid BOOLEAN DEFAULT 1 NOT NULL,
                bearing FLOAT,
                province_en VARCHAR(100),
                city_en VARCHAR(100),
                district_en VARCHAR(100),
                road_name_en VARCHAR(200),
                memo TEXT
            )
        """)

        op.execute("""
            INSERT INTO track_points_new (
                id, track_id, point_index, time,
                latitude_wgs84, longitude_wgs84,
                latitude_gcj02, longitude_gcj02,
                latitude_bd09, longitude_bd09,
                elevation, speed,
                province, city, district, road_name, road_number,
                created_at, updated_at, created_by, updated_by, is_valid,
                bearing, province_en, city_en, district_en, road_name_en, memo
            )
            SELECT
                id, track_id, point_index, time,
                latitude_wgs84, longitude_wgs84,
                latitude_gcj02, longitude_gcj02,
                latitude_bd09, longitude_bd09,
                elevation, speed,
                province, city, district, road_name, road_number,
                created_at, updated_at, created_by, updated_by, is_valid,
                bearing, province_en, city_en, district_en, road_name_en, memo
            FROM track_points
        """)

        op.execute("DROP TABLE track_points")
        op.execute("ALTER TABLE track_points_new RENAME TO track_points")

        op.create_index('ix_track_points_track_id', 'track_points', ['track_id'])
    else:
        # MySQL / PostgreSQL: 直接 ALTER COLUMN
        op.alter_column('track_points', 'latitude_wgs84',
                        existing_type=sa.Double(),
                        type_=sa.Float())
        op.alter_column('track_points', 'longitude_wgs84',
                        existing_type=sa.Double(),
                        type_=sa.Float())
        op.alter_column('track_points', 'latitude_gcj02',
                        existing_type=sa.Double(),
                        type_=sa.Float())
        op.alter_column('track_points', 'longitude_gcj02',
                        existing_type=sa.Double(),
                        type_=sa.Float())
        op.alter_column('track_points', 'latitude_bd09',
                        existing_type=sa.Double(),
                        type_=sa.Float())
        op.alter_column('track_points', 'longitude_bd09',
                        existing_type=sa.Double(),
                        type_=sa.Float())
        op.alter_column('track_points', 'elevation',
                        existing_type=sa.Double(),
                        type_=sa.Float())
        op.alter_column('track_points', 'speed',
                        existing_type=sa.Double(),
                        type_=sa.Float())
        op.alter_column('track_points', 'bearing',
                        existing_type=sa.Double(),
                        type_=sa.Float())
