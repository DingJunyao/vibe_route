"""
轨迹相关 API 路由
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.track import (
    TrackCreate,
    TrackUpdate,
    TrackResponse,
    TrackListResponse,
    TrackPointResponse,
    TrackStatsResponse,
    RegionTreeResponse,
)
from app.services.track_service import track_service

router = APIRouter(prefix="/tracks", tags=["轨迹"])


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

    - file: GPX 文件
    - name: 轨迹名称
    - description: 轨迹描述（可选）
    - original_crs: 原始坐标系 (wgs84, gcj02, bd09)
    - convert_to: 转换到目标坐标系（可选）
    - fill_geocoding: 是否填充行政区划和道路信息
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
    if not file.filename or not file.filename.lower().endswith('.gpx'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只支持 GPX 文件格式",
        )

    # 读取文件内容
    content = await file.read()

    # 尝试解析 GPX
    try:
        gpx_content = content.decode('utf-8')
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无法解析 GPX 文件，请确保文件编码为 UTF-8",
        )

    # 创建轨迹
    try:
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
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
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
    获取当前用户的轨迹列表

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


@router.get("/stats", response_model=TrackStatsResponse)
async def get_track_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取当前用户的轨迹统计
    """
    stats = await track_service.get_stats(db, current_user.id)
    return TrackStatsResponse(**stats)


@router.get("/{track_id}", response_model=TrackResponse)
async def get_track(
    track_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取轨迹详情
    """
    track = await track_service.get_by_id(db, track_id, current_user.id)
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="轨迹不存在",
        )

    return TrackResponse.model_validate(track)


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

    # 启动异步填充
    import asyncio
    asyncio.create_task(
        track_service.fill_geocoding_info(db, track_id, current_user.id)
    )

    return {"message": "开始填充行政区划和道路信息", "track_id": track_id}


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
    """
    # 获取用户的所有轨迹ID
    tracks, _ = await track_service.get_list(db, current_user.id, 0, 1000)

    result = {}
    for track in tracks:
        progress = track_service.get_fill_progress(track.id)
        if progress and progress.get("status") in ("filling", "completed", "failed"):
            current = progress.get("current", 0)
            total_points = progress.get("total", 0)
            percent = int((current / total_points * 100)) if total_points > 0 else 0
            result[track.id] = {
                "status": progress.get("status", "idle"),
                "current": current,
                "total": total_points,
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
    import gpxpy
    import gpxpy.gpx

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
    gpx_track = gpxpy.gpx.GPXTrack()
    gpx_segment = gpxpy.gpx.GPXTrackSegment()

    # 确定使用的坐标系
    if crs == "original":
        target_crs = track.original_crs
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

    # 生成文件名
    filename = f"{track.name}_{target_crs}.gpx"

    return Response(
        content=gpx.to_xml(),
        media_type="application/gpx+xml",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
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
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    导出轨迹点数据为 CSV 或 XLSX 格式

    - format: 导出格式 (csv 或 xlsx)
    - CSV 格式使用 UTF-8 编码带 BOM，确保 Excel 正确显示中文
    - 导出文件包含所有轨迹点的详细数据，便于编辑行政区划和道路信息
    """
    from fastapi.responses import Response
    from loguru import logger
    from urllib.parse import quote

    def encode_filename(filename: str) -> str:
        """编码文件名以支持中文"""
        encoded = quote(filename.encode('utf-8'))
        return f"attachment; filename*=UTF-8''{encoded}"

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
        else:  # xlsx
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
    except ValueError as e:
        logger.error(f"Export ValueError: {e}")
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    从 CSV 或 XLSX 文件导入轨迹点数据，更新行政区划和道路信息

    - file: CSV 或 XLSX 文件
    - match_mode: 匹配方式，index=索引匹配，time=时间匹配
    - timezone: 导入文件的时间戳时区（如 UTC、UTC+8、Asia/Shanghai），默认 UTC
    - time_tolerance: 时间匹配误差（秒），默认 1 秒（不含）
    - 只更新可编辑字段：行政区划、道路信息、备注
    - 坐标、海拔、速度等原始数据不会被修改
    """
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"导入失败: {str(e)}",
        )
