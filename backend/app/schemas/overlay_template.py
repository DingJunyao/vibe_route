"""
覆盖层模板相关 Schemas
"""
from typing import Optional, List, Literal, Any, Dict
from pydantic import BaseModel, Field, model_validator
from datetime import datetime


# ============================================================================
# 锚点类型
# ============================================================================

ContainerAnchor = Literal[
    'top-left', 'top', 'top-right',
    'left', 'center', 'right',
    'bottom-left', 'bottom', 'bottom-right'
]

ElementAnchor = ContainerAnchor  # 元素锚点与容器锚点相同

# ============================================================================
# 数据源类型
# ============================================================================

DataSource = Literal[
    'province',           # 省份
    'city',               # 城市
    'district',           # 区县
    'province_en',        # 省份英文名
    'city_en',            # 城市英文名
    'district_en',        # 区县英文名
    'region',             # 区域（组合显示，如"河南省 三门峡市 湖滨区"）
    'region_en',          # 区域英文（组合显示，如"Hubin District, Sanmenxia City, Henan Province"）
    'road_number',        # 道路编号
    'road_name',          # 道路名称
    'road_name_en',       # 道路英文名
    'speed',              # 速度
    'elevation',          # 海拔
    'compass_angle',      # 方位角
    'elapsed_distance',   # 已行驶距离
    'elapsed_time',       # 已用时间
    'remain_distance',    # 剩余距离
    'remain_time',        # 剩余时间
    'current_time',       # 当前时间
    'latitude',           # 纬度
    'longitude',          # 经度
]

# ============================================================================
# 位置配置
# ============================================================================

class PositionConfig(BaseModel):
    """位置配置"""
    container_anchor: ContainerAnchor = Field(default='top-left', description="容器锚点")
    element_anchor: ElementAnchor = Field(default='top-left', description="元素锚点")
    x: float = Field(default=0.0, ge=-0.5, le=0.5, description="X偏移（画布宽度的百分比）")
    y: float = Field(default=0.0, ge=-0.5, le=0.5, description="Y偏移（画布高度的百分比）")
    use_safe_area: bool = Field(default=False, description="是否使用安全区")

# ============================================================================
# 尺寸配置
# ============================================================================

class SizeConfig(BaseModel):
    """尺寸配置（百分比）"""
    width: Optional[float] = Field(None, ge=0, le=1, description="宽度（画布宽度的百分比）")
    height: Optional[float] = Field(None, ge=0, le=1, description="高度（画布高度的百分比）")

# ============================================================================
# 内容配置
# ============================================================================

class ContentConfig(BaseModel):
    """内容配置"""
    source: DataSource = Field(description="数据来源")
    prefix: str = Field(default='', description="前缀（已废弃，使用format）")
    suffix: str = Field(default='', description="后缀（已废弃，使用format）")
    format: str = Field(default='{}', description="格式化字符串，支持前缀后缀和小数位数，如'速度: {:.1f} km/h'")
    sample_text: Optional[str] = Field(None, description="自定义示例文本（预览时使用）")
    decimal_places: Optional[int] = Field(None, ge=0, le=10, description="小数位数（仅数字类型）")

# ============================================================================
# 文本布局配置
# ============================================================================

class TextLayoutConfig(BaseModel):
    """文本布局配置"""
    width: Optional[float] = Field(None, ge=0, le=1, description="固定宽度")
    max_width: Optional[float] = Field(None, ge=0, le=1, description="最大宽度")
    min_width: Optional[float] = Field(None, ge=0, le=1, description="最小宽度")
    height: Optional[float] = Field(None, ge=0, le=1, description="固定高度")
    horizontal_align: Literal['left', 'center', 'right', 'justify'] = Field(default='left', description="水平对齐")
    vertical_align: Literal['top', 'middle', 'bottom'] = Field(default='top', description="垂直对齐")
    wrap: bool = Field(default=False, description="是否折行")
    max_lines: Optional[int] = Field(None, ge=1, description="最大行数")
    line_height: float = Field(default=1.2, ge=0.5, le=3.0, description="行高倍数")
    char_spacing: Optional[float] = Field(None, ge=0, description="字间距（相对于字号的百分比）")
    paragraph_spacing: Optional[float] = Field(None, ge=0, description="段落间距（相对于字号的百分比）")

# ============================================================================
# 样式配置
# ============================================================================

class StyleConfig(BaseModel):
    """样式配置"""
    font_family: str = Field(default='system_msyh', description="字体ID")
    font_size: float = Field(default=0.03, gt=0, le=0.2, description="字体大小（画布高度的百分比）")
    color: str = Field(default='#FFFFFF', description="文本颜色")
    background_color: Optional[str] = Field(None, description="背景颜色")
    padding: Optional[float] = Field(None, ge=0, description="内边距（相对于字号）")

# ============================================================================
# 元素配置
# ============================================================================

