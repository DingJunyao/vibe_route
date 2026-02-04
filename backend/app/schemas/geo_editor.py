"""
地理信息编辑器相关的 Pydantic schemas
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_serializer


class TrackPointGeoData(BaseModel):
    """轨迹点数据（仅包含编辑所需字段）"""
    point_index: int
    time: Optional[datetime]
    created_at: Optional[datetime]
    latitude: float  # WGS84 纬度
    longitude: float  # WGS84 经度
    latitude_wgs84: float  # WGS84 纬度
    longitude_wgs84: float  # WGS84 经度
    latitude_gcj02: Optional[float] = None  # GCJ02 纬度（高德、腾讯）
    longitude_gcj02: Optional[float] = None  # GCJ02 经度
    latitude_bd09: Optional[float] = None  # BD09 纬度（百度）
    longitude_bd09: Optional[float] = None  # BD09 经度
    elevation: Optional[float] = None  # 海拔（米）
    speed: Optional[float] = None  # 速度（m/s）
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    province_en: Optional[str] = None
    city_en: Optional[str] = None
    district_en: Optional[str] = None
    road_number: Optional[str] = None
    road_name: Optional[str] = None
    road_name_en: Optional[str] = None

    @field_serializer('time', 'created_at')
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        if dt is None:
            return None
        return dt.isoformat() + '+00:00'

    class Config:
        from_attributes = True


class GeoSegmentUpdate(BaseModel):
    """单个段落的更新数据"""
    track_type: str = Field(..., pattern="^(province|city|district|road_number|road_name)$")
    start_index: int = Field(..., ge=0)
    end_index: int = Field(..., ge=0)
    value: Optional[str] = None
    value_en: Optional[str] = None


class GeoSegmentsUpdateRequest(BaseModel):
    """批量更新请求"""
    segments: List[GeoSegmentUpdate]


class GeoEditorDataResponse(BaseModel):
    """编辑器初始化数据"""
    track_id: int
    name: str
    original_crs: str
    total_duration: int  # 毫秒
    point_count: int
    points: List[TrackPointGeoData]

    @field_serializer('points')
    def serialize_points(self, points: List[TrackPointGeoData]) -> List[TrackPointGeoData]:
        # 限制返回点数，避免响应过大
        return points[:5000]
