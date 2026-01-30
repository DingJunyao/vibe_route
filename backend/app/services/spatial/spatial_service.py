"""
空间计算服务抽象接口

定义空间计算服务的统一接口，支持多种实现方式。
"""

from abc import ABC, abstractmethod
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession


class ISpatialService(ABC):
    """空间计算服务抽象接口"""

    @abstractmethod
    async def distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        计算两点间距离（米）

        Args:
            lat1, lon1: 第一个点的纬度、经度
            lat2, lon2: 第二个点的纬度、经度

        Returns:
            距离（米）
        """

    @abstractmethod
    async def nearby_points(
        self,
        db: AsyncSession,
        track_id: int,
        lat: float,
        lon: float,
        radius: float
    ) -> List:
        """
        查找指定半径内的轨迹点

        Args:
            db: 数据库会话
            track_id: 轨迹 ID
            lat, lon: 中心点坐标
            radius: 半径（米）

        Returns:
            轨迹点列表
        """

    @abstractmethod
    async def points_in_bbox(
        self,
        db: AsyncSession,
        track_id: int,
        min_lat: float,
        min_lon: float,
        max_lat: float,
        max_lon: float
    ) -> List:
        """
        查找边界框内的轨迹点

        Args:
            db: 数据库会话
            track_id: 轨迹 ID
            min_lat, min_lon: 边界框最小坐标
            max_lat, max_lon: 边界框最大坐标

        Returns:
            轨迹点列表
        """

    @abstractmethod
    async def track_length(self, points: List) -> float:
        """
        计算轨迹总长度（米）

        Args:
            points: 轨迹点列表

        Returns:
            轨迹总长度（米）
        """

    @abstractmethod
    def get_capability_info(self) -> dict:
        """
        返回当前实现的能力信息

        Returns:
            包含能力信息的字典，如：
            {
                "backend": "python" | "postgis",
                "description": "...",
                "features": [...]
            }
        """
