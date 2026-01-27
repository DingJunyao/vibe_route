"""fix road_sign_cache id type

Revision ID: 004_fix_road_sign_cache_id
Revises: 003_add_memo_to_track_points
Create Date: 2026-01-26

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004_fix_road_sign_cache_id'
down_revision = '003_add_memo'
branch_labels = None
depends_on = None


def upgrade():
    # 先删除旧表
    op.drop_table('road_sign_cache')

    # 创建新表，使用 String(32) 作为 id 类型
    op.create_table(
        'road_sign_cache',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('province', sa.String(10), nullable=True),
        sa.Column('name', sa.String(100), nullable=True),
        sa.Column('svg_path', sa.String(500), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('is_valid', sa.Boolean(), nullable=False, server_default='1')
    )

    # 创建索引
    op.create_index(op.f('ix_road_sign_cache_code', 'road_sign_cache', ['code']))
    op.create_index(op.f('ix_road_sign_cache_is_valid', 'road_sign_cache', ['is_valid']))
    op.create_index(op.f('ix_road_sign_cache_created_by', 'road_sign_cache', ['created_by']))
    op.create_index(op.f('ix_road_sign_cache_updated_by', 'road_sign_cache', ['updated_by']))


def downgrade():
    # 删除新表
    op.drop_table('road_sign_cache')

    # 恢复旧表（使用 Integer id）
    op.create_table(
        'road_sign_cache',
        sa.Column('id', sa.Integer(), autoincrement=False, primary_key=True),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('province', sa.String(10), nullable=True),
        sa.Column('name', sa.String(100), nullable=True),
        sa.Column('svg_path', sa.String(500), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('is_valid', sa.Boolean(), nullable=False, server_default='1')
    )

    # 创建索引
    op.create_index(op.f('ix_road_sign_cache_code', 'road_sign_cache', ['code']))
    op.create_index(op.f('ix_road_sign_cache_is_valid', 'road_sign_cache', ['is_valid']))
    op.create_index(op.f('ix_road_sign_cache_created_by', 'road_sign_cache', ['created_by']))
    op.create_index(op.f('ix_road_sign_cache_updated_by', 'road_sign_cache', ['updated_by']))
