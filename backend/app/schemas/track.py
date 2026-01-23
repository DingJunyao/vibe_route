"""
轨迹相关的 Pydantic schemas
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_serializer


class CoordinateSystem(BaseModel):
    """坐标系枚举"""
    wgs84: str = "wgs84"
    gcj02: str = "gcj02"
    bd09: str = "bd09"


class TrackCreate(BaseModel):
    """轨迹创建 schema（上传时）"""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    original_crs: str = Field(default="wgs84", pattern="^(wgs84|gcj02|bd09)$")
    convert_to: Optional[str] = Field(None, pattern="^(wgs84|gcj02|bd09)$")
    fill_area_info: bool = True
    fill_road_info: bool = True


class TrackUpdate(BaseModel):
    """轨迹更新 schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None


class TrackResponse(BaseModel):
    """轨迹响应 schema"""
    id: int
    user_id: int
    name: str
    description: Optional[str]
    original_filename: str
    original_crs: str
    distance: float
    duration: int
    elevation_gain: float
    elevation_loss: float
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    has_area_info: bool
    has_road_info: bool
    created_at: datetime
    updated_at: datetime

    @field_serializer('start_time', 'end_time', 'created_at', 'updated_at')
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        """序列化 datetime 为带时区的 ISO 格式字符串"""
        if dt is None:
            return None
        # 返回 UTC 时间并添加时区后缀
        return dt.isoformat() + '+00:00'

    class Config:
        from_attributes = True


class TrackListResponse(BaseModel):
    """轨迹列表响应 schema"""
    total: int
    page: int
    page_size: int
    items: List[TrackResponse]


class TrackPointResponse(BaseModel):
    """轨迹点响应 schema"""
    id: int
    point_index: int
    time: Optional[datetime]
    latitude_wgs84: float
    longitude_wgs84: float
    latitude_gcj02: Optional[float]
    longitude_gcj02: Optional[float]
    latitude_bd09: Optional[float]
    longitude_bd09: Optional[float]
    elevation: Optional[float]
    speed: Optional[float]
    province: Optional[str]
    city: Optional[str]
    district: Optional[str]
    road_name: Optional[str]
    road_number: Optional[str]

    @field_serializer('time')
    def serialize_time(self, dt: Optional[datetime]) -> Optional[str]:
        """序列化 datetime 为带时区的 ISO 格式字符串"""
        if dt is None:
            return None
        return dt.isoformat() + '+00:00'

    class Config:
        from_attributes = True


class TrackStatsResponse(BaseModel):
    """轨迹统计汇总响应 schema"""
    total_tracks: Optional[int] = 0
    total_distance: Optional[float] = 0  # 米
    total_duration: Optional[int] = 0  # 秒
    total_elevation_gain: Optional[float] = 0  # 米
    total_elevation_loss: Optional[float] = 0  # 米


class RegionNode(BaseModel):
    """区域树节点"""
    id: str
    name: str
    type: str  # province, city, district, road
    point_count: int = 0
    distance: float = 0  # 路径长度（米）
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    road_number: Optional[str] = None
    children: List['RegionNode'] = []

    @field_serializer('start_time', 'end_time')
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        """序列化 datetime 为带时区的 ISO 格式字符串"""
        if dt is None:
            return None
        return dt.isoformat() + '+00:00'


# 更新前向引用
RegionNode.model_rebuild()


class RegionTreeResponse(BaseModel):
    """区域树响应 schema"""
    track_id: int
    regions: List[RegionNode]
    stats: dict  # 各级区域数量统计