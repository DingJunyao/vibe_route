"""
Python 空间计算服务实现

使用纯 Python 实现空间计算，兼容所有数据库。
基于 Haversine 公式计算球面距离。
"""

from math import radians, sin, cos, sqrt, atan2
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.track import TrackPoint
from .spatial_service import ISpatialService


class PythonSpatialService(ISpatialService):
    """
    Python 空间计算服务

    使用 Haversine 公式计算距离，兼容所有数据库。
    性能较低，但无需任何数据库扩展。
    """

    async def distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        计算两点间距离（米）- Haversine 公式

        地球半径使用 6371000 米（平均半径）
        """
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return 6371000 * c

    async def nearby_points(
        self,
        db: AsyncSession,
        track_id: int,
        lat: float,
        lon: float,
        radius: float
    ) -> List[TrackPoint]:
        """
        查找指定半径内的轨迹点

        先用边界框快速过滤，再用 Haversine 公式精确计算距离
        """
        # 边界框粗略估计：1度约等于111km
        lat_delta = radius / 111000
        lon_delta = radius / (111000 * cos(radians(lat)))

        min_lat = lat - lat_delta
        max_lat = lat + lat_delta
        min_lon = lon - lon_delta
        max_lon = lon + lon_delta

        # 先用边界框过滤
        result = await db.execute(
            select(TrackPoint).where(
                and_(
                    TrackPoint.track_id == track_id,
                    TrackPoint.latitude_wgs84 >= min_lat,
                    TrackPoint.latitude_wgs84 <= max_lat,
                    TrackPoint.longitude_wgs84 >= min_lon,
                    TrackPoint.longitude_wgs84 <= max_lon,
                    TrackPoint.is_valid == True
                )
            )
        )
        points = list(result.scalars().all())

        # 精确计算距离，过滤超出半径的点
        nearby = []
        for point in points:
            dist = await self.distance(lat, lon, point.latitude_wgs84, point.longitude_wgs84)
            if dist <= radius:
                nearby.append(point)

        return nearby

    async def points_in_bbox(
        self,
        db: AsyncSession,
        track_id: int,
        min_lat: float,
        min_lon: float,
        max_lat: float,
        max_lon: float
    ) -> List[TrackPoint]:
        """
        查找边界框内的轨迹点
        """
        result = await db.execute(
            select(TrackPoint).where(
                and_(
                    TrackPoint.track_id == track_id,
                    TrackPoint.latitude_wgs84 >= min_lat,
                    TrackPoint.latitude_wgs84 <= max_lat,
                    TrackPoint.longitude_wgs84 >= min_lon,
                    TrackPoint.longitude_wgs84 <= max_lon,
                    TrackPoint.is_valid == True
                )
            )
        )
        return list(result.scalars().all())

    async def track_length(self, points: List[TrackPoint]) -> float:
        """
        计算轨迹总长度（米）

        累加相邻点之间的距离
        """
        if len(points) < 2:
            return 0.0

        total = 0.0
        for i in range(1, len(points)):
            p1 = points[i - 1]
            p2 = points[i]
            total += await self.distance(
                p1.latitude_wgs84, p1.longitude_wgs84,
                p2.latitude_wgs84, p2.longitude_wgs84
            )
        return total

    def get_capability_info(self) -> dict:
        """
        返回当前实现的能力信息
        """
        return {
            "backend": "python",
            "description": "Python Haversine 实现（兼容所有数据库）",
            "features": [
                "distance - Haversine 公式计算",
                "nearby_points - 边界框 + 精确计算",
                "points_in_bbox - SQL 边界框查询",
                "track_length - 累加相邻点距离"
            ],
            "performance": "中等（纯 Python 计算）"
        }
