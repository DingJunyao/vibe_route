"""
轨迹插值模型
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import AuditMixin


class TrackInterpolation(Base, AuditMixin):
    """轨迹插值配置表"""

    __tablename__ = "track_interpolations"

    id = Column(Integer, primary_key=True, index=True)
    track_id = Column(Integer, ForeignKey("tracks.id"), nullable=False, index=True)
    start_point_index = Column(Integer, nullable=False, comment="起点索引")
    end_point_index = Column(Integer, nullable=False, comment="终点索引")
    path_geometry = Column(Text, nullable=False, comment="控制点数据(JSON格式)")
    interpolation_interval_seconds = Column(Integer, nullable=False, default=1, comment="插值间隔(秒)")
    point_count = Column(Integer, nullable=False, comment="插入的点数")
    algorithm = Column(String(50), nullable=False, default="cubic_bezier", comment="插值算法")

    # 关系
    track = relationship("Track", back_populates="interpolations")
    interpolated_points = relationship(
        "TrackPoint",
        foreign_keys="TrackPoint.interpolation_id",
        back_populates="interpolation_source"
    )

    def __repr__(self):
        return f"<TrackInterpolation(id={self.id}, track_id={self.track_id}, points={self.point_count})>"
