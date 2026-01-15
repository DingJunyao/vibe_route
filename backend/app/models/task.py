"""
任务相关模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import AuditMixin


class Task(Base, AuditMixin):
    """异步任务表"""

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(String(20), nullable=False)  # overlay_generate 等
    status = Column(String(20), nullable=False, default="pending")  # pending, running, completed, failed
    progress = Column(Integer, default=0)  # 0-100
    result_path = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)

    # 关系
    user = relationship("User", back_populates="tasks")

    @property
    def is_finished(self) -> bool:
        """任务是否已完成（成功或失败）"""
        return self.status in ("completed", "failed")

    def __repr__(self):
        return f"<Task(id={self.id}, type='{self.type}', status='{self.status}')>"
