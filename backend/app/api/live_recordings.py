"""
实时记录相关 API 路由
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query, Response, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.live_recording import (
    CreateRecordingRequest,
    LiveRecordingResponse,
    RecordingStatusResponse,
    LogPointResponse,
)
from app.schemas.track import TrackResponse
from app.services.live_recording_service import live_recording_service
from app.services.track_service import track_service

router = APIRouter(prefix="/live-recordings", tags=["实时记录"])


@router.post("/create", response_model=LiveRecordingResponse)
async def create_recording(
    data: CreateRecordingRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    创建实时记录会话

    生成一个长期有效的上传 token，可用于无认证上传轨迹
    """
    recording = await live_recording_service.create(
        db,
        user_id=current_user.id,
        name=data.name,
        description=data.description,
        fill_geocoding=data.fill_geocoding or False,
    )

    # 生成上传 URL（使用相对路径，前端根据需要拼接域名）
    upload_url = f"/live-upload?token={recording.token}"

    return LiveRecordingResponse(
        id=recording.id,
        name=recording.name,
        description=recording.description,
        token=recording.token,
        status=recording.status,
        track_count=recording.track_count,
        last_upload_at=recording.last_upload_at,
        upload_url=upload_url,
        created_at=recording.created_at,
        fill_geocoding=recording.fill_geocoding,
    )


@router.get("", response_model=list[LiveRecordingResponse])
async def get_recordings(
    status: Optional[str] = Query(None, description="状态筛选：active 或 ended"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取当前用户的实时记录列表
    """
    recordings = await live_recording_service.get_list(
        db,
        user_id=current_user.id,
        status=status,
    )

    # 生成完整的上传 URL
    result = []
    for recording in recordings:
        upload_url = f"/live-upload?token={recording.token}"
        result.append(LiveRecordingResponse(
            id=recording.id,
            name=recording.name,
            description=recording.description,
            token=recording.token,
            status=recording.status,
            track_count=recording.track_count,
            last_upload_at=recording.last_upload_at,
            upload_url=upload_url,
            created_at=recording.created_at,
            fill_geocoding=recording.fill_geocoding,
        ))

    return result


@router.post("/{recording_id}/end", response_model=LiveRecordingResponse)
async def end_recording(
    recording_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    结束实时记录会话

    结束后，token 将失效，无法继续上传轨迹
    """
    recording = await live_recording_service.get_by_id(db, recording_id, current_user.id)
    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="记录不存在",
        )

    if recording.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="记录已结束",
        )

    recording = await live_recording_service.end(db, recording)

    # 主动断开该记录的所有 WebSocket 连接
    from app.api.websocket import live_track_manager
    await live_track_manager.close_recording_connections(
        recording_id,
        code=1000,
        reason="Recording ended"
    )

    upload_url = f"/live-upload?token={recording.token}"
    return LiveRecordingResponse(
        id=recording.id,
        name=recording.name,
        description=recording.description,
        token=recording.token,
        status=recording.status,
        track_count=recording.track_count,
        last_upload_at=recording.last_upload_at,
        upload_url=upload_url,
        created_at=recording.created_at,
        fill_geocoding=recording.fill_geocoding,
    )


@router.get("/{recording_id}/detail", response_model=TrackResponse)
async def get_recording_detail(
    recording_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取实时记录的详情（返回格式与普通轨迹相同）

    使用关联的当前轨迹的数据返回，包括统计信息、点数据等。
    如果还没有关联的轨迹（等待上传点），返回空轨迹对象。
    """
    recording = await live_recording_service.get_by_id(db, recording_id, current_user.id)
    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="记录不存在",
        )

    # 获取关联的当前轨迹 ID
    track_id = getattr(recording, 'current_track_id')
    if track_id is None:
        # 还没有上传轨迹点，返回一个空的 Track 对象
        return TrackResponse(
            id=-recording_id,  # 使用负数 ID 表示虚拟轨迹
            user_id=current_user.id,
            name=recording.name,
            description=recording.description,
            original_filename="",
            original_crs="wgs84",
            distance=0,
            duration=0,
            elevation_gain=0,
            elevation_loss=0,
            start_time=None,
            end_time=None,
            has_area_info=False,
            has_road_info=False,
            created_at=recording.created_at,
            updated_at=recording.created_at,
            is_live_recording=True,
            live_recording_status=recording.status,
            live_recording_id=recording.id,
            live_recording_token=recording.token,
            fill_geocoding=recording.fill_geocoding,
        )

    # 获取关联的轨迹（track_id 在此之后保证不为 None）
    track = await track_service.get_by_id(db, track_id, getattr(current_user, 'id'))
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="轨迹数据不存在",
        )

    # 返回轨迹数据（格式与普通轨迹详情相同）
    # 使用 model_dump_json() 获取正确的 JSON 格式，然后添加额外字段
    import json
    track_json = TrackResponse.model_validate(track).model_dump_json()
    track_dict = json.loads(track_json)
    track_dict['fill_geocoding'] = recording.fill_geocoding
    track_dict['is_live_recording'] = True
    track_dict['live_recording_id'] = recording.id
    track_dict['live_recording_status'] = recording.status
    track_dict['live_recording_token'] = recording.token

    # 使用 JSONResponse 直接返回 JSON
    from fastapi.responses import JSONResponse
    return JSONResponse(content=track_dict)


@router.get("/{recording_id}/status", response_model=RecordingStatusResponse)
async def get_recording_status(
    recording_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取实时记录状态和关联的轨迹列表
    """
    recording = await live_recording_service.get_by_id(db, recording_id, current_user.id)
    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="记录不存在",
        )

    # 获取关联的轨迹列表
    tracks, _ = await track_service.get_list(
        db,
        current_user.id,
        skip=0,
        limit=100,
    )

    # 筛选与本次记录相关的轨迹（通过创建时间判断）
    # 由于记录开始后上传的轨迹都会关联，我们可以简单地返回所有在记录创建之后的轨迹
    related_tracks = []
    for track in tracks:
        if track.created_at >= recording.created_at:
            related_tracks.append({
                "id": track.id,
                "name": track.name,
                "distance": track.distance,
                "duration": track.duration,
                "created_at": track.created_at.isoformat() + "+00:00",
            })

    return RecordingStatusResponse(
        id=recording.id,
        name=recording.name,
        description=recording.description,
        status=recording.status,
        track_count=recording.track_count,
        last_upload_at=recording.last_upload_at,
        created_at=recording.created_at,
        tracks=related_tracks,
    )


