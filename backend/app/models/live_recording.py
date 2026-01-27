"""
实时记录模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import AuditMixin


class LiveRecording(Base, AuditMixin):
    """实时记录表"""

    __tablename__ = "live_recordings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token = Column(String(64), nullable=False, unique=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="active")  # active, ended
    track_count = Column(Integer, default=0)
    last_upload_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    current_track_id = Column(Integer, ForeignKey("tracks.id"), nullable=True)
    fill_geocoding = Column(Boolean, default=False)  # 上传点时是否自动填充地理信息

    # 关系
    user = relationship("User", back_populates="live_recordings")
    current_track = relationship("Track", foreign_keys=[current_track_id])

    def __repr__(self):
        return f"<LiveRecording(id={self.id}, name='{self.name}', status='{self.status}')>"
