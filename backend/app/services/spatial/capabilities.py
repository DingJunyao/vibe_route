"""
空间计算能力检测

检测数据库是否支持 PostGIS，以便选择最佳的空间计算实现。
"""

from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


class SpatialBackend(str, Enum):
    """空间计算后端类型"""
    AUTO = "auto"      # 自动检测
    PYTHON = "python"  # Python 实现（兼容所有数据库）
    POSTGIS = "postgis"  # PostGIS 实现（需要 PostgreSQL + PostGIS）


class SpatialCapabilityLevel(str, Enum):
    """空间计算能力级别"""
    POSTGIS = "postgis"  # 完整 PostGIS 支持
    BASIC = "basic"      # 基础 SQL 支持


async def detect_spatial_capability(db: AsyncSession) -> SpatialCapabilityLevel:
    """
    检测数据库的空间计算能力

    检测逻辑：
    1. 检查是否为 PostgreSQL 数据库
    2. 如果是 PostgreSQL，检查是否安装了 PostGIS 扩展
    3. 如果安装了 PostGIS，返回 POSTGIS 级别
    4. 否则返回 BASIC 级别

    Args:
        db: 数据库会话

    Returns:
        SpatialCapabilityLevel.POSTGIS 如果安装了 PostGIS
        SpatialCapabilityLevel.BASIC 否则
    """
    try:
        # 检查数据库类型
        # PostgreSQL 的 version() 函数返回类似 "PostgreSQL 15.x..."
        result = await db.execute(text("SELECT version()"))
        version_str = result.scalar()

        if version_str and "PostgreSQL" in version_str:
            # 是 PostgreSQL 数据库，检查 PostGIS 扩展
            try:
                # 检查 postgis 扩展是否存在
                result = await db.execute(
                    text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'postgis')")
                )
                has_postgis = result.scalar()

                if has_postgis:
                    # 进一步检查 PostGIS 版本
                    try:
                        result = await db.execute(text("SELECT PostGIS_Full_Version()"))
                        postgis_version = result.scalar()
                        return SpatialCapabilityLevel.POSTGIS
                    except Exception:
                        # 无法获取版本，但扩展存在
                        return SpatialCapabilityLevel.POSTGIS
            except Exception:
                # 查询失败，可能没有权限或扩展不存在
                pass

        return SpatialCapabilityLevel.BASIC

    except Exception:
        # 检测失败，返回基础级别
        return SpatialCapabilityLevel.BASIC
