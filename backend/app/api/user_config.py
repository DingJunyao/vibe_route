"""
用户配置相关 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.user_config import UserConfigResponse, UserConfigUpdate
from app.services.user_config_service import user_config_service

router = APIRouter(prefix="/user/config", tags=["用户配置"])


@router.get("", response_model=UserConfigResponse)
async def get_user_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取用户配置

    返回当前用户的地图配置，如果不存在则返回空配置。
    """
    config = await user_config_service.get_user_config(db, current_user.id)
    if not config:
        # 返回空配置
        return UserConfigResponse(
            id=0,
            user_id=current_user.id,
            map_provider=None,
            map_layers=None,
            created_at=current_user.created_at,
            updated_at=current_user.updated_at,
        )
    return config


@router.put("", response_model=UserConfigResponse)
async def update_user_config(
    data: UserConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    更新用户配置

    - map_provider: 默认地图提供商
    - map_layers: 地图层配置（与系统配置格式相同）
    """
    config = await user_config_service.update_config(
        db,
        user_id=current_user.id,
        map_provider=data.map_provider,
        map_layers=data.map_layers,
        updated_by=current_user.id,
    )
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="配置不存在"
        )
    return config


@router.post("")
async def reset_user_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    重置用户配置

    清除用户自定义配置，恢复使用系统默认配置。
    """
    await user_config_service.reset_config(db, current_user.id, current_user.id)
    return {"message": "配置已重置"}
