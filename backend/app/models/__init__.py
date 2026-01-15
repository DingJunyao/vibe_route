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
]
