"""
配置相关的 Pydantic schemas
"""
from datetime import datetime
from typing import Optional, List, Literal, Dict
from pydantic import BaseModel, Field


class MapProvider(str):
    """地图提供商枚举"""
    OSM = "osm"
    AMAP = "amap"
    BAIDU = "baidu"
    TIANDITU = "tianditu"


# 坐标系类型
CRSType = Literal["wgs84", "gcj02", "bd09"]


class MapLayerConfig(BaseModel):
    """地图底图配置"""
    id: str = Field(..., description="地图唯一标识")
    name: str = Field(..., description="地图显示名称")
    url: Optional[str] = Field(None, description="瓦片 URL 模板，支持 {x}, {y}, {z}, {s}, {ak}, {tk} 占位符")
    crs: CRSType = Field(..., description="坐标系类型")
    attribution: str = Field(default="", description="版权信息")
    max_zoom: int = Field(default=19, description="最大缩放级别")
    min_zoom: int = Field(default=1, description="最小缩放级别")
    enabled: bool = Field(default=True, description="是否启用")
    order: int = Field(default=0, description="显示顺序")
    subdomains: Optional[str | List[str]] = Field(default=None, description="子域名列表，如 'abc' 或 ['0','1','2']")
    ak: Optional[str] = Field(default="", description="百度地图 AK")
    tk: Optional[str] = Field(default="", description="天地图 tk")


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
    map_layers: Dict[str, MapLayerConfig] = Field(default_factory=dict)

    class Config:
        from_attributes = True


class ConfigUpdate(BaseModel):
    """系统配置更新 schema"""
    registration_enabled: Optional[bool] = None
    invite_code_required: Optional[bool] = None
    default_map_provider: Optional[str] = None
    geocoding_provider: Optional[str] = None
    geocoding_config: Optional[dict] = None
    map_layers: Optional[Dict[str, Dict]] = None


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
