"""
轨迹相关 API 路由
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.config import settings
from app.models.user import User
from app.models.live_recording import LiveRecording
from app.schemas.track import (
    TrackCreate,
    TrackUpdate,
    TrackResponse,
    TrackListResponse,
    TrackPointResponse,
    TrackStatsResponse,
    RegionTreeResponse,
    UnifiedTrackListResponse,
)
from app.services.track_service import track_service

router = APIRouter(prefix="/tracks", tags=["轨迹"])
logger = logging.getLogger(__name__)


@router.post("/upload", response_model=TrackResponse)
async def upload_track(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    original_crs: str = Form("wgs84"),
    convert_to: Optional[str] = Form(None),
    fill_geocoding: bool = Form(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    上传轨迹

    - file: GPX、CSV、XLSX、KML 或 KMZ 文件（支持 GPS Logger CSV 格式、本项目 CSV/XLSX 导出格式、两步路 KML 格式）
    - name: 轨迹名称
    - description: 轨迹描述（可选）
    - original_crs: 原始坐标系 (wgs84, gcj02, bd09)，仅用于 GPX、GPS Logger CSV 和 KML
    - convert_to: 转换到目标坐标系（可选），仅用于 GPX、GPS Logger CSV 和 KML
    - fill_geocoding: 是否填充行政区划和道路信息，仅用于 GPX、GPS Logger CSV 和 KML
    """
    # 验证坐标系
    valid_crs = ['wgs84', 'gcj02', 'bd09']
    if original_crs not in valid_crs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的坐标系，可选值: {', '.join(valid_crs)}",
        )

    if convert_to and convert_to not in valid_crs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的目标坐标系，可选值: {', '.join(valid_crs)}",
        )

    # 验证文件类型
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件名不能为空",
        )

    file_ext = file.filename.lower().split('.')[-1] if '.' in file.filename else ''
    if file_ext not in ('gpx', 'csv', 'xlsx', 'kml', 'kmz'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只支持 GPX、CSV、XLSX、KML 或 KMZ 文件格式",
        )

    # 读取文件内容
    content = await file.read()

    # 检查文件大小
    if len(content) > settings.MAX_UPLOAD_SIZE:
        size_mb = settings.MAX_UPLOAD_SIZE / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件大小超过限制（最大 {size_mb:.0f} MB）",
        )

    # 创建轨迹
    try:
        if file_ext == 'gpx':
            # 解析 GPX
            try:
                gpx_content = content.decode('utf-8')
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="无法解析 GPX 文件，请确保文件编码为 UTF-8",
                )

            track = await track_service.create_from_gpx(
                db=db,
                user=current_user,
                filename=file.filename,
                gpx_content=gpx_content,
                name=name,
                description=description,
                original_crs=original_crs,
                convert_to=convert_to,
                fill_geocoding=fill_geocoding,
            )
        elif file_ext == 'csv':
            # 解析 CSV
            try:
                csv_content = content.decode('utf-8-sig')
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="无法解析 CSV 文件，请确保文件编码为 UTF-8",
                )

            track = await track_service.create_from_csv(
                db=db,
                user=current_user,
                filename=file.filename,
                csv_content=csv_content,
                name=name,
                description=description,
                original_crs=original_crs,
                convert_to=convert_to,
                fill_geocoding=fill_geocoding,
            )
        elif file_ext == 'xlsx':
            # 解析 XLSX（本项目导出格式）
            track = await track_service.create_from_xlsx(
                db=db,
                user=current_user,
                filename=file.filename,
                xlsx_content=content,
                name=name,
                description=description,
            )
        elif file_ext == 'kmz':
            # 解析 KMZ (ZIP 压缩的 KML)
            import zipfile
            from io import BytesIO

            try:
                with zipfile.ZipFile(BytesIO(content)) as zf:
                    # 查找 KML 文件
                    kml_files = [f for f in zf.namelist() if f.endswith('.kml')]
                    if not kml_files:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="KMZ 文件中没有找到 KML 文件",
                        )

                    # 读取第一个 KML 文件
                    kml_content = zf.read(kml_files[0]).decode('utf-8')
            except zipfile.BadZipFile:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="KMZ 文件格式错误",
                )

            track = await track_service.create_from_kml(
                db=db,
                user=current_user,
                filename=file.filename,
                kml_content=kml_content,
                name=name,
                description=description,
                original_crs=original_crs,
                convert_to=convert_to,
                fill_geocoding=fill_geocoding,
            )
        else:  # kml
            # 解析 KML
            try:
                kml_content = content.decode('utf-8')
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="无法解析 KML 文件，请确保文件编码为 UTF-8",
                )

            track = await track_service.create_from_kml(
                db=db,
                user=current_user,
                filename=file.filename,
                kml_content=kml_content,
                name=name,
                description=description,
                original_crs=original_crs,
                convert_to=convert_to,
                fill_geocoding=fill_geocoding,
            )
    except ValueError as e:
        logger.error(f"ValueError in upload_track for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Exception in upload_track for user {current_user.id}, file {file.filename}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理轨迹时出错: {str(e)}",
        )

    return TrackResponse.model_validate(track)


