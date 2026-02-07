"""
分享页面相关 API 路由（公开访问，无需登录）
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.track import Track, TrackPoint
from app.schemas.track import (
    SharedTrackResponse, TrackResponse, TrackPointResponse,
    SharedConfigResponse, RegionTreeResponse, RegionNode
)
from app.services.share_service import share_service
from app.services.track_service import track_service

router = APIRouter(prefix="/shared", tags=["分享"])


@router.get("/{token}", response_model=SharedTrackResponse)
async def get_shared_track(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """
    获取分享的轨迹数据

    公开访问，无需登录。
    """
    track = await share_service.get_shared_track(db, token)
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="分享不存在或已失效"
        )

    # 获取轨迹点
    points_result = await db.execute(
        select(TrackPoint)
        .where(and_(TrackPoint.track_id == track.id, TrackPoint.is_valid == True))
        .order_by(TrackPoint.time, TrackPoint.created_at)
    )
    points = points_result.scalars().all()

    # 构建轨迹点响应（使用 WGS84 作为主坐标）
    point_responses = []
    for p in points:
        point_responses.append(TrackPointResponse(
            id=p.id,
            point_index=p.point_index,
            time=p.time,
            latitude=p.latitude_wgs84,
            longitude=p.longitude_wgs84,
            latitude_wgs84=p.latitude_wgs84,
            longitude_wgs84=p.longitude_wgs84,
            latitude_gcj02=p.latitude_gcj02,
            longitude_gcj02=p.longitude_gcj02,
            latitude_bd09=p.latitude_bd09,
            longitude_bd09=p.longitude_bd09,
            elevation=p.elevation,
            speed=p.speed,
            bearing=p.bearing,
            province=p.province,
            city=p.city,
            district=p.district,
            province_en=p.province_en,
            city_en=p.city_en,
            district_en=p.district_en,
            road_name=p.road_name,
            road_number=p.road_number,
            road_name_en=p.road_name_en,
            memo=p.memo,
        ))

    return SharedTrackResponse(
        track=TrackResponse.model_validate(track),
        points=point_responses
    )


@router.get("/{token}/config", response_model=SharedConfigResponse)
async def get_shared_config(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """
    获取分享者的地图配置

    公开访问，无需登录。
    返回分享者的自定义地图配置（如果存在）。
    """
    track = await share_service.get_shared_track(db, token)
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="分享不存在或已失效"
        )

    config = await share_service.get_shared_user_config(db, track)
    if not config:
        return SharedConfigResponse(
            map_provider=None,
            map_layers=None
        )

    return SharedConfigResponse(
        map_provider=config.map_provider,
        map_layers=config.map_layers
    )


@router.get("/{token}/points")
async def get_shared_track_points(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """
    获取分享轨迹的轨迹点（GeoJSON 格式）

    公开访问，无需登录。
    """
    track = await share_service.get_shared_track(db, token)
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="分享不存在或已失效"
        )

    points_result = await db.execute(
        select(TrackPoint)
        .where(and_(TrackPoint.track_id == track.id, TrackPoint.is_valid == True))
        .order_by(TrackPoint.time, TrackPoint.created_at)
    )
    points = points_result.scalars().all()

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "index": p.point_index,
                    "elevation": p.elevation,
                    "time": p.time.isoformat() + '+00:00' if p.time else None,
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [p.longitude_wgs84, p.latitude_wgs84]
                }
            }
            for p in points
        ]
    }


@router.get("/{token}/regions", response_model=RegionTreeResponse)
async def get_shared_track_regions(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """
    获取分享轨迹的经过区域

    公开访问，无需登录。
    返回按行政层级组织且按时间顺序展开的区域树：省 -> 市 -> 区 -> 道路
    """
    track = await share_service.get_shared_track(db, token)
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="分享不存在或已失效"
        )

    # 获取区域树（不需要权限检查，因为分享是公开的）
    result = await track_service.get_region_tree_no_auth(db, track.id)

    return {
        "track_id": track.id,
        "regions": result.get('regions', []),
        "stats": result.get('stats', {}),
    }
