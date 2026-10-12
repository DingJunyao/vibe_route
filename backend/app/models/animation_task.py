# backend/app/models/animation_task.py

from datetime import datetime
from sqlalchemy import Column, String, Float, Text, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base
from .base import AuditMixin


class AnimationExportTask(Base, AuditMixin):
    """动画导出任务模型"""
    __tablename__ = 'animation_export_tasks'

    id = Column(String(36), primary_key=True)
    track_id = Column(Integer, ForeignKey('tracks.id'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)

    status = Column(String(20), default='pending')  # pending, processing, completed, failed, cancelled, expired
    progress = Column(Float, default=0.0)

    started_at = Column(DateTime, nullable=True)   # 开始录制时间（进入 processing）
    finished_at = Column(DateTime, nullable=True)  # 结束时间（完成/失败/取消，保留期从此起算）

    params = Column(Text, nullable=True)      # 导出参数 JSON（duration_ms + request），排队启动时使用
    auth_token = Column(Text, nullable=True)  # 用户 JWT（排队启动时注入录制页），启动后即清空

    download_url = Column(Text, nullable=True)
    error = Column(Text, nullable=True)

    # 关联
    track = relationship("Track")
    user = relationship("User")
