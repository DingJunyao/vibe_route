"""
地理信息编辑器业务逻辑
"""
import logging
from typing import List
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.models.track import Track, TrackPoint
from app.schemas.geo_editor import (
    TrackPointGeoData,
    GeoSegmentUpdate,
    GeoSegmentsUpdateRequest,
    GeoEditorDataResponse,
)

logger = logging.getLogger(__name__)


class GeoEditorService:
    """地理信息编辑器服务"""

    async def get_editor_data(
        self,
        db: Session,
        track_id: int,
        user_id: int,
        max_points: int = 5000
    ) -> GeoEditorDataResponse:
        """
        获取编辑器初始化数据

        Args:
            db: 数据库会话
            track_id: 轨迹ID
            user_id: 用户ID
            max_points: 最大返回点数
        """
        # 验证轨迹所有权
        track = await db.execute(
            select(Track).where(
                Track.id == track_id,
                Track.user_id == user_id,
                Track.is_valid == True
            )
        )
        track = track.scalar_one_or_none()

        if not track:
            raise ValueError("轨迹不存在或无权访问")

        # 获取轨迹点（按时间排序，限制数量）
        points_query = (
            select(TrackPoint)
            .where(TrackPoint.track_id == track_id)
            .order_by(TrackPoint.time.asc(), TrackPoint.created_at.asc())
            .limit(max_points)
        )
        points_result = await db.execute(points_query)
        points = points_result.scalars().all()

        # 计算总时长（毫秒）
        total_duration = 0
        if track.start_time and track.end_time:
            total_duration = int((track.end_time - track.start_time).total_seconds() * 1000)

        # 转换为响应格式
        points_data = [
            TrackPointGeoData(
                point_index=p.point_index,
                time=p.time,
                created_at=p.created_at,
                latitude=p.latitude_wgs84,
                longitude=p.longitude_wgs84,
                latitude_gcj02=p.latitude_gcj02,
                longitude_gcj02=p.longitude_gcj02,
                latitude_bd09=p.latitude_bd09,
                longitude_bd09=p.longitude_bd09,
                elevation=p.elevation,
                speed=p.speed,
                province=p.province,
                city=p.city,
                district=p.district,
                province_en=p.province_en,
                city_en=p.city_en,
                district_en=p.district_en,
                road_number=p.road_number,
                road_name=p.road_name,
                road_name_en=p.road_name_en,
            )
            for p in points
        ]

        return GeoEditorDataResponse(
            track_id=track.id,
            name=track.name,
            original_crs=track.original_crs,
            total_duration=total_duration,
            point_count=len(points_data),
            points=points_data,
        )

    async def update_segments(
        self,
        db: Session,
        track_id: int,
        user_id: int,
        request: GeoSegmentsUpdateRequest
    ) -> dict:
        """
        批量更新轨迹点地理信息

        Args:
            db: 数据库会话
            track_id: 轨迹ID
            user_id: 用户ID
            request: 更新请求

        Returns:
            更新统计
        """
        # 验证轨迹所有权
        track = await db.execute(
            select(Track).where(
                Track.id == track_id,
                Track.user_id == user_id,
                Track.is_valid == True
            )
        )
        track = track.scalar_one_or_none()

        if not track:
            raise ValueError("轨迹不存在或无权访问")

        # 统计更新数量
        total_updated = 0

        # 字段映射
        field_mapping = {
            'province': ('province', 'province_en'),
            'city': ('city', 'city_en'),
            'district': ('district', 'district_en'),
            'road_number': ('road_number', None),
            'road_name': ('road_name', 'road_name_en'),
        }

        # 处理每个段落
        for segment in request.segments:
            field_cn, field_en = field_mapping.get(segment.track_type, (None, None))
            if not field_cn:
                continue

            # 构建更新数据
            update_data = {
                'updated_at': datetime.now(timezone.utc).replace(tzinfo=None),
            }
            if segment.value is not None:
                update_data[field_cn] = segment.value
            if segment.value_en is not None and field_en:
                update_data[field_en] = segment.value_en

            # 执行更新
            stmt = (
                update(TrackPoint)
                .where(
                    TrackPoint.track_id == track_id,
                    TrackPoint.point_index >= segment.start_index,
                    TrackPoint.point_index <= segment.end_index,
                )
                .values(**update_data)
            )
            result = await db.execute(stmt)
            total_updated += result.rowcount

        # 更新轨迹时间戳
        track.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        await db.commit()

        logger.info(f"Updated {total_updated} track points for track {track_id}")

        return {
            'track_id': track_id,
            'updated_count': total_updated,
            'segments_count': len(request.segments),
        }


geo_editor_service = GeoEditorService()
