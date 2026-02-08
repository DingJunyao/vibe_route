"""
轨迹插值服务
"""
import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track, TrackPoint
from app.models.interpolation import TrackInterpolation
from app.schemas.interpolation import (
    InterpolationCreateRequest,
    InterpolationUpdateRequest,
    InterpolationResponse,
    AvailableSegment,
    InterpolatedPoint,
    InterpolationPreviewRequest,
    InterpolationPreviewResponse,
    ControlPoint
)
from app.utils.bezier import (
    Point, CubicBezierCurve,
    calculate_distance, linear_interpolate, interpolate_angle
)
from app.gpxutil_wrapper.coord_transform import wgs84_to_gcj02, gcj02_to_bd09

logger = logging.getLogger(__name__)


class InterpolationService:
    """插值服务"""

    async def get_available_segments(
        self,
        db: AsyncSession,
        track_id: int,
        min_interval_seconds: float,
        ignore_interpolated: bool = True
    ) -> List[AvailableSegment]:
        """
        获取可用于插值的区段

        Args:
            db: 数据库会话
            track_id: 轨迹ID
            min_interval_seconds: 最小间隔（秒）
            ignore_interpolated: 是否忽略已有插值的区段

        Returns:
            可用区段列表
        """
        # 构建查询条件
        conditions = [
            TrackPoint.track_id == track_id,
            TrackPoint.is_valid == True
        ]

        # 是否忽略插值点
        if ignore_interpolated:
            conditions.append(TrackPoint.is_interpolated == False)

        # 获取轨迹的所有点（按索引排序）
        result = await db.execute(
            select(TrackPoint)
            .where(and_(*conditions))
            .order_by(TrackPoint.point_index)
        )
        points = result.scalars().all()

        segments = []
        for i in range(len(points) - 1):
            curr, next_p = points[i], points[i + 1]

            # 计算时间差
            if curr.time and next_p.time:
                interval = (next_p.time - curr.time).total_seconds()
                if interval >= min_interval_seconds:
                    segments.append(AvailableSegment(
                        start_index=curr.point_index,
                        end_index=next_p.point_index,
                        interval_seconds=interval,
                        start_time=curr.time,
                        end_time=next_p.time
                    ))

        return segments

    async def preview_interpolation(
        self,
        db: AsyncSession,
        request: InterpolationPreviewRequest
    ) -> InterpolationPreviewResponse:
        """
        生成插值预览
        """
        # 获取起点和终点
        start_point_result = await db.execute(
            select(TrackPoint).where(
                and_(
                    TrackPoint.track_id == request.track_id,
                    TrackPoint.point_index == request.start_point_index
                )
            )
        )
        start_point = start_point_result.scalar_one_or_none()

        end_point_result = await db.execute(
            select(TrackPoint).where(
                and_(
                    TrackPoint.track_id == request.track_id,
                    TrackPoint.point_index == request.end_point_index
                )
            )
        )
        end_point = end_point_result.scalar_one_or_none()

        if not start_point or not end_point:
            raise ValueError("起点或终点不存在")

        # 生成插值点
        interpolated_points = self._generate_interpolated_points(
            start_point=start_point,
            end_point=end_point,
            control_points=request.control_points,
            interval_seconds=request.interpolation_interval_seconds
        )

        return InterpolationPreviewResponse(
            points=interpolated_points,
            total_count=len(interpolated_points),
            start_time=start_point.time,
            end_time=end_point.time
        )

    def _generate_interpolated_points(
        self,
        start_point: TrackPoint,
        end_point: TrackPoint,
        control_points: List[ControlPoint],
        interval_seconds: float
    ) -> List[InterpolatedPoint]:
        """
        生成插值点

        Args:
            start_point: 起点轨迹点
            end_point: 终点轨迹点
            control_points: 控制点列表
            interval_seconds: 插值间隔（秒）

        Returns:
            插值点列表
        """
        # 构建曲线点序列
        curve_points = [
            Point(start_point.longitude_wgs84, start_point.latitude_wgs84)
        ]

        # 添加控制点（带手柄偏移）
        for cp in control_points:
            # 计算实际的控制点位置（点位置 + 手柄偏移）
            # 对于起点到终点的曲线，控制点直接使用其坐标
            curve_points.append(Point(cp.lng, cp.lat))

        curve_points.append(Point(end_point.longitude_wgs84, end_point.latitude_wgs84))

        # 创建贝塞尔曲线
        curve = CubicBezierCurve(curve_points)

        # 计算时间差和点数
        time_diff = (end_point.time - start_point.time).total_seconds()
        point_count = max(0, int(time_diff / interval_seconds))

        if point_count == 0:
            return []

        # 生成曲线上的点（排除起点和终点，只生成中间点）
        curve_points_result = curve.generate_points(point_count + 2)

        # 生成插值点数据
        interpolated = []
        start_speed = start_point.speed or 0
        end_speed = end_point.speed or 0
        start_course = start_point.bearing or 0
        end_course = end_point.bearing or 0
        start_elevation = start_point.elevation
        end_elevation = end_point.elevation

        # 跳过第一个点（起点）和最后一个点（终点），只生成中间的插值点
        for i, point in enumerate(curve_points_result[1:-1], start=1):
            t = i / point_count if point_count > 0 else 0

            # 计算时间
            point_time = start_point.time + timedelta(seconds=i * interval_seconds)

            # 线性插值速度和航向
            speed = linear_interpolate(start_speed, end_speed, t)
            course = interpolate_angle(start_course, end_course, t)

            # 线性插值高程
            elevation = None
            if start_elevation is not None and end_elevation is not None:
                elevation = linear_interpolate(start_elevation, end_elevation, t)

            # 坐标转换
            lat_wgs, lng_wgs = point.lat, point.lng
            lng_gcj, lat_gcj = wgs84_to_gcj02(lng_wgs, lat_wgs)
            lng_bd, lat_bd = gcj02_to_bd09(lng_gcj, lat_gcj)

            interpolated.append(InterpolatedPoint(
                point_index=0,  # 稍后分配
                time=point_time,
                latitude=lat_wgs,
                longitude=lng_wgs,
                latitude_gcj02=lat_gcj,
                longitude_gcj02=lng_gcj,
                latitude_bd09=lat_bd,
                longitude_bd09=lng_bd,
                speed=speed,
                course=course,
                elevation=elevation
            ))

        return interpolated

    async def create_interpolation(
        self,
        db: AsyncSession,
        track_id: int,
        request: InterpolationCreateRequest,
        user_id: int
    ) -> InterpolationResponse:
        """
        创建插值

        Args:
            db: 数据库会话
            track_id: 轨迹ID
            request: 创建请求
            user_id: 用户ID

        Returns:
            插值响应
        """
        # 1. 验证区段
        segments = await self.get_available_segments(
            db, track_id, min_interval_seconds=3.0
        )
        valid_segment = None
        for seg in segments:
            if seg.start_index == request.start_point_index and seg.end_index == request.end_point_index:
                valid_segment = seg
                break

        if not valid_segment:
            raise ValueError("所选区段不可用于插值")

        # 2. 生成插值预览
        preview_request = InterpolationPreviewRequest(
            track_id=track_id,
            start_point_index=request.start_point_index,
            end_point_index=request.end_point_index,
            control_points=request.control_points,
            interpolation_interval_seconds=request.interpolation_interval_seconds
        )
        preview = await self.preview_interpolation(db, preview_request)

        # 3. 创建插值记录
        control_points_data = [cp.dict() for cp in request.control_points]
        interpolation = TrackInterpolation(
            track_id=track_id,
            start_point_index=request.start_point_index,
            end_point_index=request.end_point_index,
            path_geometry=json.dumps(control_points_data),
            interpolation_interval_seconds=int(request.interpolation_interval_seconds),
            point_count=len(preview.points),
            algorithm=request.algorithm,
            created_by=user_id,
            updated_by=user_id
        )
        db.add(interpolation)
        await db.flush()

        # 4. 插入插值点
        await self._insert_interpolated_points(
            db,
            track_id,
            interpolation.id,
            request.start_point_index,
            preview.points
        )

        await db.commit()
        await db.refresh(interpolation)

        return InterpolationResponse(
            id=interpolation.id,
            track_id=interpolation.track_id,
            start_point_index=interpolation.start_point_index,
            end_point_index=interpolation.end_point_index,
            point_count=interpolation.point_count,
            control_points=request.control_points,
            interpolation_interval_seconds=interpolation.interpolation_interval_seconds,
            algorithm=interpolation.algorithm,
            created_at=interpolation.created_at
        )

    async def _insert_interpolated_points(
        self,
        db: AsyncSession,
        track_id: int,
        interpolation_id: int,
        start_point_index: int,
        points: List[InterpolatedPoint]
    ):
        """
        插入插值点到数据库

        Args:
            db: 数据库会话
            track_id: 轨迹ID
            interpolation_id: 插值ID
            start_point_index: 起点索引
            points: 插值点列表
        """
        # 更新后续点的索引（为插入腾出空间）
        # 首先获取需要更新的点
        result = await db.execute(
            select(TrackPoint).where(
                and_(
                    TrackPoint.track_id == track_id,
                    TrackPoint.point_index > start_point_index
                )
            )
        )
        points_to_update = result.scalars().all()

        # 计算索引偏移量
        offset = len(points)

        # 批量更新索引
        for point in points_to_update:
            point.point_index += offset

        # 批量插入插值点
        new_index_start = start_point_index + 1
        for i, point_data in enumerate(points):
            track_point = TrackPoint(
                track_id=track_id,
                point_index=new_index_start + i,
                time=point_data.time,
                latitude_wgs84=point_data.latitude,
                longitude_wgs84=point_data.longitude,
                latitude_gcj02=point_data.latitude_gcj02,
                longitude_gcj02=point_data.longitude_gcj02,
                latitude_bd09=point_data.latitude_bd09,
                longitude_bd09=point_data.longitude_bd09,
                speed=point_data.speed,
                bearing=point_data.course,
                elevation=point_data.elevation,
                is_interpolated=True,
                interpolation_id=interpolation_id,
                # 插值点不包含地理信息
                province=None,
                city=None,
                district=None,
                road_name=None,
                road_number=None,
                is_valid=True
            )
            db.add(track_point)

        await db.flush()

    async def delete_interpolation(
        self,
        db: AsyncSession,
        interpolation_id: int
    ) -> bool:
        """
        删除插值配置及关联的插值点

        Args:
            db: 数据库会话
            interpolation_id: 插值ID

        Returns:
            是否成功删除
        """
        # 获取插值记录
        result = await db.execute(
            select(TrackInterpolation).where(
                TrackInterpolation.id == interpolation_id
            )
        )
        interpolation = result.scalar_one_or_none()

        if not interpolation:
            raise ValueError("插值记录不存在")

        # 获取关联的插值点
        points_result = await db.execute(
            select(TrackPoint).where(
                TrackPoint.interpolation_id == interpolation_id
            )
        )
        interpolated_points = points_result.scalars().all()

        # 软删除插值记录
        interpolation.is_valid = False

        # 删除或标记插值点
        for point in interpolated_points:
            point.is_valid = False
            point.is_interpolated = False
            point.interpolation_id = None

        await db.commit()
        return True

    async def get_interpolation_by_id(
        self,
        db: AsyncSession,
        interpolation_id: int
    ) -> Optional[InterpolationResponse]:
        """
        获取插值配置详情

        Args:
            db: 数据库会话
            interpolation_id: 插值ID

        Returns:
            插值响应
        """
        result = await db.execute(
            select(TrackInterpolation).where(
                TrackInterpolation.id == interpolation_id
            )
        )
        interpolation = result.scalar_one_or_none()

        if not interpolation:
            return None

        # 解析控制点
        control_points_data = json.loads(interpolation.path_geometry)
        control_points = [ControlPoint(**cp) for cp in control_points_data]

        return InterpolationResponse(
            id=interpolation.id,
            track_id=interpolation.track_id,
            start_point_index=interpolation.start_point_index,
            end_point_index=interpolation.end_point_index,
            point_count=interpolation.point_count,
            control_points=control_points,
            interpolation_interval_seconds=interpolation.interpolation_interval_seconds,
            algorithm=interpolation.algorithm,
            created_at=interpolation.created_at
        )

    async def get_track_interpolations(
        self,
        db: AsyncSession,
        track_id: int
    ) -> List[InterpolationResponse]:
        """
        获取轨迹的所有插值配置

        Args:
            db: 数据库会话
            track_id: 轨迹ID

        Returns:
            插值响应列表
        """
        result = await db.execute(
            select(TrackInterpolation)
            .where(
                TrackInterpolation.track_id == track_id,
                TrackInterpolation.is_valid == True
            )
            .order_by(TrackInterpolation.start_point_index)
        )
        interpolations = result.scalars().all()

        responses = []
        for interp in interpolations:
            # 解析控制点
            control_points_data = json.loads(interp.path_geometry)
            control_points = [ControlPoint(**cp) for cp in control_points_data]

            responses.append(InterpolationResponse(
                id=interp.id,
                track_id=interp.track_id,
                start_point_index=interp.start_point_index,
                end_point_index=interp.end_point_index,
                point_count=interp.point_count,
                control_points=control_points,
                interpolation_interval_seconds=interp.interpolation_interval_seconds,
                algorithm=interp.algorithm,
                created_at=interp.created_at
            ))

        return responses


# 单例服务实例
interpolation_service = InterpolationService()
