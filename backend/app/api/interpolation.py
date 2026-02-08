"""
轨迹插值 API 路由
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.interpolation import (
    InterpolationCreateRequest,
    InterpolationUpdateRequest,
    InterpolationResponse,
    InterpolationPreviewRequest,
    InterpolationPreviewResponse,
    AvailableSegment
)
from app.services.interpolation_service import interpolation_service

router = APIRouter(prefix="/interpolation", tags=["interpolation"])
logger = logging.getLogger(__name__)


@router.get("/tracks/{track_id}/available-segments")
async def get_available_segments(
    track_id: int,
    min_interval: float = 3.0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> list[AvailableSegment]:
    """
    获取轨迹的可插值区段列表

    Args:
        track_id: 轨迹ID
        min_interval: 最小间隔（秒）

    Returns:
        可用区段列表
    """
    segments = await interpolation_service.get_available_segments(
        db, track_id, min_interval
    )
    return segments


@router.post("/preview")
async def preview_interpolation(
    request: InterpolationPreviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> InterpolationPreviewResponse:
    """
    预览插值结果（不保存）
    """
    try:
        return await interpolation_service.preview_interpolation(db, request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tracks/{track_id}/interpolations")
async def create_interpolation(
    track_id: int,
    request: InterpolationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> InterpolationResponse:
    """
    创建插值配置并插入插值点
    """
    try:
        return await interpolation_service.create_interpolation(
            db, track_id, request, current_user.id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tracks/{track_id}/interpolations")
async def get_track_interpolations(
    track_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> list[InterpolationResponse]:
    """
    获取轨迹的所有插值配置
    """
    interpolations = await interpolation_service.get_track_interpolations(db, track_id)
    return interpolations


@router.delete("/interpolations/{interpolation_id}")
async def delete_interpolation(
    interpolation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除插值配置及关联的插值点
    """
    try:
        await interpolation_service.delete_interpolation(db, interpolation_id)
        return {"message": "插值已删除"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
