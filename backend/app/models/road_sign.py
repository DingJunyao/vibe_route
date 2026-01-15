"""
道路标志缓存模型
"""
from sqlalchemy import Column, Integer, String

from app.core.database import Base
from app.models.base import AuditMixin


class RoadSignCache(Base, AuditMixin):
    """道路标志缓存表"""

    __tablename__ = "road_sign_cache"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), index=True, nullable=False)
    province = Column(String(10), nullable=True)  # 省份（高速用）
    name = Column(String(100), nullable=True)  # 道路名称
    svg_path = Column(String(500), nullable=False)  # SVG 文件路径

    def __repr__(self):
        return f"<RoadSignCache(code='{self.code}', province='{self.province}')>"
