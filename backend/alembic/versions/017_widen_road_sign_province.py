"""widen road_sign_cache.province for Indonesia support

Revision ID: 017_widen_road_sign_province
Revises: 016_add_multilanguage_region
Create Date: 2026-09-10

显式承载 road_sign_cache.province 由 String(10) 放宽到 String(100)。

背景：016 里这条放宽 DDL 是后补进去的，而已 stamped 到 016 的环境
（版本号判重，重跑 016 是 no-op）永远拿不到它，模型侧却已是 String(100)。
单独占一个迁移号，才能让已应用 016 的环境真正拿到这条变更。
幂等：全新环境 016 已放宽，本迁移再放宽一次是 no-op。

兼容 SQLite / MySQL / PostgreSQL。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '017_widen_road_sign_province'
down_revision = '016_add_multilanguage_region'
branch_labels = None
depends_on = None


def upgrade():
    """放宽 province 列宽：region='id' 时承载印尼语省名（最长 29 字符）"""
    # 用 batch_alter_table：SQLite 不支持直接改列类型，batch 模式会重建表；
    # MySQL / PostgreSQL 下退化为普通 ALTER COLUMN。
    with op.batch_alter_table('road_sign_cache') as batch_op:
        batch_op.alter_column(
            'province', type_=sa.String(100), existing_type=sa.String(10),
            existing_nullable=True,
        )


def downgrade():
    """回滚：恢复 province 为 String(10)"""
    with op.batch_alter_table('road_sign_cache') as batch_op:
        batch_op.alter_column(
            'province', type_=sa.String(10), existing_type=sa.String(100),
            existing_nullable=True,
        )
