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
    latitude: float
    longitude: float
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
