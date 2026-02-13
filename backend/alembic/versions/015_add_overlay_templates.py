"""add overlay_templates and fonts tables

Revision ID: 015_add_overlay_templates
Revises: 014_add_interpolations
Create Date: 2026-02-10

添加覆盖层模板和字体管理功能相关表结构。
兼容 SQLite / MySQL / PostgreSQL。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '015_add_overlay_templates'
down_revision = '014_add_interpolations'
branch_labels = None
depends_on = None


def upgrade():
    """
    创建覆盖层模板表和字体表
    """
    # 检查表是否已存在（可能之前手动创建过）
    from sqlalchemy import inspect
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()

    # 创建 overlay_templates 表
    if 'overlay_templates' not in tables:
        op.create_table(
            'overlay_templates',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('created_by', sa.Integer(), nullable=True),
            sa.Column('updated_by', sa.Integer(), nullable=True),
            sa.Column('is_valid', sa.Boolean(), nullable=False, server_default='1'),

            sa.Column('name', sa.String(length=100), nullable=False, comment='模板名称'),
            sa.Column('description', sa.Text(), nullable=True, comment='模板描述'),
            sa.Column('config', sa.JSON(), nullable=False, comment='模板配置（JSON）'),
            sa.Column('user_id', sa.Integer(), nullable=True, comment='所有者ID，NULL表示系统模板'),
            sa.Column('is_public', sa.Boolean(), nullable=False, server_default='0', comment='是否公开'),
            sa.Column('is_system', sa.Boolean(), nullable=False, server_default='0', comment='是否系统预设模板'),

            sa.PrimaryKeyConstraint('id')
        )

    # 创建 overlay_templates 索引
    existing_indexes = [idx['name'] for idx in inspector.get_indexes('overlay_templates')] if 'overlay_templates' in tables else []
    if 'ix_overlay_templates_is_valid' not in existing_indexes:
        op.create_index('ix_overlay_templates_is_valid', 'overlay_templates', ['is_valid'])
    if 'ix_overlay_templates_user_id' not in existing_indexes:
        op.create_index('ix_overlay_templates_user_id', 'overlay_templates', ['user_id'])
    if 'ix_overlay_templates_is_system' not in existing_indexes:
        op.create_index('ix_overlay_templates_is_system', 'overlay_templates', ['is_system'])

    # 创建 fonts 表
    if 'fonts' not in tables:
        op.create_table(
            'fonts',
            sa.Column('id', sa.String(length=50), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('created_by', sa.Integer(), nullable=True),
            sa.Column('updated_by', sa.Integer(), nullable=True),
            sa.Column('is_valid', sa.Boolean(), nullable=False, server_default='1'),

            sa.Column('name', sa.String(length=100), nullable=False, comment='字体显示名称'),
            sa.Column('filename', sa.String(length=255), nullable=False, comment='字体文件名'),
            sa.Column('type', sa.String(length=10), nullable=False, comment='字体类型：system/admin/user'),
            sa.Column('owner_id', sa.Integer(), nullable=True, comment='所有者ID（user类型时）'),
            sa.Column('file_path', sa.String(length=500), nullable=False, comment='字体文件路径'),
            sa.Column('file_size', sa.Integer(), nullable=False, comment='文件大小（字节）'),
            sa.Column('family', sa.String(length=100), nullable=True, comment='字体家族'),
            sa.Column('style', sa.String(length=20), nullable=False, server_default='normal', comment='字体样式'),
            sa.Column('weight', sa.Integer(), nullable=False, server_default=400, comment='字体粗细'),
            sa.Column('supports_latin', sa.Boolean(), nullable=False, server_default='1', comment='支持拉丁字符'),
            sa.Column('supports_chinese', sa.Boolean(), nullable=False, server_default='0', comment='支持中文字符'),
            sa.Column('supports_japanese', sa.Boolean(), nullable=False, server_default='0', comment='支持日文字符'),
            sa.Column('supports_korean', sa.Boolean(), nullable=False, server_default='0', comment='支持韩文字符'),
            sa.Column('preview_url', sa.String(length=500), nullable=True, comment='预览图URL'),

            sa.PrimaryKeyConstraint('id')
        )

    # 创建 fonts 索引
    existing_indexes = [idx['name'] for idx in inspector.get_indexes('fonts')] if 'fonts' in tables else []
    if 'ix_fonts_is_valid' not in existing_indexes:
        op.create_index('ix_fonts_is_valid', 'fonts', ['is_valid'])
    if 'ix_fonts_owner_id' not in existing_indexes:
        op.create_index('ix_fonts_owner_id', 'fonts', ['owner_id'])

    # 创建外键（SQLite 不支持外键，会忽略）
    try:
        op.create_foreign_key('fk_overlay_templates_user_id', 'overlay_templates', 'users', ['user_id'], ['id'])
        op.create_foreign_key('fk_fonts_owner_id', 'fonts', 'users', ['owner_id'], ['id'])
    except Exception:
        # SQLite 不支持外键，忽略错误
        pass


def downgrade():
    """
    回滚迁移
    """
    # 删除外键
    try:
        op.drop_constraint('fk_fonts_owner_id', 'fonts', type_='foreignkey')
        op.drop_constraint('fk_overlay_templates_user_id', 'overlay_templates', type_='foreignkey')
    except Exception:
        pass

    # 删除索引
    try:
        op.drop_index('ix_fonts_owner_id', 'fonts')
    except Exception:
        pass
    try:
        op.drop_index('ix_fonts_is_valid', 'fonts')
    except Exception:
        pass
    try:
        op.drop_index('ix_overlay_templates_is_system', 'overlay_templates')
    except Exception:
        pass
    try:
        op.drop_index('ix_overlay_templates_user_id', 'overlay_templates')
    except Exception:
        pass
    try:
        op.drop_index('ix_overlay_templates_is_valid', 'overlay_templates')
    except Exception:
        pass

    # 删除表
    try:
        op.drop_table('fonts')
    except Exception:
        pass
    try:
        op.drop_table('overlay_templates')
    except Exception:
        pass
