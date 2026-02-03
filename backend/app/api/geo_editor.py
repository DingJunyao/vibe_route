"""
地理信息编辑器 API 路由
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.geo_editor import (
    GeoEditorDataResponse,
    GeoSegmentsUpdateRequest,
)
from app.services.geo_editor_service import geo_editor_service

router = APIRouter(prefix="/geo-editor", tags=["地理信息编辑器"])
logger = logging.getLogger(__name__)


@router.get("/tracks/{track_id}", response_model=GeoEditorDataResponse)
async def get_geo_editor_data(
    track_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取轨迹地理信息编辑器数据

    返回轨迹点和地理信息，用于初始化编辑器
    """
    try:
        return await geo_editor_service.get_editor_data(
            db=db,
            track_id=track_id,
            user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error getting geo-editor data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取编辑器数据失败",
        )


@router.put("/tracks/{track_id}/segments")
async def update_geo_segments(
    track_id: int,
    request: GeoSegmentsUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    批量更新轨迹点地理信息

    根据段落范围批量更新轨迹点的行政区划、道路编号、道路名称等字段
    """
    try:
        result = await geo_editor_service.update_segments(
            db=db,
            track_id=track_id,
            user_id=current_user.id,
            request=request,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error updating geo-segments: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新地理信息失败",
        )
