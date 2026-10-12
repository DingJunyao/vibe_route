"""add task columns to animation_export_tasks for queueing

Revision ID: 018_add_animation_task_times
Revises: eac60779d33a
Create Date: 2026-10-12

录屏任务化：
- started_at / finished_at：保留期清理按 finished_at 起算，任务页展示耗时
- params：导出参数 JSON（排队后才启动，启动时才读取）
- auth_token：录制页登录 token（启动后即清空，减少 DB 凭据存留）
兼容 SQLite / MySQL / PostgreSQL（与 PostGIS 无关）。幂等：列已存在时跳过。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '018_add_animation_task_times'
down_revision = 'eac60779d33a'
branch_labels = None
depends_on = None


def _existing_columns(inspector, table):
    return {col['name'] for col in inspector.get_columns(table)}


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'animation_export_tasks' not in inspector.get_table_names():
        return

    columns = _existing_columns(inspector, 'animation_export_tasks')
    if 'started_at' not in columns:
        op.add_column(
            'animation_export_tasks',
            sa.Column('started_at', sa.DateTime(), nullable=True),
        )
    if 'finished_at' not in columns:
        op.add_column(
            'animation_export_tasks',
            sa.Column('finished_at', sa.DateTime(), nullable=True),
        )
    if 'params' not in columns:
        op.add_column(
            'animation_export_tasks',
            sa.Column('params', sa.Text(), nullable=True),
        )
    if 'auth_token' not in columns:
        op.add_column(
            'animation_export_tasks',
            sa.Column('auth_token', sa.Text(), nullable=True),
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'animation_export_tasks' not in inspector.get_table_names():
        return

    columns = _existing_columns(inspector, 'animation_export_tasks')
    if 'auth_token' in columns:
        op.drop_column('animation_export_tasks', 'auth_token')
    if 'params' in columns:
        op.drop_column('animation_export_tasks', 'params')
    if 'finished_at' in columns:
        op.drop_column('animation_export_tasks', 'finished_at')
    if 'started_at' in columns:
        op.drop_column('animation_export_tasks', 'started_at')
