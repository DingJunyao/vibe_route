"""
轨迹相关模型
"""
from datetime import datetime
from sqlalchemy import (
    Boolean, Column, Integer, String, Float, Text, DateTime, ForeignKey, BigInteger,
    Sequence, Double,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import AuditMixin


class Track(Base, AuditMixin):
    """轨迹表"""

    __tablename__ = "tracks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    original_filename = Column(String(255), nullable=False)
    original_crs = Column(String(10), nullable=False)  # wgs84, gcj02, bd09

    # 统计信息
    distance = Column(Float, default=0)  # 长度（米）
    duration = Column(Integer, default=0)  # 时长（秒）
    elevation_gain = Column(Float, default=0)  # 爬升（米）
    elevation_loss = Column(Float, default=0)  # 下降（米）

    # 时间范围
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)

    # 处理状态
    has_area_info = Column(Boolean, default=False)
    has_road_info = Column(Boolean, default=False)

    # 标记是否为实时记录的轨迹
    is_live_recording = Column(Boolean, default=False, nullable=False)

    # 关系
    user = relationship("User", back_populates="tracks")
    points = relationship("TrackPoint", back_populates="track", cascade="all, delete-orphan")
    live_recordings = relationship("LiveRecording", foreign_keys="LiveRecording.current_track_id")

    def __repr__(self):
        return f"<Track(id={self.id}, name='{self.name}', user_id={self.user_id})>"


class TrackPoint(Base, AuditMixin):
    """轨迹点表"""

    __tablename__ = "track_points"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    track_id = Column(Integer, ForeignKey("tracks.id"), nullable=False, index=True)
    point_index = Column(Integer, nullable=False)  # 点序号

    # 时间
    time = Column(DateTime, nullable=True)

    # 三种坐标系（使用 Double 确保经纬度精度）
    latitude_wgs84 = Column(Double, nullable=False)
    longitude_wgs84 = Column(Double, nullable=False)
    latitude_gcj02 = Column(Double, nullable=True)
    longitude_gcj02 = Column(Double, nullable=True)
    latitude_bd09 = Column(Double, nullable=True)
    longitude_bd09 = Column(Double, nullable=True)

    # 数据
    elevation = Column(Double, nullable=True)  # 海拔（米）
    speed = Column(Double, nullable=True)  # 速度（m/s）
    bearing = Column(Double, nullable=True)  # 方位角（度），范围 [0, 360)

    # 行政区划信息
    province = Column(String(50), nullable=True)
    city = Column(String(50), nullable=True)
    district = Column(String(50), nullable=True)
    province_en = Column(String(100), nullable=True)
    city_en = Column(String(100), nullable=True)
    district_en = Column(String(100), nullable=True)

    # 道路信息
    road_name = Column(String(200), nullable=True)
    road_number = Column(String(50), nullable=True)
    road_name_en = Column(String(200), nullable=True)

    # 备注
    memo = Column(Text, nullable=True)

    # 关系
    track = relationship("Track", back_populates="points")

    def get_coords(self, crs: str = "wgs84") -> tuple[float, float]:
        """
        根据坐标系获取坐标

        Args:
            crs: 坐标系 (wgs84, gcj02, bd09)

        Returns:
            (latitude, longitude) 元组
        """
        if crs == "wgs84":
            return self.latitude_wgs84, self.longitude_wgs84
        elif crs == "gcj02":
            # 如果 gcj02 坐标为空，返回 wgs84 坐标
            if self.latitude_gcj02 is None or self.longitude_gcj02 is None:
                return self.latitude_wgs84, self.longitude_wgs84
            return self.latitude_gcj02, self.longitude_gcj02
        elif crs == "bd09":
            # 如果 bd09 坐标为空，返回 wgs84 坐标
            if self.latitude_bd09 is None or self.longitude_bd09 is None:
                return self.latitude_wgs84, self.longitude_wgs84
            return self.latitude_bd09, self.longitude_bd09
        # 默认返回 wgs84
        return self.latitude_wgs84, self.longitude_wgs84

    def __repr__(self):
        return f"<TrackPoint(id={self.id}, track_id={self.track_id}, index={self.point_index})>"


class TrackPointSpatial(Base):
    """
    PostGIS 空间扩展表（可选）

    仅用于 PostgreSQL + PostGIS 环境。
    为轨迹点添加 geometry 字段以支持空间索引加速查询。

    注意：此表为可选，不影响其他数据库的使用。
    """

    __tablename__ = "track_points_spatial"

    point_id = Column(
        Integer,
        ForeignKey("track_points.id", ondelete="CASCADE"),
        primary_key=True
    )

    # 注意：geom 字段仅在迁移脚本中创建（使用 Geography 类型）
    # 这里不定义 geom 列，因为 SQLAlchemy-GeoAlchemy2 是可选依赖
    # 迁移脚本会使用原生 SQL 创建：geom GEOGRAPHY(POINT, 4326)

    def __repr__(self):
        return f"<TrackPointSpatial(point_id={self.point_id})>"