class OverlayElementBase(BaseModel):
    """覆盖层元素基础配置"""
    id: str = Field(description="元素ID")
    type: Literal['text', 'road_sign', 'icon', 'group'] = Field(default='text', description="元素类型")
    name: str = Field(description="元素名称")
    visible: bool = Field(default=True, description="是否可见")

    # 位置和尺寸
    position: PositionConfig = Field(default_factory=PositionConfig, description="位置配置")
    size: SizeConfig = Field(default_factory=SizeConfig, description="尺寸配置")

    # 样式（所有元素通用）
    style: Optional[StyleConfig] = Field(default=None, description="样式配置")

    # 数据绑定（非group元素）
    content: Optional[ContentConfig] = Field(default=None, description="内容配置")

    # 文本布局（仅text元素）
    layout: Optional[TextLayoutConfig] = Field(default=None, description="文本布局配置")

    # 子元素（仅group元素）
    children: Optional[List['OverlayElement']] = Field(default=None, description="子元素")


# 支持自引用
OverlayElement = OverlayElementBase

# ============================================================================
# 安全区配置
# ============================================================================

class SafeAreaConfig(BaseModel):
    """安全区配置"""
    top: float = Field(default=0.05, ge=0, le=0.2, description="顶部边距")
    bottom: float = Field(default=0.05, ge=0, le=0.2, description="底部边距")
    left: float = Field(default=0.05, ge=0, le=0.2, description="左侧边距")
    right: float = Field(default=0.05, ge=0, le=0.2, description="右侧边距")

# ============================================================================
# 背景配置
# ============================================================================

class BackgroundConfig(BaseModel):
    """背景配置"""
    color: str = Field(default='#000000', description="背景颜色")
    opacity: float = Field(default=0.0, ge=0, le=1, description="不透明度")

# ============================================================================
# 模板配置
# ============================================================================

class CanvasConfig(BaseModel):
    """画布配置"""
    width: int = Field(default=1920, ge=100, le=7680, description="画布宽度（像素）")
    height: int = Field(default=1080, ge=100, le=4320, description="画布高度（像素）")


class OverlayTemplateConfig(BaseModel):
    """覆盖层模板配置"""
    canvas: CanvasConfig = Field(default_factory=CanvasConfig, description="画布配置")
    safe_area: SafeAreaConfig = Field(default_factory=SafeAreaConfig, description="安全区配置")
    background: Optional[BackgroundConfig] = Field(default=None, description="背景配置")
    elements: List[OverlayElement] = Field(default_factory=list, description="元素列表")

# ============================================================================
# API 请求/响应模型
# ============================================================================

class OverlayTemplateCreate(BaseModel):
    """创建覆盖层模板请求"""
    name: str = Field(..., min_length=1, max_length=100, description="模板名称")
    description: Optional[str] = Field(None, description="模板描述")
    config: OverlayTemplateConfig = Field(..., description="模板配置")


class OverlayTemplateUpdate(BaseModel):
    """更新覆盖层模板请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="模板名称")
    description: Optional[str] = Field(None, description="模板描述")
    config: Optional[OverlayTemplateConfig] = Field(None, description="模板配置")
    is_public: Optional[bool] = Field(None, description="是否公开")


class OverlayTemplateResponse(BaseModel):
    """覆盖层模板响应"""
    id: int
    name: str
    description: Optional[str]
    config: OverlayTemplateConfig
    user_id: Optional[int]
    is_public: bool
    is_system: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OverlayTemplateListResponse(BaseModel):
    """覆盖层模板列表响应"""
    total: int
    items: List[OverlayTemplateResponse]


# ============================================================================
# 导入/导出
# ============================================================================

class OverlayTemplateImport(BaseModel):
    """导入覆盖层模板"""
    file: bytes  # YAML 文件内容


class OverlayTemplateExport(BaseModel):
    """导出覆盖层模板"""
    yaml_content: str


# ============================================================================
# 预览
# ============================================================================

class OverlayPreviewRequest(BaseModel):
    """预览请求"""
    template_id: int
    resolution: str = Field(default='1920x1080', description="预览分辨率")


# ============================================================================
# 字体相关
# ============================================================================

class FontCreate(BaseModel):
    """创建字体请求（管理员上传）"""
    name: str = Field(..., max_length=100, description="字体名称")


class FontResponse(BaseModel):
    """字体响应"""
    id: str
    name: str
    filename: str
    type: Literal['system', 'admin', 'user']
    owner_id: Optional[int]
    file_size: int
    family: Optional[str]
    style: str
    weight: int
    supports_latin: bool
    supports_chinese: bool
    supports_japanese: bool
    supports_korean: bool
    preview_url: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class FontListResponse(BaseModel):
    """字体列表响应"""
    total: int
    items: List[FontResponse]


# ============================================================================
# 导出配置
# ============================================================================

class OverlayExportRequest(BaseModel):
    """覆盖层导出请求（使用模板配置中的画布尺寸）"""
    template_id: int = Field(..., description="模板ID")
    frame_rate: int = Field(default=1, ge=0, description="采样率（0=全部，1=每秒1帧）")
    start_index: int = Field(default=0, ge=0, description="起始点索引")
    end_index: int = Field(default=-1, description="结束点索引（-1=到最后）")
    output_format: Literal['zip', 'png_sequence'] = Field(default='zip', description="输出格式")


class PreviewWithConfigRequest(BaseModel):
    """使用配置生成预览的请求"""
    config: OverlayTemplateConfig = Field(..., description="模板配置")