@router.delete("/{recording_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recording(
    recording_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    删除实时记录会话
    """
    recording = await live_recording_service.get_by_id(db, recording_id, current_user.id)
    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="记录不存在",
        )

    await live_recording_service.delete(db, recording)


@router.patch("/{recording_id}/fill-geocoding")
async def update_fill_geocoding(
    recording_id: int,
    data: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    更新自动填充地理信息设置

    Args:
        recording_id: 记录 ID
        data: 包含 fill_geocoding 的 JSON 对象
    """
    from loguru import logger

    fill_geocoding = data.get("fill_geocoding", False)
    logger.info(f"PATCH fill_geocoding: recording_id={recording_id}, fill_geocoding={fill_geocoding}, data={data}")

    recording = await live_recording_service.get_by_id(db, recording_id, current_user.id)
    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="记录不存在",
        )

    recording = await live_recording_service.update_fill_geocoding(db, recording, fill_geocoding)

    logger.info(f"Updated fill_geocoding: recording_id={recording_id}, new_value={recording.fill_geocoding}")

    return {
        "fill_geocoding": recording.fill_geocoding,
        "message": "设置已更新"
    }


@router.get("/info/{token}", response_model=LiveRecordingResponse)
async def get_recording_info(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """
    根据 token 获取记录信息（无需认证）

    用于在上传页面显示记录名称和描述
    """
    recording = await live_recording_service.get_by_token(db, token)
    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="无效的链接或记录不存在",
        )

    if recording.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="此记录已结束",
        )

    upload_url = f"/live-upload?token={recording.token}"
    return LiveRecordingResponse(
        id=recording.id,
        name=recording.name,
        description=recording.description,
        token=recording.token,
        status=recording.status,
        track_count=recording.track_count,
        last_upload_at=recording.last_upload_at,
        upload_url=upload_url,
        created_at=recording.created_at,
        fill_geocoding=recording.fill_geocoding,
    )


