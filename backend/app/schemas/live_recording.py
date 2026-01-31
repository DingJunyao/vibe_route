"""
实时记录相关的 Pydantic schemas
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_serializer


class CreateRecordingRequest(BaseModel):
    """创建记录请求 schema"""
    name: str = Field(..., min_length=1, max_length=200, description="记录名称")
    description: Optional[str] = Field(None, max_length=1000, description="描述")
    fill_geocoding: Optional[bool] = Field(False, description="上传点时是否自动填充地理信息")


class LiveRecordingResponse(BaseModel):
    """实时记录响应 schema"""
    id: int
    name: str
    description: Optional[str]
    token: str
    status: str
    track_count: int
    last_upload_at: Optional[datetime]
    last_point_time: Optional[datetime] = Field(None, description="最近一次轨迹点的 GPS 时间")
    last_point_created_at: Optional[datetime] = Field(None, description="最近一次轨迹点的服务器接收时间")
    upload_url: str
    created_at: datetime
    fill_geocoding: bool = False

    @field_serializer('last_upload_at', 'last_point_time', 'last_point_created_at', 'created_at')
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        """序列化 datetime 为带时区的 ISO 格式字符串"""
        if dt is None:
            return None
        return dt.isoformat() + '+00:00'

    class Config:
        from_attributes = True


class RecordingStatusResponse(BaseModel):
    """记录状态响应 schema"""
    id: int
    name: str
    description: Optional[str]
    status: str
    track_count: int
    last_upload_at: Optional[datetime]
    last_point_time: Optional[datetime] = Field(None, description="最近一次轨迹点的 GPS 时间")
    last_point_created_at: Optional[datetime] = Field(None, description="最近一次轨迹点的服务器接收时间")
    created_at: datetime
    tracks: list[dict] = []

    @field_serializer('last_upload_at', 'last_point_time', 'last_point_created_at', 'created_at')
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        """序列化 datetime 为带时区的 ISO 格式字符串"""
        if dt is None:
            return None
        return dt.isoformat() + '+00:00'

    class Config:
        from_attributes = True


class LogPointResponse(BaseModel):
    """日志点上传响应 schema"""
    success: bool
    point_id: int
    track_id: int
    recording_id: int
    point_index: int
    calculated_speed: Optional[float] = None
    calculated_bearing: Optional[float] = None
    distance_from_prev: Optional[float] = None
