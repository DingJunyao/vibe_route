"""
PostGIS 空间计算服务实现

使用 PostGIS 函数实现空间计算，需要 PostgreSQL + PostGIS。
性能高，支持空间索引加速查询。
"""

from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, text, func

from app.models.track import TrackPoint
from .spatial_service import ISpatialService


class PostGISSpatialService(ISpatialService):
    """
    PostGIS 空间计算服务

    使用 PostGIS 函数进行空间计算，性能高。
    需要 PostgreSQL 数据库和 PostGIS 扩展。
    """

    async def distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        计算两点间距离（米）

        使用 ST_Distance(geography, geography)
        返回以米为单位的距离
        """
        # 由于这是纯计算函数，没有数据库连接时使用 Haversine 作为回退
        # 实际使用时，建议通过数据库查询来使用 ST_Distance
        from math import radians, sin, cos, sqrt, atan2
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

        使用 ST_DWithin 进行空间查询
        """
        # 使用原生 SQL 查询，利用 PostGIS 的 ST_DWithin
        # ST_DWithin 使用 geography 类型，自动处理地球曲率
        sql = text("""
            SELECT id
            FROM track_points
            WHERE track_id = :track_id
                AND is_valid = TRUE
                AND ST_DWithin(
                    ST_MakePoint(longitude_wgs84, latitude_wgs84)::geography,
                    ST_MakePoint(:lon, :lat)::geography,
                    :radius
                )
            ORDER BY ST_Distance(
                ST_MakePoint(longitude_wgs84, latitude_wgs84)::geography,
                ST_MakePoint(:lon, :lat)::geography
            )
        """)

        result = await db.execute(
            sql,
            {
                "track_id": track_id,
                "lat": lat,
                "lon": lon,
                "radius": radius
            }
        )
        point_ids = [row[0] for row in result]

        if not point_ids:
            return []

        # 根据 ID 获取完整的 TrackPoint 对象
        final_result = await db.execute(
            select(TrackPoint).where(
                and_(
                    TrackPoint.id.in_(point_ids),
                    TrackPoint.track_id == track_id,
                    TrackPoint.is_valid == True
                )
            )
        )

        # 按照距离排序
        points_by_id = {p.id: p for p in final_result.scalars().all()}
        return [points_by_id[pid] for pid in point_ids if pid in points_by_id]

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

        使用 ST_Within 和 ST_MakeEnvelope
        """
        sql = text("""
            SELECT id
            FROM track_points
            WHERE track_id = :track_id
                AND is_valid = TRUE
                AND ST_Within(
                    ST_MakePoint(longitude_wgs84, latitude_wgs84)::geography,
                    ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326)::geography
                )
        """)

        result = await db.execute(
            sql,
            {
                "track_id": track_id,
                "min_lat": min_lat,
                "min_lon": min_lon,
                "max_lat": max_lat,
                "max_lon": max_lon
            }
        )
        point_ids = [row[0] for row in result]

        if not point_ids:
            return []

        final_result = await db.execute(
            select(TrackPoint).where(
                and_(
                    TrackPoint.id.in_(point_ids),
                    TrackPoint.track_id == track_id,
                    TrackPoint.is_valid == True
                )
            )
        )
        return list(final_result.scalars().all())

    async def track_length(self, points: List[TrackPoint]) -> float:
        """
        计算轨迹总长度（米）

        使用 ST_Length 计算线段长度
        """
        if len(points) < 2:
            return 0.0

        # 对于少量点，使用累加距离
        # 对于大量点，可以构建 LineString 使用 ST_Length
        total = 0.0
        for i in range(1, len(points)):
            p1 = points[i - 1]
            p2 = points[i]
            # 简单的累加计算（大量点时可优化为 ST_Length）
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
            "backend": "postgis",
            "description": "PostGIS 空间数据库实现（高性能）",
            "features": [
                "distance - Haversine 回退（或可使用 ST_Distance）",
                "nearby_points - ST_DWithin 空间索引查询",
                "points_in_bbox - ST_Within 边界框查询",
                "track_length - 累加计算（可优化为 ST_Length）"
            ],
            "performance": "高（空间索引 + 数据库引擎）"
        }