@router.post("/upload/{token}", response_model=dict)
async def upload_to_recording(
    token: str,
    file: UploadFile = File(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    original_crs: str = Form("wgs84"),
    convert_to: Optional[str] = Form(None),
    fill_geocoding: bool = Form(False),
    db: AsyncSession = Depends(get_db),
):
    """
    使用 token 上传轨迹到实时记录（无需认证）

    - token: 实时记录 token
    - file: GPX 文件
    - name: 轨迹名称
    - description: 轨迹描述（可选）
    - original_crs: 原始坐标系 (wgs84, gcj02, bd09)
    - convert_to: 转换到目标坐标系（可选）
    - fill_geocoding: 是否填充行政区划和道路信息
    """
    # 验证 token 并获取记录
    recording = await live_recording_service.get_by_token(db, token)
    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="无效的 token",
        )

    if recording.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="记录已结束，无法上传",
        )

    # 获取记录所属用户
    from app.models.user import User
    from app.services.user_service import user_service

    user = await user_service.get_by_id(db, recording.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

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
            user=user,
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

    # 更新记录的轨迹计数
    await live_recording_service.increment_track_count(db, recording)

    return {
        "message": "轨迹上传成功",
        "track_id": track.id,
        "recording_id": recording.id,
        "recording_name": recording.name,
    }


@router.get("/log/{token}")
@router.post("/log/{token}")
async def log_track_point(
    token: str,
    lat: Optional[str] = Query(None, description="纬度"),
    lon: Optional[str] = Query(None, description="经度"),
    longitude: Optional[str] = Query(None, description="经度（GPS Logger 兼容）"),
    time: Optional[str] = Query(None, description="时间（ISO 格式字符串或毫秒时间戳）"),
    alt: Optional[str] = Query(None, description="海拔（米）"),
    spd: Optional[str] = Query(None, description="速度（m/s）"),
    s: Optional[str] = Query(None, description="速度（GPS Logger 兼容，m/s）"),
    acc: Optional[str] = Query(None, description="精度（米）"),
    sat: Optional[str] = Query(None, description="卫星数量"),
    bea: Optional[str] = Query(None, description="方位角（度）"),
    original_crs: str = Query("wgs84", description="原始坐标系"),
    db: AsyncSession = Depends(get_db),
):
    """
    实时上传单个轨迹点（无需认证）

    支持 GET 和 POST 方法，兼容 GPS Logger 等 GPS 记录应用的 URL 参数格式：
    - lat: 纬度（必需）
    - lon 或 longitude: 经度（必需）
    - time: 时间（支持 ISO 格式字符串或毫秒时间戳）
    - alt: 海拔（米）
    - spd 或 s: 速度（m/s）
    - acc: 精度（米）
    - sat: 卫星数量
    - bea: 方位角（度）

    GPS Logger URL 示例：
    https://route.a4ding.com/api/live-recordings/log/{TOKEN}?lat=%LAT&lon=%LON&time=%TIME&alt=%ALT&spd=%SPD

    如果 URL 中包含占位符（如 %LAT），会重定向到引导页面。
    """
    from datetime import datetime

    # 检查是否为占位符（GPS Logger 占位符格式：%LAT, %LON, %TIME 等）
    placeholder_values = ["%LAT", "%LON", "%TIME", "%ALT", "%SPD"]
    query_params = [lat, lon, longitude, time, alt, spd, s, acc, sat, bea]

    # 如果任何参数包含占位符，重定向到前端引导页面
    if any(any(param and ph in param for ph in placeholder_values) for param in query_params if param):
        # 在开发环境，前端地址是 localhost:5173
        # 在生产环境，需要根据实际情况调整
        # 这里我们返回一个简单的 HTML 页面，带有重定向
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta http-equiv="refresh" content="0; url=/live-recordings/log/{token}">
            <script>
                // 立即重定向到前端引导页面
                window.location.href = '/live-recordings/log/{token}';
            </script>
        </head>
        <body>
            <p>正在跳转到配置页面...</p>
            <p>如果没有跳转，请点击：<a href="/live-recordings/log/{token}">配置 GPS Logger</a></p>
        </body>
        </html>
        """
        return Response(content=html_content, media_type="text/html")

    # 正常处理：验证必需参数
    if lat is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="缺少纬度参数",
        )

    # 参数兼容性处理：GPS Logger 使用 longitude 和 s
    actual_lon = lon if lon is not None else longitude

    if actual_lon is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="缺少经度参数（请使用 lon 或 longitude）",
        )

    # 尝试将参数转换为数值
    try:
        lat_float = float(lat)
        actual_lon_float = float(actual_lon)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="纬度和经度必须是有效的数字",
        )

    actual_spd = spd if spd is not None else s
    actual_spd_float = float(actual_spd) if actual_spd else None
    alt_float = float(alt) if alt else None
    acc_float = float(acc) if acc else None
    sat_int = int(sat) if sat else None
    bea_float = float(bea) if bea else None

    # 验证坐标系
    valid_crs = ['wgs84', 'gcj02', 'bd09']
    if original_crs not in valid_crs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的坐标系，可选值: {', '.join(valid_crs)}",
        )

    # 验证坐标范围
    if not -90 <= lat_float <= 90:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="纬度必须在 -90 到 90 之间",
        )
    if not -180 <= actual_lon_float <= 180:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="经度必须在 -180 到 180 之间",
        )

    # 解析时间参数（支持 ISO 格式字符串或毫秒时间戳）
    time_ms: int | None = None
    if time:
        try:
            # 尝试解析为毫秒时间戳（数字字符串）
            time_ms = int(time)
        except ValueError:
            # 如果不是纯数字，尝试解析为 ISO 格式时间字符串
            try:
                # GPS Logger 发送的格式如: 2026-01-27T11:36:02.000Z
                dt = datetime.fromisoformat(time.replace('Z', '+00:00'))
                time_ms = int(dt.timestamp() * 1000)
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"无效的时间格式: {time}",
                )

    # 根据 token 获取记录
    recording = await live_recording_service.get_by_token(db, token)
    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="无效的 token",
        )

    if recording.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="记录已结束，无法上传",
        )

    # 添加轨迹点
    try:
        result = await live_recording_service.add_point_to_recording(
            db=db,
            recording=recording,
            lat=lat_float,
            lon=actual_lon_float,
            time=time_ms,
            elevation=alt_float,
            speed=actual_spd_float,
            accuracy=acc_float,
            satellites=sat_int,
            bearing=bea_float,
            original_crs=original_crs,
        )
        return LogPointResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"添加轨迹点时出错: {str(e)}",
        )
