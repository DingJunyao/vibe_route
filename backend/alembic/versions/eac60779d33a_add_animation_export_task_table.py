"""add_animation_export_task_table

Revision ID: eac60779d33a
Revises: 015_add_overlay_templates
Create Date: 2026-02-14 15:01:40.588980

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eac60779d33a'
down_revision: Union[str, None] = '015_add_overlay_templates'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'animation_export_tasks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('track_id', sa.Integer(), nullable=False, index=True),
        sa.Column('user_id', sa.Integer(), nullable=False, index=True),
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('progress', sa.Float(), default=0.0),
        sa.Column('download_url', sa.Text(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('is_valid', sa.Boolean(), default=True, nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_animation_export_tasks_user_id'),
        sa.ForeignKeyConstraint(['track_id'], ['tracks.id'], name='fk_animation_export_tasks_track_id'),
    )
    op.create_index('ix_animation_export_tasks_status', 'animation_export_tasks', ['status'])
    op.create_index('ix_animation_export_tasks_created_at', 'animation_export_tasks', ['created_at'])


def downgrade() -> None:
    op.drop_table('animation_export_tasks')
