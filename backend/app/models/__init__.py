"""
数据库模型初始化
"""
from app.core.database import Base
from app.models.base import AuditMixin
from app.models.user import User
from app.models.track import Track, TrackPoint
from app.models.config import Config, InviteCode
from app.models.task import Task
from app.models.road_sign import RoadSignCache
from app.models.live_recording import LiveRecording
from app.models.admin_division import AdminDivision
from app.models.admin_division_spatial import AdminDivisionSpatial
from app.models.user_config import UserConfig
from app.models.interpolation import TrackInterpolation
from app.models.overlay_template import OverlayTemplate, Font
from app.models.animation_task import AnimationExportTask

__all__ = [
    "Base",
    "AuditMixin",
    "User",
    "Track",
    "TrackPoint",
    "Config",
    "InviteCode",
    "Task",
    "RoadSignCache",
    "LiveRecording",
    "AdminDivision",
    "AdminDivisionSpatial",
    "UserConfig",
    "TrackInterpolation",
    "OverlayTemplate",
    "Font",
    "AnimationExportTask",
]
