"""
Pydantic schemas 初始化
"""
from app.schemas.user import (
    UserBase,
    UserCreate,
    UserLogin,
    UserUpdate,
    UserResponse,
    TokenResponse,
)
from app.schemas.track import (
    TrackCreate,
    TrackResponse,
    TrackListResponse,
    TrackPointResponse,
    TrackStatsResponse,
)
from app.schemas.config import (
    ConfigResponse,
    InviteCodeCreate,
    InviteCodeResponse,
    MapProvider,
    GeocodingProvider,
)
from app.schemas.task import (
    TaskResponse,
    TaskCreate,
)
from app.schemas.interpolation import (
    ControlPointHandle,
    ControlPoint,
    AvailableSegment,
    InterpolatedPoint,
    InterpolationCreateRequest,
    InterpolationUpdateRequest,
    InterpolationResponse,
    InterpolationPreviewRequest,
    InterpolationPreviewResponse,
)
from app.schemas.overlay_template import (
    OverlayTemplateConfig,
    OverlayTemplateCreate,
    OverlayTemplateUpdate,
    OverlayTemplateResponse,
    OverlayTemplateListResponse,
    OverlayElement,
    OverlayElementBase,
    PositionConfig,
    SizeConfig,
    ContentConfig,
    TextLayoutConfig,
    StyleConfig,
    SafeAreaConfig,
    BackgroundConfig,
    FontCreate,
    FontResponse,
    FontListResponse,
    OverlayExportRequest,
    DataSource,
    ContainerAnchor,
    ElementAnchor,
)

__all__ = [
    # User
    "UserBase",
    "UserCreate",
    "UserLogin",
    "UserUpdate",
    "UserResponse",
    "TokenResponse",
    # Track
    "TrackCreate",
    "TrackResponse",
    "TrackListResponse",
    "TrackPointResponse",
    "TrackStatsResponse",
    # Config
    "ConfigResponse",
    "InviteCodeCreate",
    "InviteCodeResponse",
    "MapProvider",
    "GeocodingProvider",
    # Task
    "TaskResponse",
    "TaskCreate",
    # Interpolation
    "ControlPointHandle",
    "ControlPoint",
    "AvailableSegment",
    "InterpolatedPoint",
    "InterpolationCreateRequest",
    "InterpolationUpdateRequest",
    "InterpolationResponse",
    "InterpolationPreviewRequest",
    "InterpolationPreviewResponse",
    # Overlay Template
    "OverlayTemplateConfig",
    "OverlayTemplateCreate",
    "OverlayTemplateUpdate",
    "OverlayTemplateResponse",
    "OverlayTemplateListResponse",
    "OverlayElement",
    "OverlayElementBase",
    "PositionConfig",
    "SizeConfig",
    "ContentConfig",
    "TextLayoutConfig",
    "StyleConfig",
    "SafeAreaConfig",
    "BackgroundConfig",
    "FontCreate",
    "FontResponse",
    "FontListResponse",
    "OverlayExportRequest",
    "DataSource",
    "ContainerAnchor",
    "ElementAnchor",
]
