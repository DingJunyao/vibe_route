"""
空间服务工厂

根据数据库能力和用户配置创建合适的空间服务实例。
"""

from sqlalchemy.ext.asyncio import AsyncSession

from .spatial_service import ISpatialService
from .python_spatial import PythonSpatialService
from .postgis_spatial import PostGISSpatialService
from .capabilities import SpatialBackend, SpatialCapabilityLevel, detect_spatial_capability


async def create_spatial_service(
    db: AsyncSession,
    backend: SpatialBackend = SpatialBackend.AUTO
) -> ISpatialService:
    """
    创建空间服务实例

    Args:
        db: 数据库会话
        backend: 空间后端类型
            - AUTO: 自动检测数据库能力
            - PYTHON: 强制使用 Python 实现
            - POSTGIS: 强制使用 PostGIS 实现（如果可用）

    Returns:
        空间服务实例

    Raises:
        ValueError: 如果强制使用 POSTGIS 但数据库不支持
    """
    if backend == SpatialBackend.PYTHON:
        return PythonSpatialService()

    if backend == SpatialBackend.POSTGIS:
        # 强制使用 PostGIS，需要验证数据库支持
        capability = await detect_spatial_capability(db)
        if capability != SpatialCapabilityLevel.POSTGIS:
            raise ValueError(
                "PostGIS 后端已配置但数据库不支持 PostGIS。"
                "请确保使用 PostgreSQL 数据库并安装 PostGIS 扩展，"
                "或者将配置改为 'auto' 或 'python'。"
            )
        return PostGISSpatialService()

    # AUTO 模式：自动检测
    capability = await detect_spatial_capability(db)
    if capability == SpatialCapabilityLevel.POSTGIS:
        return PostGISSpatialService()
    return PythonSpatialService()
