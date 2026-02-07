"""
用户配置相关的 Pydantic schemas
"""
from datetime import datetime
from typing import Optional, Dict
from pydantic import BaseModel, Field, field_serializer

from app.schemas.config import MapLayerConfig


class UserConfigResponse(BaseModel):
    """用户配置响应 schema"""
    id: int
    user_id: int
    map_provider: Optional[str] = None
    map_layers: Optional[Dict[str, MapLayerConfig]] = None
    created_at: datetime
    updated_at: datetime

    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, dt: datetime) -> str:
        """序列化 datetime 为带时区的 ISO 格式字符串（UTC）"""
        return dt.isoformat() + '+00:00'

    class Config:
        from_attributes = True


class UserConfigUpdate(BaseModel):
    """用户配置更新 schema"""
    map_provider: Optional[str] = None
    map_layers: Optional[Dict[str, Dict]] = None
