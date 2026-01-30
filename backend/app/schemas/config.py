"""
配置相关的 Pydantic schemas
"""
from datetime import datetime
from typing import Optional, List, Literal, Dict
from pydantic import BaseModel, Field, field_serializer


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
    api_key: Optional[str] = Field(default="", description="高德地图 JS API Key")
    security_js_code: Optional[str] = Field(default="", description="高德地图安全密钥")


class GeocodingProvider(str):
    """地理编码提供商枚举"""
    NOMINATIM = "nominatim"
    GDF = "gdf"
    AMAP = "amap"
    BAIDU = "baidu"


# ========== 道路标志字体配置 ==========

class FontConfig(BaseModel):
    """字体配置 schema"""
    font_a: Optional[str] = Field(None, description="A 型字体路径（中文标题）")
    font_b: Optional[str] = Field(None, description="B 型字体路径（主数字）")
    font_c: Optional[str] = Field(None, description="C 型字体路径（小数字）")


class FontInfo(BaseModel):
    """字体文件信息 schema"""
    filename: str = Field(..., description="文件名")
    size: int = Field(..., description="文件大小（字节）")
    font_type: Optional[str] = Field(None, description="字体类型（A/B/C）")


class ConfigResponse(BaseModel):
    """系统配置响应 schema"""
    registration_enabled: bool
    invite_code_required: bool
    default_map_provider: str
    geocoding_provider: str
    geocoding_config: dict
    map_layers: Dict[str, MapLayerConfig] = Field(default_factory=dict)
    font_config: FontConfig = Field(default_factory=FontConfig)
    show_road_sign_in_region_tree: bool = True
    spatial_backend: str = "auto"

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
    font_config: Optional[FontConfig] = None
    show_road_sign_in_region_tree: Optional[bool] = None
    spatial_backend: Optional[str] = None


class PublicConfigResponse(BaseModel):
    """公开配置响应 schema（普通用户可访问）"""
    default_map_provider: str
    map_layers: Dict[str, MapLayerConfig] = Field(default_factory=dict)
    invite_code_required: bool
    registration_enabled: bool
    font_config: FontConfig = Field(default_factory=FontConfig)
    show_road_sign_in_region_tree: bool = True


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

    @field_serializer('created_at', 'expires_at')
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        """序列化 datetime 为带时区的 ISO 格式字符串（UTC）"""
        if dt is None:
            return None
        return dt.isoformat() + '+00:00'

    class Config:
        from_attributes = True


# 字体列表响应（包含激活状态）
class FontListResponse(BaseModel):
    """字体列表响应 schema"""
    fonts: List[FontInfo]
    active_fonts: FontConfig  # 当前激活的字体配置
