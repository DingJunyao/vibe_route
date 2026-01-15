"""
配置相关的 Pydantic schemas
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class MapProvider(str):
    """地图提供商枚举"""
    OSM = "osm"
    AMAP = "amap"
    BAIDU = "baidu"


class GeocodingProvider(str):
    """地理编码提供商枚举"""
    NOMINATIM = "nominatim"
    GDF = "gdf"
    AMAP = "amap"
    BAIDU = "baidu"


class ConfigResponse(BaseModel):
    """系统配置响应 schema"""
    registration_enabled: bool
    invite_code_required: bool
    default_map_provider: str
    geocoding_provider: str
    geocoding_config: dict

    class Config:
        from_attributes = True


class ConfigUpdate(BaseModel):
    """系统配置更新 schema"""
    registration_enabled: Optional[bool] = None
    invite_code_required: Optional[bool] = None
    default_map_provider: Optional[str] = None
    geocoding_provider: Optional[str] = None
    geocoding_config: Optional[dict] = None


class InviteCodeCreate(BaseModel):
    """邀请码创建 schema"""
    code: Optional[str] = None  # 不提供则自动生成
    max_uses: int = Field(default=1, ge=1)
    expires_in_days: Optional[int] = Field(None, ge=1)


class InviteCodeResponse(BaseModel):
    """邀请码响应 schema"""
    id: int
    code: str
    max_uses: int
    used_count: int
    created_by: int
    created_at: datetime
    expires_at: Optional[datetime]
    is_valid: bool

    class Config:
        from_attributes = True
