"""
实时记录服务层
"""
import secrets
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.live_recording import LiveRecording
from app.models.track import Track, TrackPoint
from app.gpxutil_wrapper.coord_transform import convert_point_to_all, CoordinateType
from app.gpxutil_wrapper.geocoding import create_geocoding_service, GeocodingProvider
from app.core.config import settings
from loguru import logger


class LiveRecordingService:
    """实时记录服务类"""

    def __init__(self, spatial_service=None):
        """
        初始化服务

        Args:
            spatial_service: 空间计算服务实例，如果为 None 则使用默认的 Python 实现
        """
        from app.services.spatial import ISpatialService, PythonSpatialService

        self._geocoding_service = None
        self._geocoding_provider = None
        self._geocoding_config = None

        # 空间计算服务
        self.spatial_service: ISpatialService = spatial_service or PythonSpatialService()

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

    async def create(
        self,
        db: AsyncSession,
        user_id: int,
        name: str,
        description: str = None,
        fill_geocoding: bool = False,
    ) -> LiveRecording:
        """
        创建实时记录会话，同时创建关联的 Track

        Args:
            db: 数据库会话
            user_id: 用户 ID
            name: 记录名称
            description: 描述
            fill_geocoding: 上传点时是否自动填充地理信息

        Returns:
            创建的记录对象
        """
        from app.models.track import Track

        # 生成 64 位安全随机 token
        token = secrets.token_hex(32)

        # 先创建 Track
        track = Track(
            user_id=user_id,
            name=name,
            description=description,
            original_filename=f"live_recording_{token[:8]}",
            original_crs="wgs84",
            distance=0,
            duration=0,
            elevation_gain=0,
            elevation_loss=0,
            start_time=None,  # 第一个点到达时设置
            end_time=None,
            has_area_info=False,
            has_road_info=False,
            is_live_recording=True,  # 标记为实时记录轨迹
            created_by=user_id,
            updated_by=user_id,
            is_valid=True,
        )
        db.add(track)
        await db.flush()

        # 再创建 LiveRecording，关联到 Track
        recording = LiveRecording(
            user_id=user_id,
            token=token,
            name=name,
            description=description,
            status="active",
            track_count=0,
            current_track_id=track.id,  # 直接关联
            fill_geocoding=fill_geocoding,
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(recording)
        await db.commit()
        await db.refresh(recording)
        logger.info(f"Created live recording {recording.id} with track {track.id}")
        return recording

    async def get_by_id(self, db: AsyncSession, recording_id: int, user_id: int) -> Optional[LiveRecording]:
        """
        根据 ID 获取记录（仅属于指定用户）

        Args:
            db: 数据库会话
            recording_id: 记录 ID
            user_id: 用户 ID

        Returns:
            记录对象或 None
        """
        result = await db.execute(
            select(LiveRecording).where(
                and_(
                    LiveRecording.id == recording_id,
                    LiveRecording.user_id == user_id,
                    LiveRecording.is_valid == True
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_token(self, db: AsyncSession, token: str) -> Optional[LiveRecording]:
        """
        根据 token 获取记录

        Args:
            db: 数据库会话
            token: 记录 token

        Returns:
            记录对象或 None
        """
        result = await db.execute(
            select(LiveRecording).where(
                and_(
                    LiveRecording.token == token,
                    LiveRecording.is_valid == True
                )
            )
        )
        recording = result.scalar_one_or_none()
        if recording:
            logger.info(f"get_by_token: Found recording {recording.id} with current_track_id={recording.current_track_id}")
        else:
            logger.warning(f"get_by_token: No recording found for token={token[:8]}...")
        return recording

    async def get_list(
        self,
        db: AsyncSession,
        user_id: int,
        status: Optional[str] = None,
    ) -> List[LiveRecording]:
        """
        获取用户的记录列表

        Args:
            db: 数据库会话
            user_id: 用户 ID
            status: 状态筛选（active/ended）

        Returns:
            记录列表
        """
        conditions = [
            LiveRecording.user_id == user_id,
            LiveRecording.is_valid == True
        ]

        if status:
            conditions.append(LiveRecording.status == status)

        result = await db.execute(
            select(LiveRecording)
            .where(and_(*conditions))
            .order_by(desc(LiveRecording.created_at))
        )
        return list(result.scalars().all())

    async def end(self, db: AsyncSession, recording: LiveRecording) -> LiveRecording:
        """
        结束记录会话

        结束时会自动修复 point_index（按时间顺序重新分配），
        确保距离计算和后续操作正确。

        Args:
            db: 数据库会话
            recording: 记录对象

        Returns:
            更新后的记录对象
        """
        recording.status = "ended"
        recording.ended_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()
        await db.refresh(recording)

        # 自动修复 point_index
        try:
            fix_result = await self.fix_point_index(db, recording.track_id)
            logger.info(
                f"Recording {recording.id}: 自动修复 point_index 完成 - "
                f"{fix_result.get('status')}: {fix_result.get('message', '')}"
            )
        except Exception as e:
            logger.error(f"Recording {recording.id}: 修复 point_index 失败: {e}")

        return recording

    async def increment_track_count(self, db: AsyncSession, recording: LiveRecording) -> LiveRecording:
        """
        增加轨迹计数并更新最后上传时间

        Args:
            db: 数据库会话
            recording: 记录对象

        Returns:
            更新后的记录对象
        """
        recording.track_count += 1
        recording.last_upload_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await db.commit()
        await db.refresh(recording)
        return recording

    async def add_point_to_recording(
        self,
        db: AsyncSession,
        recording: LiveRecording,
        lat: float,
        lon: float,
        time: Optional[int] = None,
        elevation: Optional[float] = None,
        speed: Optional[float] = None,
        accuracy: Optional[float] = None,
        satellites: Optional[int] = None,
        bearing: Optional[float] = None,
        original_crs: CoordinateType = 'wgs84',
    ) -> dict:
        """
        向实时记录添加单个轨迹点

        由于创建 LiveRecording 时已关联 Track，此方法不再创建新 Track。

        Args:
            db: 数据库会话
            recording: 记录对象
            lat: 纬度
            lon: 经度
            time: 时间戳（毫秒）
            elevation: 海拔（米）
            speed: 速度（m/s）
            accuracy: 精度（米）
            satellites: 卫星数量
            bearing: 方位角（度）
            original_crs: 原始坐标系

        Returns:
            包含点信息的字典
        """
        # 检查记录状态
        if recording.status != "active":
            raise ValueError("记录已结束，无法添加点")

        # 获取关联的 Track
        if not recording.current_track_id:
            raise ValueError("记录未关联到任何轨迹，数据异常")

        result = await db.execute(
            select(Track).where(
                and_(
                    Track.id == recording.current_track_id,
                    Track.is_valid == True
                )
            )
        )
        track = result.scalar_one_or_none()
        if not track:
            raise ValueError(f"关联的轨迹 {recording.current_track_id} 不存在或已删除")

        logger.info(f"Recording {recording.id}: using track {track.id}")

        # 转换时间（毫秒 -> 秒）
        point_time = None
        if time is not None:
            point_time = datetime.fromtimestamp(time / 1000, tz=timezone.utc)

        # 坐标转换
        all_coords = convert_point_to_all(lon, lat, original_crs)

        # 获取最后一个点（按时间排序，而非 point_index）
        # 实时上传场景下，点可能乱序到达，必须按实际时间顺序处理
        last_point_result = await db.execute(
            select(TrackPoint)
            .where(
                and_(
                    TrackPoint.track_id == track.id,
                    TrackPoint.is_valid == True
                )
            )
            .order_by(TrackPoint.time.desc(), TrackPoint.created_at.desc())
            .limit(1)
        )
        last_point = last_point_result.scalar_one_or_none()

        # 计算点索引
        # 策略：使用 MAX(point_index) + 1
        # 注意：这在高并发场景下仍有极小概率冲突，但SQLite的行级锁会自动处理
        # 如果发生冲突，数据库会抛出异常，客户端可以重试
        max_index_result = await db.execute(
            select(func.max(TrackPoint.point_index))
            .where(
                and_(
                    TrackPoint.track_id == track.id,
                    TrackPoint.is_valid == True
                )
            )
        )
        max_index = max_index_result.scalar()
        point_index = 0 if max_index is None else max_index + 1

        # 计算方位角、速度和距离
        calculated_bearing = bearing
        calculated_speed = speed
        distance_from_prev = 0.0

        if last_point:
            # 计算方位角
            if bearing is None:
                calculated_bearing = self._calculate_bearing(
                    last_point.latitude_wgs84,
                    last_point.longitude_wgs84,
                    all_coords['wgs84'][1],
                    all_coords['wgs84'][0]
                )

            # 计算距离和速度
            distance_from_prev = await self.spatial_service.distance(
                last_point.latitude_wgs84, last_point.longitude_wgs84,
                all_coords['wgs84'][1], all_coords['wgs84'][0]
            )

            # 计算速度（如果未提供）
            if speed is None and point_time and last_point.time:
                # 确保两个时间都是带时区的，以便比较
                last_time = last_point.time
                if last_time.tzinfo is None:
                    last_time = last_time.replace(tzinfo=timezone.utc)
                if point_time.tzinfo is None:
                    point_time_compare = point_time.replace(tzinfo=timezone.utc)
                else:
                    point_time_compare = point_time

                time_diff = (point_time_compare - last_time).total_seconds()
                if time_diff > 0:
                    calculated_speed = distance_from_prev / time_diff
                    # 限制最大速度
                    if calculated_speed > 55.56:  # 200 km/h
                        calculated_speed = None

            # 注意：不在添加点时累加距离，因为乱序到达会导致累积误差
            # 距离会在查询时通过 get_track_with_calculated_stats() 实时计算

            # 计算爬升/下降（同样会有误差，但影响较小，结束后会统一修复）
            if elevation is not None and last_point.elevation is not None:
                elevation_diff = elevation - last_point.elevation
                if elevation_diff > 0:
                    track.elevation_gain = round(track.elevation_gain + elevation_diff, 2)
                else:
                    track.elevation_loss = round(track.elevation_loss + abs(elevation_diff), 2)

        # 创建轨迹点（去除时区信息，数据库使用不带时区的 TIMESTAMP）
        point = TrackPoint(
            track_id=track.id,
            point_index=point_index,
            time=point_time.replace(tzinfo=None) if point_time else None,
            latitude_wgs84=all_coords['wgs84'][1],
            longitude_wgs84=all_coords['wgs84'][0],
            latitude_gcj02=all_coords['gcj02'][1],
            longitude_gcj02=all_coords['gcj02'][0],
            latitude_bd09=all_coords['bd09'][1],
            longitude_bd09=all_coords['bd09'][0],
            elevation=elevation,
            speed=calculated_speed,
            bearing=calculated_bearing,
            created_by=recording.user_id,
            updated_by=recording.user_id,
            is_valid=True,
        )
        db.add(point)
        await db.flush()

        # 更新轨迹统计
        if point_time:
            # 确保 point_time 不带时区（与数据库中的时间一致）
            point_time_naive = point_time.replace(tzinfo=None)

            if track.start_time is None or point_time_naive < track.start_time:
                track.start_time = point_time_naive
            if track.end_time is None or point_time_naive > track.end_time:
                track.end_time = point_time_naive

            # 更新时长
            if track.start_time and track.end_time:
                track.duration = int((track.end_time - track.start_time).total_seconds())

        # 自动填充地理信息（如果启用）
        if recording.fill_geocoding:
            try:
                geo_service = await self._get_geocoding_service(db)
                if geo_service:
                    # get_point_info 参数顺序是 (lat, lon)，all_coords['gcj02'] 格式是 [lon, lat]
                    geo_info = await geo_service.get_point_info(all_coords['gcj02'][1], all_coords['gcj02'][0])
                    if geo_info:
                        # 字段映射要与 track_service.py 一致：district <- area, road_number <- road_num
                        point.province = geo_info.get('province', '')
                        point.city = geo_info.get('city', '')
                        point.district = geo_info.get('area', '')
                        point.province_en = geo_info.get('province_en', '')
                        point.city_en = geo_info.get('city_en', '')
                        point.district_en = geo_info.get('area_en', '')
                        point.road_name = geo_info.get('road_name', '')
                        point.road_number = geo_info.get('road_num', '')
                        point.road_name_en = geo_info.get('road_name_en', '')
                        # 更新轨迹的地理信息标记
                        if point.province or point.city:
                            track.has_area_info = True
                        if point.road_name or point.road_number:
                            track.has_road_info = True
            except Exception as e:
                logger.warning(f"Failed to fill geocoding for point {point_index}: {e}")

        # 更新记录的最后上传时间
        recording.last_upload_at = datetime.now(timezone.utc).replace(tzinfo=None)

        await db.commit()
        # 刷新 recording 对象，确保 current_track_id 已正确设置
        await db.refresh(recording)
        logger.info(f"After commit: recording {recording.id} current_track_id={recording.current_track_id}")
        await db.refresh(point)

        # 通过 WebSocket 通知订阅的客户端
        try:
            from app.api.websocket import notify_point_added
            # 准备点数据（时间添加 UTC 时区后缀）
            time_str = None
            if point.time:
                if point.time.tzinfo is not None:
                    time_str = point.time.isoformat()
                else:
                    # 数据库存储的是 naive datetime，约定为 UTC 时间
                    time_str = point.time.isoformat() + "+00:00"

            point_data = {
                "id": point.id,
                "point_index": point.point_index,
                "latitude": point.latitude_wgs84,
                "longitude": point.longitude_wgs84,
                "latitude_wgs84": point.latitude_wgs84,
                "longitude_wgs84": point.longitude_wgs84,
                "latitude_gcj02": point.latitude_gcj02,
                "longitude_gcj02": point.longitude_gcj02,
                "latitude_bd09": point.latitude_bd09,
                "longitude_bd09": point.longitude_bd09,
                "elevation": point.elevation,
                "speed": point.speed,
                "time": time_str,
                "created_at": point.created_at.isoformat() + "+00:00",
                # 地理信息
                "province": point.province,
                "city": point.city,
                "district": point.district,
                "road_name": point.road_name,
                "road_number": point.road_number,
                "province_en": point.province_en,
                "city_en": point.city_en,
                "district_en": point.district_en,
                "road_name_en": point.road_name_en,
            }
            # 准备统计信息
            stats_data = {
                "distance": track.distance,
                "duration": track.duration,
                "elevation_gain": track.elevation_gain,
                "elevation_loss": track.elevation_loss,
            }
            # 异步通知（不阻塞当前请求）
            import asyncio
            asyncio.create_task(notify_point_added(
                recording_id=recording.id,
                track_id=track.id,
                point_data=point_data,
                stats_data=stats_data
            ))
        except ImportError:
            # WebSocket 模块可能未加载
            pass
        except Exception as e:
            logger.warning(f"Failed to send WebSocket notification: {e}")

        logger.info(
            f"Added point {point_index} to track {track.id} for recording {recording.id}: "
            f"lat={lat:.6f}, lon={lon:.6f}, distance={distance_from_prev:.2f}m"
        )

        return {
            "success": True,
            "point_id": point.id,
            "track_id": track.id,
            "recording_id": recording.id,
            "point_index": point_index,
            "calculated_speed": calculated_speed,
            "calculated_bearing": calculated_bearing,
            "distance_from_prev": round(distance_from_prev, 2) if distance_from_prev else None,
        }

    def _calculate_bearing(self, lat1: float, lon1: float, lat2: float, lon2: float) -> Optional[float]:
        """
        计算从点1到点2的方位角（度）

        Args:
            lat1, lon1: 第一个点的纬度和经度（度）
            lat2, lon2: 第二个点的纬度和经度（度）

        Returns:
            方位角（度），范围 [0, 360)，如果两点重合则返回 None
        """
        from math import radians, degrees, atan2, sin, cos

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

    async def recalculate_track_stats(self, db: AsyncSession, track_id: int) -> dict:
        """
        重新计算轨迹的爬升/下降统计

        Args:
            db: 数据库会话
            track_id: 轨迹ID

        Returns:
            包含更新后统计信息的字典
        """
        # 获取轨迹
        result = await db.execute(
            select(Track).where(
                and_(
                    Track.id == track_id,
                    Track.is_valid == True
                )
            )
        )
        track = result.scalar_one_or_none()
        if not track:
            raise ValueError(f"轨迹 {track_id} 不存在")

        # 获取所有有效点，按时间排序（实时记录场景下 point_index 可能不准确）
        points_result = await db.execute(
            select(TrackPoint)
            .where(
                and_(
                    TrackPoint.track_id == track_id,
                    TrackPoint.is_valid == True,
                    TrackPoint.elevation.is_not(None)
                )
            )
            .order_by(TrackPoint.time.asc(), TrackPoint.created_at.asc())
        )
        points = points_result.scalars().all()

        if len(points) < 2:
            return {
                "track_id": track_id,
                "elevation_gain": track.elevation_gain,
                "elevation_loss": track.elevation_loss,
                "message": "轨迹点少于2个，无法计算"
            }

        # 计算爬升/下降
        elevation_gain = 0.0
        elevation_loss = 0.0
        prev_elevation = points[0].elevation

        for point in points[1:]:
            if point.elevation is not None:
                diff = point.elevation - prev_elevation
                if diff > 0:
                    elevation_gain += diff
                else:
                    elevation_loss += abs(diff)
                prev_elevation = point.elevation

        # 更新轨迹
        track.elevation_gain = round(elevation_gain, 2)
        track.elevation_loss = round(elevation_loss, 2)
        await db.commit()

        logger.info(f"Recalculated elevation stats for track {track_id}: gain={elevation_gain}, loss={elevation_loss}")

        return {
            "track_id": track_id,
            "elevation_gain": track.elevation_gain,
            "elevation_loss": track.elevation_loss,
        }

    async def fix_point_index(
        self,
        db: AsyncSession,
        track_id: int,
    ) -> dict:
        """
        修复轨迹的 point_index（按时间顺序重新分配）

        实时记录场景下，点可能乱序到达，导致 point_index 不连续或不正确。
        此方法按 GPS 时间重新排序并分配连续的索引，同时重新计算距离和爬升统计。

        Args:
            db: 数据库会话
            track_id: 轨迹 ID

        Returns:
            修复结果字典
        """
        # 获取所有点，按 time 排序（GPS 时间是轨迹的真正顺序）
        points_result = await db.execute(
            select(TrackPoint)
            .where(
                and_(
                    TrackPoint.track_id == track_id,
                    TrackPoint.is_valid == True
                )
            )
            .order_by(TrackPoint.time.asc(), TrackPoint.created_at.asc())
        )
        points = points_result.scalars().all()

        if not points:
            return {
                "track_id": track_id,
                "status": "skipped",
                "message": "没有找到轨迹点"
            }

        # 检查是否需要修复
        needs_fix = False
        for i, point in enumerate(points):
            if point.point_index != i:
                needs_fix = True
                break

        if not needs_fix:
            logger.info(f"Track {track_id}: point_index 已正确，无需修复")
            return {
                "track_id": track_id,
                "status": "ok",
                "message": "point_index 已正确",
                "point_count": len(points)
            }

        # 重新分配 point_index
        logger.info(f"Track {track_id}: 开始修复 {len(points)} 个点的 point_index")
        updated_count = 0
        for i, point in enumerate(points):
            if point.point_index != i:
                point.point_index = i
                point.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                updated_count += 1

        # 重新计算距离和爬升
        total_distance = 0.0
        total_duration = 0
        elevation_gain = 0.0
        elevation_loss = 0.0

        if len(points) >= 2:
            for i in range(1, len(points)):
                prev_point = points[i - 1]
                curr_point = points[i]

                # 计算距离
                if curr_point.latitude_wgs84 and curr_point.longitude_wgs84:
                    distance = await self.spatial_service.distance(
                        prev_point.latitude_wgs84, prev_point.longitude_wgs84,
                        curr_point.latitude_wgs84, curr_point.longitude_wgs84
                    )
                    total_distance += distance

                # 计算爬升/下降
                if curr_point.elevation is not None and prev_point.elevation is not None:
                    diff = curr_point.elevation - prev_point.elevation
                    if diff > 0:
                        elevation_gain += diff
                    else:
                        elevation_loss += abs(diff)

            # 计算时长
            first_point = points[0]
            last_point = points[-1]
            if first_point.time and last_point.time:
                total_duration = int((last_point.time - first_point.time).total_seconds())

        # 更新轨迹统计
        track_result = await db.execute(
            select(Track).where(
                and_(
                    Track.id == track_id,
                    Track.is_valid == True
                )
            )
        )
        track = track_result.scalar_one_or_none()
        if track:
            old_distance = track.distance
            track.distance = round(total_distance, 2)
            track.duration = total_duration
            track.elevation_gain = round(elevation_gain, 2)
            track.elevation_loss = round(elevation_loss, 2)

            logger.info(f"Track {track_id}: 距离从 {old_distance:.2f}m 更新为 {track.distance:.2f}m")

        await db.commit()

        logger.info(f"Track {track_id}: 已修复 {updated_count} 个点")

        return {
            "track_id": track_id,
            "status": "fixed",
            "point_count": len(points),
            "updated_count": updated_count,
            "old_distance": old_distance if track else None,
            "new_distance": track.distance if track else None,
        }

    async def delete(self, db: AsyncSession, recording: LiveRecording) -> None:
        """
        删除记录（软删除）

        Args:
            db: 数据库会话
            recording: 记录对象
        """
        recording.is_valid = False
        recording.updated_by = recording.user_id
        await db.commit()

    async def update_fill_geocoding(
        self,
        db: AsyncSession,
        recording: LiveRecording,
        fill_geocoding: bool,
    ) -> LiveRecording:
        """
        更新自动填充地理信息设置

        Args:
            db: 数据库会话
            recording: 记录对象
            fill_geocoding: 是否自动填充地理信息

        Returns:
            更新后的记录对象
        """
        recording.fill_geocoding = fill_geocoding
        await db.commit()
        await db.refresh(recording)
        return recording

    async def get_last_point_time(self, db: AsyncSession, recording: LiveRecording) -> Optional[datetime]:
        """
        获取记录中最近一次上传的轨迹点的 GPS 时间

        Args:
            db: 数据库会话
            recording: 记录对象

        Returns:
            最近一次轨迹点的 GPS 时间（time 字段），如果没有点则返回 None
        """
        if not recording.current_track_id:
            return None

        # 直接按 created_at 降序获取最新的点
        last_point_result = await db.execute(
            select(TrackPoint)
            .where(
                and_(
                    TrackPoint.track_id == recording.current_track_id,
                    TrackPoint.is_valid == True
                )
            )
            .order_by(TrackPoint.created_at.desc())
            .limit(1)
        )
        last_point = last_point_result.scalar_one_or_none()

        return last_point.time if last_point else None

    async def get_last_point_created_at(self, db: AsyncSession, recording: LiveRecording) -> Optional[datetime]:
        """
        获取记录中最近一次上传的轨迹点的服务器接收时间

        Args:
            db: 数据库会话
            recording: 记录对象

        Returns:
            最近一次轨迹点的服务器接收时间（created_at 字段），如果没有点则返回 None
        """
        if not recording.current_track_id:
            return None

        # 直接按 created_at 降序获取最新的点
        last_point_result = await db.execute(
            select(TrackPoint)
            .where(
                and_(
                    TrackPoint.track_id == recording.current_track_id,
                    TrackPoint.is_valid == True
                )
            )
            .order_by(TrackPoint.created_at.desc())
            .limit(1)
        )
        last_point = last_point_result.scalar_one_or_none()

        return last_point.created_at if last_point else None

    async def calculate_track_stats_from_points(
        self,
        db: AsyncSession,
        track_id: int,
    ) -> dict:
        """
        从轨迹点实时计算统计信息（按时间排序）

        用于实时记录场景，确保统计数据的准确性，
        不依赖可能错误的累加值。

        Args:
            db: 数据库会话
            track_id: 轨迹 ID

        Returns:
            包含 distance, duration, elevation_gain, elevation_loss 的字典
        """
        # 获取所有点，按时间排序
        points_result = await db.execute(
            select(TrackPoint)
            .where(
                and_(
                    TrackPoint.track_id == track_id,
                    TrackPoint.is_valid == True
                )
            )
            .order_by(TrackPoint.time.asc(), TrackPoint.created_at.asc())
        )
        points = points_result.scalars().all()

        if len(points) < 2:
            return {
                "distance": 0.0,
                "duration": 0,
                "elevation_gain": 0.0,
                "elevation_loss": 0.0,
            }

        # 计算距离和爬升
        total_distance = 0.0
        elevation_gain = 0.0
        elevation_loss = 0.0

        for i in range(1, len(points)):
            prev_point = points[i - 1]
            curr_point = points[i]

            # 计算距离
            if curr_point.latitude_wgs84 and curr_point.longitude_wgs84:
                distance = await self.spatial_service.distance(
                    prev_point.latitude_wgs84, prev_point.longitude_wgs84,
                    curr_point.latitude_wgs84, curr_point.longitude_wgs84
                )
                total_distance += distance

            # 计算爬升/下降
            if curr_point.elevation is not None and prev_point.elevation is not None:
                diff = curr_point.elevation - prev_point.elevation
                if diff > 0:
                    elevation_gain += diff
                else:
                    elevation_loss += abs(diff)

        # 计算时长
        duration = 0
        first_point = points[0]
        last_point = points[-1]
        if first_point.time and last_point.time:
            duration = int((last_point.time - first_point.time).total_seconds())

        return {
            "distance": round(total_distance, 2),
            "duration": duration,
            "elevation_gain": round(elevation_gain, 2),
            "elevation_loss": round(elevation_loss, 2),
        }


live_recording_service = LiveRecordingService()