@router.get("", response_model=TrackListResponse)
async def get_tracks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="搜索轨迹名称"),
    sort_by: Optional[str] = Query(None, description="排序字段: start_time, distance, duration"),
    sort_order: Optional[str] = Query("desc", description="排序方向: asc, desc"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取当前用户的轨迹列表（仅普通轨迹，不包含实时记录）

    - search: 搜索轨迹名称（模糊匹配）
    - sort_by: 排序字段 (start_time, distance, duration)，默认为 start_time
    - sort_order: 排序方向 (asc=正序, desc=倒序)，默认为 desc
    """
    skip = (page - 1) * page_size
    tracks, total = await track_service.get_list(
        db,
        current_user.id,
        skip,
        page_size,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return TrackListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[TrackResponse.model_validate(t) for t in tracks],
    )


@router.get("/unified", response_model=UnifiedTrackListResponse)
async def get_unified_tracks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="搜索轨迹名称"),
    sort_by: Optional[str] = Query(None, description="排序字段: start_time, distance, duration"),
    sort_order: Optional[str] = Query("desc", description="排序方向: asc, desc"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取当前用户的轨迹列表（包含实时记录）

    实时记录会作为特殊轨迹一起返回，带有 is_live_recording=True 标记
    """
    items, total = await track_service.get_unified_list(
        db,
        current_user.id,
        (page - 1) * page_size,
        page_size,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return UnifiedTrackListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )


@router.get("/stats", response_model=TrackStatsResponse)
async def get_track_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取当前用户的轨迹统计
    """
    stats = await track_service.get_stats(db, current_user.id)
    return TrackStatsResponse(
        total_tracks=stats['total_tracks'],
        total_distance=stats['total_distance'],
        total_duration=stats['total_duration'],
        total_elevation_gain=stats['total_elevation_gain'],
    )


@router.get("/{track_id}", response_model=TrackResponse)
async def get_track(
    track_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取轨迹详情

    使用 selectinload 优化查询，一次性获取轨迹和关联的实时记录数据
    """
    # 使用优化的查询，预加载关联的实时记录
    track = await track_service.get_by_id(db, track_id, current_user.id, load_recording=True)
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="轨迹不存在",
        )

    # 从预加载的数据中查找活跃的实时记录
    recording = None
    if hasattr(track, 'live_recordings') and track.live_recordings:
        for rec in track.live_recordings:
            if rec.is_valid and rec.status == "active" and rec.current_track_id == track_id:
                recording = rec
                break

    # 获取实时记录的时间信息和统计数据
    last_point_time = None
    last_point_created_at = None
    calculated_stats = None
    if recording:
        from app.services.live_recording_service import live_recording_service
        last_point_time = await live_recording_service.get_last_point_time(db, recording)
        last_point_created_at = await live_recording_service.get_last_point_created_at(db, recording)
        # 实时计算统计数据（从点重新计算，确保准确性）
        calculated_stats = await live_recording_service.calculate_track_stats_from_points(db, track.id)

    # 构建响应
    # 对于实时记录，使用实时计算的统计值；否则使用数据库中的值
    if recording and calculated_stats:
        distance = calculated_stats["distance"]
        duration = calculated_stats["duration"]
        elevation_gain = calculated_stats["elevation_gain"]
        elevation_loss = calculated_stats["elevation_loss"]
    else:
        distance = track.distance or 0
        duration = track.duration or 0
        elevation_gain = track.elevation_gain or 0
        elevation_loss = track.elevation_loss or 0

    response_data = {
        "id": track.id,
        "user_id": track.user_id,
        "name": track.name,
        "description": track.description,
        "original_filename": track.original_filename,
        "original_crs": track.original_crs,
        "distance": distance,
        "duration": duration,
        "elevation_gain": elevation_gain,
        "elevation_loss": elevation_loss,
        "start_time": track.start_time,
        "end_time": track.end_time,
        "has_area_info": track.has_area_info or False,
        "has_road_info": track.has_road_info or False,
        "created_at": track.created_at,
        "updated_at": track.updated_at,
        # 实时记录相关
        "is_live_recording": recording is not None,
        "live_recording_id": recording.id if recording else None,
        "live_recording_status": recording.status if recording else None,
        "live_recording_token": recording.token if recording else None,
        "fill_geocoding": recording.fill_geocoding if recording else False,
        "last_upload_at": recording.last_upload_at if recording else None,
        "last_point_time": last_point_time,
        "last_point_created_at": last_point_created_at,
    }

    return TrackResponse.model_validate(response_data)


