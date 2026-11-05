"""add email_templates table and user notification prefs; merge 017/018

Revision ID: 019_add_email_templates_and_notify_prefs
Revises: ('017_widen_road_sign_province', '018_add_animation_task_times')
Create Date: 2026-11-05

邮件通知系统：
- 新建 email_templates 表（录屏完成/失败通知模板，管理员可编辑）
- user_configs 增加 notify_recording_completed / notify_recording_failed 用户级开关
- 同时合并 017 与 018 的分叉（两者 down_revision 均为 eac60779d33a），收敛为单 head
兼容 SQLite / MySQL / PostgreSQL（与 PostGIS 无关）。幂等：表/列已存在时跳过。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '019_add_email_templates_and_notify_prefs'
down_revision = ('017_widen_road_sign_province', '018_add_animation_task_times')
branch_labels = None
depends_on = None


def _existing_columns(inspector, table):
    return {col['name'] for col in inspector.get_columns(table)}


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = inspector.get_table_names()

    # 1. 新建 email_templates 表
    if 'email_templates' not in table_names:
        op.create_table(
            'email_templates',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('template_key', sa.String(50), nullable=False),
            sa.Column('subject', sa.String(200), nullable=False),
            sa.Column('body', sa.Text(), nullable=False),
            sa.Column('is_html', sa.Boolean(), nullable=False, server_default=sa.false()),
            # AuditMixin
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('created_by', sa.Integer(), nullable=True),
            sa.Column('updated_by', sa.Integer(), nullable=True),
            sa.Column('is_valid', sa.Boolean(), nullable=False, server_default=sa.true()),
        )
        op.create_index('ix_email_templates_template_key', 'email_templates', ['template_key'], unique=True)

    # 2. user_configs 增加通知开关列
    if 'user_configs' in table_names:
        columns = _existing_columns(inspector, 'user_configs')
        if 'notify_recording_completed' not in columns:
            op.add_column(
                'user_configs',
                sa.Column('notify_recording_completed', sa.Boolean(), nullable=False, server_default=sa.false()),
            )
        if 'notify_recording_failed' not in columns:
            op.add_column(
                'user_configs',
                sa.Column('notify_recording_failed', sa.Boolean(), nullable=False, server_default=sa.false()),
            )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = inspector.get_table_names()

    if 'user_configs' in table_names:
        columns = _existing_columns(inspector, 'user_configs')
        if 'notify_recording_failed' in columns:
            op.drop_column('user_configs', 'notify_recording_failed')
        if 'notify_recording_completed' in columns:
            op.drop_column('user_configs', 'notify_recording_completed')

    if 'email_templates' in table_names:
        op.drop_index('ix_email_templates_template_key', table_name='email_templates')
        op.drop_table('email_templates')
