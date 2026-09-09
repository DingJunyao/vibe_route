"""add multilanguage and region columns for Indonesia support

Revision ID: 016_add_multilanguage_region
Revises: eac60779d33a
Create Date: 2026-09-09

兼容 SQLite / MySQL / PostgreSQL。
tracks/track_points 增加 region 默认 'cn'；track_points 增加 *_id 印尼语列；
road_sign_cache 增加 region。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '016_add_multilanguage_region'
down_revision = 'eac60779d33a'
branch_labels = None
depends_on = None


def _add_column_if_missing(table: str, column_name: str, column: sa.Column) -> None:
    """检查列不存在再添加（数据库可能已手动建过）"""
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {c['name'] for c in inspector.get_columns(table)}
    if column_name not in columns:
        op.add_column(table, column)


def upgrade():
    """添加地区与多语言列"""
    # tracks.region
    _add_column_if_missing(
        'tracks', 'region',
        sa.Column('region', sa.String(10), nullable=False,
                  server_default='cn', comment='地区: cn=中国, id=印尼')
    )
    # track_points.region + *_id
    _add_column_if_missing(
        'track_points', 'region',
        sa.Column('region', sa.String(10), nullable=False,
                  server_default='cn', comment='地区: cn=中国, id=印尼')
    )
    for col in ('province_id', 'city_id', 'district_id'):
        _add_column_if_missing(
            'track_points', col,
            sa.Column(col, sa.String(100), nullable=True)
        )
    _add_column_if_missing(
        'track_points', 'road_name_id',
        sa.Column('road_name_id', sa.String(200), nullable=True)
    )
    # road_sign_cache.region
    _add_column_if_missing(
        'road_sign_cache', 'region',
        sa.Column('region', sa.String(10), nullable=False,
                  server_default='cn', comment='地区: cn=中国, id=印尼')
    )


def downgrade():
    """回滚：删除新增列（列存在才删）"""
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)

    def drop_if_exists(table: str, column_name: str) -> None:
        columns = {c['name'] for c in inspector.get_columns(table)}
        if column_name in columns:
            op.drop_column(table, column_name)

    for col in ('road_name_id', 'province_id', 'city_id', 'district_id'):
        drop_if_exists('track_points', col)
    drop_if_exists('track_points', 'region')
    drop_if_exists('tracks', 'region')
    drop_if_exists('road_sign_cache', 'region')