@router.patch("/{track_id}", response_model=TrackResponse)
async def update_track(
    track_id: int,
    update_data: TrackUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    更新轨迹信息（名称和描述）
    """
    track = await track_service.get_by_id(db, track_id, current_user.id)
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="轨迹不存在",
        )

    updated_track = await track_service.update(db, track, update_data, current_user.id)
    return TrackResponse.model_validate(updated_track)


@router.delete("/{track_id}")
async def delete_track(
    track_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    软删除轨迹
    """
    track = await track_service.get_by_id(db, track_id, current_user.id)
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="轨迹不存在",
        )

    await track_service.delete(db, track, current_user.id)
    return {"message": "轨迹已删除"}


@router.post("/{track_id}/fill-geocoding")
async def fill_track_geocoding(
    track_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    填充轨迹的行政区划和道路信息

    这是一个异步操作，会立即返回，可以通过进度查询接口获取填充进度
    """
    track = await track_service.get_by_id(db, track_id, current_user.id)
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="轨迹不存在",
        )

    # 检查是否已经在填充中
    progress = track_service.get_fill_progress(track_id)
    if progress.get("status") == "filling":
        return {"message": "正在填充中", "progress": progress}

    # 启动异步填充（创建新的数据库会话）
    import asyncio

    async def fill_task():
        """异步填充任务，创建自己的数据库会话"""
        from app.core.database import async_session_maker
        async with async_session_maker() as new_db:
            try:
                await track_service.fill_geocoding_info(new_db, track_id, current_user.id)
            except Exception as e:
                logger.exception(f"Fill geocoding task error for track {track_id}, user {current_user.id}")

    asyncio.create_task(fill_task())

    return {"message": "开始填充行政区划和道路信息", "track_id": track_id}


@router.post("/{track_id}/change-crs", response_model=TrackResponse)
async def change_track_crs(
    track_id: int,
    original_crs: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    更改轨迹的原始坐标系，并重新计算所有坐标系

    - original_crs: 新的原始坐标系 (wgs84, gcj02, bd09)
    - 会重新计算所有坐标系的坐标并保存
    """
    # 验证坐标系
    valid_crs = ['wgs84', 'gcj02', 'bd09']
    if original_crs not in valid_crs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的坐标系，可选值: {', '.join(valid_crs)}",
        )

    track = await track_service.get_by_id(db, track_id, current_user.id)
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="轨迹不存在",
        )

    try:
        updated_track = await track_service.change_original_crs(
            db, track_id, current_user.id, original_crs
        )
        return TrackResponse.model_validate(updated_track)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/{track_id}/fill-progress")
async def get_fill_progress(
    track_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取轨迹地理信息填充进度
    """
    track = await track_service.get_by_id(db, track_id, current_user.id)
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="轨迹不存在",
        )

    progress = track_service.get_fill_progress(track_id)
    return {
        "track_id": track_id,
        "progress": progress,
    }


@router.post("/{track_id}/fill-stop")
async def stop_fill_geocoding(
    track_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    停止填充地理信息
    """
    track = await track_service.get_by_id(db, track_id, current_user.id)
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="轨迹不存在",
        )

    success = track_service.stop_fill_geocoding(track_id)
    if success:
        return {"message": "已停止填充地理信息", "track_id": track_id}
    else:
        return {"message": "填充未在进行中", "track_id": track_id}


