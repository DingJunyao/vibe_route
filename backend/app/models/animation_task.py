# backend/app/models/animation_task.py

from datetime import datetime
from sqlalchemy import Column, String, Float, Text, Integer
from sqlalchemy.orm import relationship

from .base import AuditMixin


class AnimationExportTask(AuditMixin):
    """动画导出任务模型"""
    __tablename__ = 'animation_export_tasks'

    id = Column(String(36), primary_key=True)
    track_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)

    status = Column(String(20), default='pending')  # pending, processing, completed, failed, cancelled
    progress = Column(Float, default=0.0)

    download_url = Column(Text, nullable=True)
    error = Column(Text, nullable=True)

    # 关联
    track = relationship("Track")
    user = relationship("User")
