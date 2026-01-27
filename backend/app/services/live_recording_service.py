"""
实时记录服务层
"""
import secrets
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.live_recording import LiveRecording
from app.models.track import Track, TrackPoint
from app.gpxutil_wrapper.coord_transform import convert_point_to_all, CoordinateType
from app.gpxutil_wrapper.geocoding import create_geocoding_service, GeocodingProvider
from loguru import logger


class LiveRecordingService:
    """实时记录服务类"""

    def __init__(self):
        """初始化服务"""
        self._geocoding_service = None
        self._geocoding_provider = None
        self._geocoding_config = None

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
        创建实时记录会话

        Args:
            db: 数据库会话
            user_id: 用户 ID
            name: 记录名称
            description: 描述
            fill_geocoding: 上传点时是否自动填充地理信息

        Returns:
            创建的记录对象
        """
        # 生成 64 位安全随机 token
        token = secrets.token_hex(32)

        recording = LiveRecording(
            user_id=user_id,
            token=token,
            name=name,
            description=description,
            status="active",
            track_count=0,
            fill_geocoding=fill_geocoding,
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(recording)
        await db.commit()
        await db.refresh(recording)
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

        Args:
            db: 数据库会话
            recording: 记录对象

        Returns:
            更新后的记录对象
        """
        recording.status = "ended"
        recording.ended_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(recording)
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
        recording.last_upload_at = datetime.now(timezone.utc)
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

        # 转换时间（毫秒 -> 秒）
        point_time = None
        if time is not None:
            point_time = datetime.fromtimestamp(time / 1000, tz=timezone.utc)

        # 获取或创建当前轨迹
        track = None
        logger.info(f"Recording {recording.id}: current_track_id={recording.current_track_id}")
        if recording.current_track_id:
            # 获取现有轨迹
            result = await db.execute(
                select(Track).where(
                    and_(
                        Track.id == recording.current_track_id,
                        Track.is_valid == True
                    )
                )
            )
            track = result.scalar_one_or_none()
            if track:
                logger.info(f"Found existing track {track.id} for recording {recording.id}")
            else:
                logger.warning(f"Recording {recording.id} has current_track_id={recording.current_track_id} but track not found or invalid")

        if not track:
            logger.info(f"Creating new track for recording {recording.id}")
            # 创建新轨迹
            # 将带时区的时间转换为不带时区的时间（与数据库一致）
            track_time = point_time.replace(tzinfo=None) if point_time else None

            track = Track(
                user_id=recording.user_id,
                name=recording.name,
                description=recording.description,
                original_filename=f"live_recording_{recording.id}",
                original_crs=original_crs,
                distance=0,
                duration=0,
                elevation_gain=0,
                elevation_loss=0,
                start_time=track_time,
                end_time=track_time,
                has_area_info=False,
                has_road_info=False,
                created_by=recording.user_id,
                updated_by=recording.user_id,
                is_valid=True,
            )
            db.add(track)
            await db.flush()

            # 更新记录的当前轨迹
            recording.current_track_id = track.id
            logger.info(f"Created new track {track.id} and set recording.current_track_id={recording.current_track_id}")

        # 坐标转换
        all_coords = convert_point_to_all(lon, lat, original_crs)

        # 获取最后一个点，用于计算
        last_point_result = await db.execute(
            select(TrackPoint)
            .where(
                and_(
                    TrackPoint.track_id == track.id,
                    TrackPoint.is_valid == True
                )
            )
            .order_by(TrackPoint.point_index.desc())
            .limit(1)
        )
        last_point = last_point_result.scalar_one_or_none()

        # 计算点索引
        point_index = 0
        if last_point:
            point_index = last_point.point_index + 1

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
            distance_from_prev = self._calculate_distance(
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

            # 更新轨迹总距离
            track.distance = round(track.distance + distance_from_prev, 2)

            # 计算爬升/下降
            if elevation is not None and last_point.elevation is not None:
                elevation_diff = elevation - last_point.elevation
                if elevation_diff > 0:
                    track.elevation_gain = round(track.elevation_gain + elevation_diff, 2)
                else:
                    track.elevation_loss = round(track.elevation_loss + abs(elevation_diff), 2)

        # 创建轨迹点
        point = TrackPoint(
            track_id=track.id,
            point_index=point_index,
            time=point_time,
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
        recording.last_upload_at = datetime.now(timezone.utc)

        await db.commit()
        # 刷新 recording 对象，确保 current_track_id 已正确设置
        await db.refresh(recording)
        logger.info(f"After commit: recording {recording.id} current_track_id={recording.current_track_id}")
        await db.refresh(point)

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

    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """计算两点之间的距离（米），使用 Haversine 公式"""
        from math import radians, sin, cos, sqrt, atan2

        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return 6371000 * c  # 地球半径 6371km

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

        # 获取所有有效点，按索引排序
        points_result = await db.execute(
            select(TrackPoint)
            .where(
                and_(
                    TrackPoint.track_id == track_id,
                    TrackPoint.is_valid == True,
                    TrackPoint.elevation.is_not(None)
                )
            )
            .order_by(TrackPoint.point_index)
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


live_recording_service = LiveRecordingService()