@router.get("/fill-progress/all")
async def get_all_fill_progress(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取当前用户所有正在填充的轨迹的进度

    只返回有进度信息的轨迹（状态为 filling, completed, failed）
    包括实时记录轨迹的填充进度
    """
    result = {}

    # 直接从内存中的进度字典获取所有有进度信息的轨迹
    # 这样可以包括实时记录轨迹的进度
    all_progress = track_service.get_all_fill_progress()

    for track_id, progress in all_progress.items():
        if progress.get("status") in ("filling", "completed", "failed"):
            # 验证轨迹属于当前用户
            track = await track_service.get_by_id(db, track_id, current_user.id)
            if track:
                current = progress.get("current", 0)
                total_points = progress.get("total", 0)
                failed = progress.get("failed", 0)
                percent = int((current / total_points * 100)) if total_points > 0 else 0
                result[track_id] = {
                    "status": progress.get("status", "idle"),
                    "current": current,
                    "total": total_points,
                    "failed": failed,
                    "percent": percent,
                }

    return result


@router.get("/{track_id}/points")
async def get_track_points(
    track_id: int,
    crs: str = Query("wgs84", pattern="^(wgs84|gcj02|bd09)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取轨迹点数据

    - crs: 主坐标系 (wgs84, gcj02, bd09)，用于设置 latitude/longitude 字段
    - 返回所有坐标系的字段，方便地图切换
    """
    points = await track_service.get_points(db, track_id, current_user.id, crs)

    # 返回所有坐标系数据
    result = []
    for point in points:
        # 格式化时间，添加 UTC 时区标识
        time_str = None
        if point.time is not None:
            time_str = point.time.isoformat() + '+00:00'

        point_data = {
            "id": point.id,
            "point_index": point.point_index,
            "time": time_str,
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
            "bearing": point.bearing,
            "province": point.province,
            "city": point.city,
            "district": point.district,
            "province_en": point.province_en,
            "city_en": point.city_en,
            "district_en": point.district_en,
            "road_name": point.road_name,
            "road_name_en": point.road_name_en,
            "road_number": point.road_number,
        }
        result.append(point_data)

    return {
        "track_id": track_id,
        "crs": crs,
        "count": len(result),
        "points": result,
    }


@router.get("/{track_id}/download")
async def download_track(
    track_id: int,
    crs: str = Query("original", pattern="^(original|wgs84|gcj02|bd09)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    下载轨迹 GPX 文件

    - crs: 坐标系 (original=原始坐标系, wgs84, gcj02, bd09)
    """
    from fastapi.responses import Response
    from urllib.parse import quote
    import gpxpy
    import gpxpy.gpx

    def encode_filename(filename: str) -> str:
        """编码文件名以支持中文，filename 和 filename* 都使用相同的 URL 编码"""
        # safe='' 确保编码所有特殊字符（包括冒号）
        encoded = quote(filename, safe='')
        return f"attachment; filename=\"{encoded}\"; filename*=utf-8''{encoded}"

    track = await track_service.get_by_id(db, track_id, current_user.id)
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="轨迹不存在",
        )

    # 获取轨迹点
    points = await track_service.get_points(db, track_id, current_user.id, track.original_crs)

    # 创建 GPX 对象
    gpx = gpxpy.gpx.GPX()
    gpx_track = gpxpy.gpx.GPXTrack(name=track.name)
    gpx_segment = gpxpy.gpx.GPXTrackSegment()

    # 确定使用的坐标系
    if crs == "original":
        original_crs_value = track.original_crs or "wgs84"
        target_crs = str(original_crs_value)  # type: ignore[arg-type]
    else:
        target_crs = crs

    # 添加轨迹点
    for point in points:
        if target_crs == "wgs84":
            lat, lon = point.latitude_wgs84, point.longitude_wgs84
        elif target_crs == "gcj02":
            lat, lon = point.latitude_gcj02, point.longitude_gcj02
        elif target_crs == "bd09":
            lat, lon = point.latitude_bd09, point.longitude_bd09
        else:
            # 使用原始坐标
            lat, lon = point.latitude_wgs84, point.longitude_wgs84

        gpx_point = gpxpy.gpx.GPXTrackPoint(
            latitude=lat,
            longitude=lon,
            elevation=point.elevation,
            time=point.time,
        )
        gpx_segment.points.append(gpx_point)

    gpx_track.segments.append(gpx_segment)
    gpx.tracks.append(gpx_track)

    # 生成文件名（使用轨迹名称）
    # 如果坐标系不是原坐标系，在文件名中加上坐标系后缀
    original_crs_str = str(track.original_crs or "wgs84")
    target_crs_str = str(target_crs) if target_crs else "wgs84"
    crs_suffix = "" if target_crs_str == original_crs_str else f"_{target_crs_str.upper()}"
    filename = f"{track.name}{crs_suffix}.gpx"

    return Response(
        content=gpx.to_xml(),
        media_type="application/gpx+xml",
        headers={
            "Content-Disposition": encode_filename(filename),
        },
    )


@router.get("/{track_id}/regions", response_model=RegionTreeResponse)
async def get_track_regions(
    track_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取轨迹的区域树

    返回按行政层级组织且按时间顺序展开的区域树：省 -> 市 -> 区 -> 道路
    同一区域的多次经过会分开显示。
    """
    result = await track_service.get_region_tree(db, track_id, current_user.id)

    return {
        "track_id": track_id,
        "regions": result.get('regions', []),
        "stats": result.get('stats', {}),
    }


@router.get("/{track_id}/export")
async def export_track_points(
    track_id: int,
    format: str = Query("csv", pattern="^(csv|xlsx|kml)$"),
    crs: Optional[str] = Query(None, description="坐标系 (仅用于 kml 格式)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    导出轨迹点数据为 CSV、XLSX 或 KML 格式

    - format: 导出格式 (csv、xlsx 或 kml)
    - crs: 坐标系 (仅用于 kml 格式，可选 original/wgs84/gcj02/bd09)
    - CSV 格式使用 UTF-8 编码带 BOM，确保 Excel 正确显示中文
    - KML 格式使用 Google gx:Track 扩展，支持两步路导入
    - 导出文件包含所有轨迹点的详细数据，便于编辑行政区划和道路信息
    """
    from fastapi.responses import Response
    from loguru import logger
    from urllib.parse import quote

    def encode_filename(filename: str) -> str:
        """编码文件名以支持中文，filename 和 filename* 都使用相同的 URL 编码"""
        # safe='' 确保编码所有特殊字符（包括冒号）
        encoded = quote(filename, safe='')
        return f"attachment; filename=\"{encoded}\"; filename*=UTF-8''{encoded}"

    try:
        logger.info(f"Exporting track {track_id} as {format}")

        if format == "csv":
            filename, content = await track_service.export_points_to_csv(
                db, track_id, current_user.id
            )
            logger.info(f"CSV export successful: {filename}")
            return Response(
                content=content,
                media_type="text/csv; charset=utf-8",
                headers={
                    "Content-Disposition": encode_filename(filename),
                },
            )
        elif format == "xlsx":
            filename, content = await track_service.export_points_to_xlsx(
                db, track_id, current_user.id
            )
            logger.info(f"XLSX export successful: {filename}")
            return Response(
                content=content,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={
                    "Content-Disposition": encode_filename(filename),
                },
            )
        else:  # kml
            filename, content = await track_service.export_points_to_kml(
                db, track_id, current_user.id, crs
            )
            logger.info(f"KML export successful: {filename}")
            return Response(
                content=content,
                media_type="application/vnd.google-earth.kml+xml",
                headers={
                    "Content-Disposition": encode_filename(filename),
                },
            )
    except ValueError as e:
        logger.error(f"Export ValueError for track {track_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Export failed for track {track_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"导出失败: {str(e)}",
        )


@router.post("/{track_id}/import")
async def import_track_points(
    track_id: int,
    file: UploadFile = File(...),
    match_mode: str = Form("index"),
    timezone: str = Form("UTC"),
    time_tolerance: float = Form(1.0),
    confirm: bool = Form(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    从 CSV 或 XLSX 文件导入轨迹点数据，更新行政区划和道路信息

    - file: CSV 或 XLSX 文件
    - match_mode: 匹配方式，index=索引匹配，time=时间匹配
    - timezone: 导入文件的时间戳时区（如 UTC、UTC+8、Asia/Shanghai），默认 UTC
    - time_tolerance: 时间匹配误差（秒），默认 1 秒（不含）
    - confirm: 是否确认停止正在进行的地理信息填充并继续导入
    - 只更新可编辑字段：行政区划、道路信息、备注
    - 坐标、海拔、速度等原始数据不会被修改
    """
    # 检查是否正在填充地理信息
    progress = track_service.get_fill_progress(track_id)
    if progress.get("status") == "filling":
        if not confirm:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "message": "当前正在填充地理信息，如果继续导入，会立即停止，改用导入的结果",
                    "code": "FILLING_IN_PROGRESS",
                    "confirm_required": True,
                },
            )
        # 用户确认，停止填充任务
        logger.info(f"User confirmed to stop filling for track {track_id}")
        track_service.stop_fill_geocoding(track_id)
    # 验证匹配方式
    if match_mode not in ("index", "time"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的匹配方式，可选值: index, time",
        )
    # 验证误差范围
    if time_tolerance <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="时间误差必须大于 0",
        )
    # 确定文件格式
    filename = file.filename or ""
    if filename.lower().endswith(".csv"):
        file_format = "csv"
    elif filename.lower().endswith(".xlsx"):
        file_format = "xlsx"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不支持的文件格式，请上传 CSV 或 XLSX 文件",
        )

    try:
        content = await file.read()
        result = await track_service.import_points_from_file(
            db, track_id, current_user.id, content, file_format, match_mode, timezone, time_tolerance
        )
        return result
    except ValueError as e:
        logger.error(f"Import ValueError for track {track_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Import failed for track {track_id}, user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"导入失败: {str(e)}",
        )
