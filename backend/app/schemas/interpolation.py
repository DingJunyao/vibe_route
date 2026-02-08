"""
轨迹插值相关的 Pydantic schemas
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_serializer


class ControlPointHandle(BaseModel):
    """控制点手柄"""
    dx: float = Field(..., description="X 方向偏移量（经度）")
    dy: float = Field(..., description="Y 方向偏移量（纬度）")


class ControlPoint(BaseModel):
    """贝塞尔曲线控制点"""
    lng: float = Field(..., description="经度", ge=-180, le=180)
    lat: float = Field(..., description="纬度", ge=-90, le=90)
    in_handle: ControlPointHandle = Field(..., description="进入手柄")
    out_handle: ControlPointHandle = Field(..., description="离开手柄")
    handles_locked: bool = Field(default=True, description="手柄是否锁定")


class AvailableSegment(BaseModel):
    """可插值区段"""
    start_index: int
    end_index: int
    interval_seconds: float
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @field_serializer('start_time', 'end_time')
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        """序列化 datetime 为带时区的 ISO 格式字符串"""
        if dt is None:
            return None
        return dt.isoformat() + '+00:00'


class InterpolatedPoint(BaseModel):
    """插值点数据"""
    point_index: int
    time: datetime
    latitude: float
    longitude: float
    latitude_gcj02: float
    longitude_gcj02: float
    latitude_bd09: float
    longitude_bd09: float
    speed: float
    course: float
    elevation: Optional[float] = None

    @field_serializer('time')
    def serialize_datetime(self, dt: datetime) -> str:
        """序列化 datetime 为带时区的 ISO 格式字符串"""
        return dt.isoformat() + '+00:00'


class InterpolationCreateRequest(BaseModel):
    """创建插值请求"""
    start_point_index: int = Field(..., ge=0, description="起点索引")
    end_point_index: int = Field(..., ge=0, description="终点索引")
    control_points: List[ControlPoint] = Field(default_factory=list, description="控制点列表")
    interpolation_interval_seconds: float = Field(default=1.0, ge=0.1, le=60, description="插值间隔（秒）")
    algorithm: str = Field(default="cubic_bezier", description="插值算法类型")


class InterpolationUpdateRequest(BaseModel):
    """更新插值请求"""
    control_points: List[ControlPoint] = Field(..., description="新的控制点列表")
    interpolation_interval_seconds: Optional[float] = Field(None, ge=0.1, le=60, description="新的插值间隔")


class InterpolationResponse(BaseModel):
    """插值响应"""
    id: int
    track_id: int
    start_point_index: int
    end_point_index: int
    point_count: int
    control_points: List[ControlPoint]
    interpolation_interval_seconds: int
    algorithm: str
    created_at: datetime

    @field_serializer('created_at')
    def serialize_datetime(self, dt: datetime) -> str:
        """序列化 datetime 为带时区的 ISO 格式字符串"""
        return dt.isoformat() + '+00:00'


class InterpolationPreviewRequest(BaseModel):
    """插值预览请求"""
    track_id: int
    start_point_index: int
    end_point_index: int
    control_points: List[ControlPoint] = Field(default_factory=list)
    interpolation_interval_seconds: float = Field(default=1.0, ge=0.1, le=60)


class InterpolationPreviewResponse(BaseModel):
    """插值预览响应"""
    points: List[InterpolatedPoint]
    total_count: int
    start_time: datetime
    end_time: datetime

    @field_serializer('start_time', 'end_time')
    def serialize_datetime(self, dt: datetime) -> str:
        """序列化 datetime 为带时区的 ISO 格式字符串"""
        return dt.isoformat() + '+00:00'
