"""change track points to double for precision

Revision ID: 007_change_track_points_to_double
Revises: 006_add_fill_geocoding_to_live_recordings
Create Date: 2026-01-30

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007_change_track_points_to_double'
down_revision = '006_add_fill_geocoding_to_live_recordings'
branch_labels = None
depends_on = None


def upgrade():
    # 将 track_points 表中的浮点列改为 DOUBLE 类型以提高精度
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
    # 回滚：将 DOUBLE 改回 FLOAT
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
