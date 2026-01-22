"""
轨迹服务层
"""
import gpxpy
import asyncio
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import select, func, delete, insert, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track, TrackPoint
from app.models.user import User
from app.gpxutil_wrapper.coord_transform import convert_point_to_all, CoordinateType
from app.gpxutil_wrapper.geocoding import create_geocoding_service, GeocodingProvider
from app.core.query_helper import QueryHelper, SoftDeleteMixin, AuditMixin as QueryAuditMixin
from loguru import logger


class TrackService:
    """轨迹服务类"""

    def __init__(self):
        self._geocoding_service = None
        self._geocoding_provider = None
        self._geocoding_config = None

        # 存储当前正在填充的轨迹进度
        self._filling_progress = {}  # {track_id: {"current": 10, "total": 100, "status": "filling"}}

        # 追踪后台任务
        self._background_tasks = set()  # type: set[asyncio.Task]

    async def cancel_all_tasks(self):
        """取消所有后台任务"""
        for task in list(self._background_tasks):
            if not task.done():
                task.cancel()
        # 等待任务取消
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        self._background_tasks.clear()

    async def _get_geocoding_service(self, db: AsyncSession):
        """获取地理编码服务实例"""
        from app.services.config_service import config_service

        provider = await config_service.get(db, "geocoding_provider")
        if not provider:
            return None

        if self._geocoding_service is None or self._geocoding_provider != provider:
            self._geocoding_provider = provider
            config = await config_service.get_json(db, "geocoding_config", {})
            provider_config = config.get(provider, {})
            self._geocoding_service = create_geocoding_service(provider, provider_config)

        return self._geocoding_service

    async def get_by_id(self, db: AsyncSession, track_id: int, user_id: int) -> Optional[Track]:
        """获取轨迹（带用户权限检查）"""
        result = await db.execute(
            select(Track).where(
                and_(
                    Track.id == track_id,
                    Track.user_id == user_id,
                    Track.is_valid == True
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_no_check(self, db: AsyncSession, track_id: int) -> Optional[Track]:
        """获取轨迹（不带权限检查）"""
        result = await db.execute(
            select(Track).where(and_(Track.id == track_id, Track.is_valid == True))
        )
        return result.scalar_one_or_none()

    async def get_list(
        self,
        db: AsyncSession,
        user_id: int,
        skip: int = 0,
        limit: int = 20,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = "desc",
    ) -> tuple[List[Track], int]:
        """
        获取用户的轨迹列表

        Args:
            db: 数据库会话
            user_id: 用户ID
            skip: 跳过记录数
            limit: 返回记录数
            search: 搜索轨迹名称（模糊匹配）
            sort_by: 排序字段 (start_time, distance, duration)
            sort_order: 排序方向 (asc=正序, desc=倒序)

        Returns:
            (轨迹列表, 总数)
        """
        # 构建基础查询条件
        conditions = [Track.user_id == user_id, Track.is_valid == True]

        # 添加搜索条件
        if search:
            conditions.append(Track.name.ilike(f"%{search}%"))

        # 获取总数
        count_result = await db.execute(
            select(func.count(Track.id)).where(and_(*conditions))
        )
        total = count_result.scalar() or 0

        # 确定排序字段和方向
        sort_field = Track.start_time  # 默认按轨迹开始时间排序
        if sort_by == "distance":
            sort_field = Track.distance
        elif sort_by == "duration":
            sort_field = Track.duration

        # 排序方向
        if sort_order == "asc":
            order_by_clause = sort_field.asc()
        else:
            order_by_clause = sort_field.desc()

        # 获取列表
        result = await db.execute(
            select(Track)
            .where(and_(*conditions))
            .order_by(order_by_clause)
            .offset(skip)
            .limit(limit)
        )
        tracks = list(result.scalars().all())

        return tracks, total

    def _calculate_speed(self, current_time, prev_time, distance_m: float) -> Optional[float]:
        """
        计算速度 (m/s)

        Args:
            current_time: 当前点的时间
            prev_time: 前一个点的时间
            distance_m: 两点之间的距离（米）

        Returns:
            速度（米/秒），如果无法计算则返回 None
        """
        if not current_time or not prev_time:
            return None

        time_diff = (current_time - prev_time).total_seconds()
        if time_diff <= 0:
            return None

        speed = distance_m / time_diff
        # 如果速度异常（超过 200 km/h），返回 None
        if speed > 55.56:  # 200 km/h = 55.56 m/s
            return None

        return round(speed, 2)

    def _calculate_bearing(self, lat1: float, lon1: float, lat2: float, lon2: float) -> Optional[float]:
        """
        计算从点1到点2的方位角（度）

        Args:
            lat1, lon1: 第一个点的纬度和经度（度）
            lat2, lon2: 第二个点的纬度和经度（度）

        Returns:
            方位角（度），范围 [0, 360)，如果两点重合则返回 None
        """
        from math import radians, degrees, atan2, sin, cos, pi

        # 转换为弧度
        lat1_rad = radians(lat1)
        lon1_rad = radians(lon1)
        lat2_rad = radians(lat2)
        lon2_rad = radians(lon2)

        dlon = lon2_rad - lon1_rad

        # 计算方位角
        x = sin(dlon) * cos(lat2_rad)
        y = cos(lat1_rad) * sin(lat2_rad) - sin(lat1_rad) * cos(lat2_rad) * cos(dlon)

        bearing = atan2(x, y)
        bearing_deg = degrees(bearing)

        # 转换到 [0, 360) 范围
        if bearing_deg < 0:
            bearing_deg += 360

        # 检查两点是否重合（方位角无意义）
        if abs(lat1 - lat2) < 1e-9 and abs(lon1 - lon2) < 1e-9:
            return None

        return round(bearing_deg, 2)

    async def create_from_gpx(
        self,
        db: AsyncSession,
        user: User,
        filename: str,
        gpx_content: str,
        name: str,
        description: Optional[str] = None,
        original_crs: CoordinateType = 'wgs84',
        convert_to: Optional[CoordinateType] = None,
        fill_geocoding: bool = False,
    ) -> Track:
        """
        从 GPX 内容创建轨迹

        Args:
            db: 数据库会话
            user: 用户对象
            filename: 原始文件名
            gpx_content: GPX 文件内容
            name: 轨迹名称
            description: 轨迹描述
            original_crs: 原始坐标系
            convert_to: 转换到目标坐标系
            fill_geocoding: 是否填充行政区划和道路信息

        Returns:
            创建的轨迹对象
        """
        # 解析 GPX
        gpx = gpxpy.parse(gpx_content)

        if not gpx.tracks:
            raise ValueError("GPX 文件中没有轨迹数据")

        # 获取第一个轨迹的第一段
        track = gpx.tracks[0]
        segment = track.segments[0]

        if not segment.points:
            raise ValueError("GPX 文件中没有轨迹点")

        # 计算统计信息
        total_distance = 0
        elevation_gain = 0
        elevation_loss = 0
        prev_elevation = None
        start_time = None
        end_time = None

        points_data = []
        prev_point_data = None

        for idx, point in enumerate(segment.points):
            # 时间
            if point.time:
                if start_time is None:
                    start_time = point.time
                end_time = point.time

            # 坐标转换
            all_coords = convert_point_to_all(
                point.longitude,
                point.latitude,
                original_crs
            )

            # 海拔变化
            if point.elevation is not None:
                if prev_elevation is not None:
                    diff = point.elevation - prev_elevation
                    if diff > 0:
                        elevation_gain += diff
                    else:
                        elevation_loss += abs(diff)
                prev_elevation = point.elevation

            # 计算距离和速度
            distance_from_prev = 0
            speed = None
            if idx > 0 and prev_point_data:
                # 使用 WGS84 坐标计算 3D 距离
                from math import sqrt, radians, sin, cos, atan2

                lat1 = radians(prev_point_data['latitude_wgs84'])
                lon1 = radians(prev_point_data['longitude_wgs84'])
                lat2 = radians(all_coords['wgs84'][1])
                lon2 = radians(all_coords['wgs84'][0])

                # Haversine 公式计算水平距离
                dlat = lat2 - lat1
                dlon = lon2 - lon1
                a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
                c = 2 * atan2(sqrt(a), sqrt(1 - a))
                horizontal_distance = 6371000 * c  # 地球半径 6371km

                # 计算垂直距离
                elev1 = prev_point_data.get('elevation') or 0
                elev2 = point.elevation or 0
                vertical_distance = elev2 - elev1

                # 3D 距离
                distance_from_prev = sqrt(horizontal_distance ** 2 + vertical_distance ** 2)
                total_distance += distance_from_prev

                # 计算速度
                speed = self._calculate_speed(point.time, prev_point_data['time'], distance_from_prev)

                # 计算方位角
                bearing = self._calculate_bearing(
                    prev_point_data['latitude_wgs84'],
                    prev_point_data['longitude_wgs84'],
                    all_coords['wgs84'][1],
                    all_coords['wgs84'][0]
                )

            point_data = {
                'point_index': idx,
                'time': point.time,
                'latitude_wgs84': all_coords['wgs84'][1],
                'longitude_wgs84': all_coords['wgs84'][0],
                'latitude_gcj02': all_coords['gcj02'][1],
                'longitude_gcj02': all_coords['gcj02'][0],
                'latitude_bd09': all_coords['bd09'][1],
                'longitude_bd09': all_coords['bd09'][0],
                'elevation': point.elevation,
                'speed': speed,
                'bearing': bearing if idx > 0 else None,  # 第一个点没有方位角
            }
            points_data.append(point_data)
            prev_point_data = point_data

        # 计算时长（秒）
        duration = 0
        if start_time and end_time:
            duration = int((end_time - start_time).total_seconds())

        # 创建轨迹记录，带审计字段
        track_obj = Track(
            user_id=user.id,
            name=name,
            description=description,
            original_filename=filename,
            original_crs=original_crs,
            distance=round(total_distance, 2),
            duration=duration,
            elevation_gain=round(elevation_gain, 2),
            elevation_loss=round(elevation_loss, 2),
            start_time=start_time,
            end_time=end_time,
            has_area_info=False,
            has_road_info=False,
            created_by=user.id,
            updated_by=user.id,
            is_valid=True,
        )
        db.add(track_obj)
        await db.flush()  # 获取 track_id

        # 批量创建轨迹点
        insert_values = []
        for point_data in points_data:
            insert_values.append({
                "track_id": track_obj.id,
                "point_index": point_data["point_index"],
                "time": point_data["time"],
                "latitude_wgs84": point_data["latitude_wgs84"],
                "longitude_wgs84": point_data["longitude_wgs84"],
                "latitude_gcj02": point_data["latitude_gcj02"],
                "longitude_gcj02": point_data["longitude_gcj02"],
                "latitude_bd09": point_data["latitude_bd09"],
                "longitude_bd09": point_data["longitude_bd09"],
                "elevation": point_data["elevation"],
                "speed": point_data["speed"],
                "bearing": point_data["bearing"],
                "province": None,
                "city": None,
                "district": None,
                "province_en": None,
                "city_en": None,
                "district_en": None,
                "road_name": None,
                "road_number": None,
                "road_name_en": None,
                "created_by": user.id,
                "updated_by": user.id,
                "is_valid": True,
            })

        # 分批插入，每批 500 条
        batch_size = 500
        for i in range(0, len(insert_values), batch_size):
            batch = insert_values[i:i + batch_size]
            try:
                await db.execute(
                    TrackPoint.__table__.insert().values(batch)
                )
            except Exception as e:
                logger.error(f"Error inserting batch {i//batch_size}: {e}")
                raise

        await db.commit()
        await db.refresh(track_obj)

        # 异步填充地理信息（如果启用）
        if fill_geocoding:
            task = asyncio.create_task(
                self.fill_geocoding_info(db, track_obj.id, user.id)
            )
            task.add_done_callback(self._background_tasks.discard)
            self._background_tasks.add(task)

        return track_obj

    def get_fill_progress(self, track_id: int) -> dict:
        """获取地理信息填充进度"""
        return self._filling_progress.get(track_id, {"current": 0, "total": 0, "status": "idle"})

    async def fill_geocoding_info(
        self,
        db: AsyncSession,
        track_id: int,
        user_id: int,
    ):
        """
        填充行政区划和道路信息（合并功能）

        Args:
            db: 数据库会话
            track_id: 轨迹 ID
            user_id: 用户 ID
        """
        # 使用新的会话，因为原会话可能已关闭
        from app.core.database import async_session_maker

        logger.info(f"Starting geocoding fill for track {track_id}")

        async with async_session_maker() as db:
            try:
                # 获取轨迹点
                result = await db.execute(
                    select(TrackPoint)
                    .where(and_(TrackPoint.track_id == track_id, TrackPoint.is_valid == True))
                    .order_by(TrackPoint.point_index)
                )
                points = result.scalars().all()

                if not points:
                    logger.warning(f"No points found for track {track_id}")
                    return

                total_points = len(points)
                logger.info(f"Found {total_points} points for track {track_id}")

                # 初始化进度
                self._filling_progress[track_id] = {
                    "current": 0,
                    "total": total_points,
                    "status": "filling"
                }

                # 获取地理编码服务
                geocoding_service = await self._get_geocoding_service(db)
                if not geocoding_service:
                    logger.warning(f"Geocoding service not configured for track {track_id}")
                    self._filling_progress[track_id]["status"] = "failed"
                    self._filling_progress[track_id]["error"] = "Geocoding service not configured"
                    return

                logger.info(f"Geocoding service acquired: {type(geocoding_service).__name__}")

                updated_count = 0
                for idx, point in enumerate(points):
                    try:
                        lat = point.latitude_wgs84
                        lon = point.longitude_wgs84
                        info = await geocoding_service.get_point_info(lat, lon)

                        # 同时填充行政区划和道路信息
                        point.province = info.get('province', '')
                        point.city = info.get('city', '')
                        point.district = info.get('area', '')
                        point.road_name = info.get('road_name', '')
                        point.road_number = info.get('road_num', '')
                        # 英文字段
                        point.province_en = info.get('province_en', '')
                        point.city_en = info.get('city_en', '')
                        point.district_en = info.get('area_en', '')
                        point.road_name_en = info.get('road_name_en', '')

                        # 更新审计字段
                        point.updated_by = user_id

                        updated_count += 1

                        # 更新进度
                        self._filling_progress[track_id]["current"] = idx + 1

                        # 每次请求后短暂延迟，避免过载
                        await asyncio.sleep(0.2)

                    except Exception as e:
                        logger.error(f"Error getting geocoding for point {idx}: {e}")

                # 更新轨迹标记
                track_result = await db.execute(
                    select(Track).where(Track.id == track_id)
                )
                track = track_result.scalar_one_or_none()
                if track:
                    track.has_area_info = True
                    track.has_road_info = True
                    track.updated_by = user_id

                await db.commit()

                # 标记完成
                self._filling_progress[track_id]["status"] = "completed"
                logger.info(f"Geocoding info filled for track {track_id}, updated {updated_count} points")

            except Exception as e:
                logger.error(f"Error filling geocoding info for track {track_id}: {e}")
                self._filling_progress[track_id]["status"] = "failed"
                self._filling_progress[track_id]["error"] = str(e)
                await db.rollback()

    async def update(self, db: AsyncSession, track: Track, update_data, user_id: int) -> Track:
        """更新轨迹信息（名称和描述）"""
        update_dict = update_data.model_dump(exclude_unset=True)

        if update_dict:
            for field, value in update_dict.items():
                setattr(track, field, value)

            track.updated_by = user_id
            track.updated_at = datetime.now(timezone.utc)

            await db.commit()
            await db.refresh(track)

        return track

    async def delete(self, db: AsyncSession, track: Track, user_id: int) -> None:
        """软删除轨迹"""
        track.is_valid = False
        track.updated_by = user_id
        track.updated_at = datetime.now(timezone.utc)

        # 同时软删除所有轨迹点
        await db.execute(
            update(TrackPoint)
            .where(TrackPoint.track_id == track.id)
            .values(
                is_valid=False,
                updated_by=user_id,
                updated_at=datetime.now(timezone.utc)
            )
        )

        await db.commit()

    async def get_stats(self, db: AsyncSession, user_id: int) -> dict:
        """获取用户的轨迹统计"""
        result = await db.execute(
            select(
                func.count(Track.id).label('total_tracks'),
                func.sum(Track.distance).label('total_distance'),
                func.sum(Track.duration).label('total_duration'),
                func.sum(Track.elevation_gain).label('total_elevation_gain'),
            ).where(and_(Track.user_id == user_id, Track.is_valid == True))
        )
        row = result.one()

        return {
            'total_tracks': row.total_tracks or 0,
            'total_distance': row.total_distance or 0,
            'total_duration': row.total_duration or 0,
            'total_elevation_gain': row.total_elevation_gain or 0,
        }

    async def get_points(
        self,
        db: AsyncSession,
        track_id: int,
        user_id: int,
        crs: CoordinateType = 'wgs84',
    ) -> List[TrackPoint]:
        """
        获取轨迹点数据

        Args:
            db: 数据库会话
            track_id: 轨迹 ID
            user_id: 用户 ID
            crs: 返回的坐标系

        Returns:
            轨迹点列表
        """
        # 检查权限
        track = await self.get_by_id(db, track_id, user_id)
        if not track:
            return []

        # 获取轨迹点
        result = await db.execute(
            select(TrackPoint)
            .where(and_(TrackPoint.track_id == track_id, TrackPoint.is_valid == True))
            .order_by(TrackPoint.point_index)
        )
        return list(result.scalars().all())

    async def update_bearings_for_track(
        self,
        db: AsyncSession,
        track_id: int,
        user_id: int,
    ) -> dict:
        """
        为指定轨迹的所有点计算并更新方位角

        Args:
            db: 数据库会话
            track_id: 轨迹 ID
            user_id: 用户 ID

        Returns:
            更新结果 {"updated": 更新的点数, "total": 总点数}
        """
        # 检查权限
        track = await self.get_by_id(db, track_id, user_id)
        if not track:
            raise ValueError("轨迹不存在")

        # 获取所有轨迹点，按 point_index 排序
        result = await db.execute(
            select(TrackPoint)
            .where(and_(TrackPoint.track_id == track_id, TrackPoint.is_valid == True))
            .order_by(TrackPoint.point_index)
        )
        points = list(result.scalars().all())

        if not points:
            return {"updated": 0, "total": 0}

        updated_count = 0
        prev_point = None

        for point in points:
            # 第一个点没有方位角
            if prev_point is None:
                point.bearing = None
            else:
                # 计算从前一个点到当前点的方位角
                bearing = self._calculate_bearing(
                    prev_point.latitude_wgs84,
                    prev_point.longitude_wgs84,
                    point.latitude_wgs84,
                    point.longitude_wgs84
                )
                point.bearing = bearing
                updated_count += 1

            point.updated_by = user_id
            prev_point = point

        await db.commit()

        logger.info(f"Updated bearings for track {track_id}: {updated_count}/{len(points)} points")

        return {"updated": updated_count, "total": len(points)}

    async def update_bearings_for_all_tracks(
        self,
        db: AsyncSession,
    ) -> dict:
        """
        为所有现有轨迹计算并更新方位角

        Args:
            db: 数据库会话

        Returns:
            更新结果 {"updated_tracks": 更新的轨迹数, "updated_points": 更新的点数, "total_tracks": 总轨迹数}
        """
        # 获取所有有效轨迹
        result = await db.execute(
            select(Track).where(Track.is_valid == True)
        )
        tracks = list(result.scalars().all())

        updated_tracks = 0
        updated_points = 0

        for track in tracks:
            try:
                # 获取轨迹的所有点
                points_result = await db.execute(
                    select(TrackPoint)
                    .where(and_(TrackPoint.track_id == track.id, TrackPoint.is_valid == True))
                    .order_by(TrackPoint.point_index)
                )
                points = list(points_result.scalars().all())

                if not points:
                    continue

                prev_point = None
                for point in points:
                    if prev_point is None:
                        point.bearing = None
                    else:
                        bearing = self._calculate_bearing(
                            prev_point.latitude_wgs84,
                            prev_point.longitude_wgs84,
                            point.latitude_wgs84,
                            point.longitude_wgs84
                        )
                        point.bearing = bearing
                        updated_points += 1

                    point.updated_by = track.user_id
                    prev_point = point

                updated_tracks += 1

                # 每处理一个轨迹提交一次
                await db.commit()

                logger.info(f"Updated bearings for track {track.id} ({track.name})")

            except Exception as e:
                logger.error(f"Error updating bearings for track {track.id}: {e}")
                await db.rollback()

        logger.info(f"Bearing update completed: {updated_tracks} tracks, {updated_points} points")

        return {
            "updated_tracks": updated_tracks,
            "updated_points": updated_points,
            "total_tracks": len(tracks)
        }


track_service = TrackService()
