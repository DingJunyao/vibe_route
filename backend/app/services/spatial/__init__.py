"""
空间计算服务模块

提供多数据库兼容的空间计算抽象层，支持：
- Python 实现（兼容所有数据库）
- PostGIS 实现（PostgreSQL + PostGIS，高性能）
"""

from .spatial_service import ISpatialService
from .python_spatial import PythonSpatialService
from .postgis_spatial import PostGISSpatialService
from .capabilities import SpatialBackend, SpatialCapabilityLevel, detect_spatial_capability
from .factory import create_spatial_service

__all__ = [
    "ISpatialService",
    "PythonSpatialService",
    "PostGISSpatialService",
    "SpatialBackend",
    "SpatialCapabilityLevel",
    "detect_spatial_capability",
    "create_spatial_service",
]
