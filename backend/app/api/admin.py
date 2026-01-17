"""
管理员相关 API 路由
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_admin_user
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate
from app.schemas.config import (
    ConfigResponse,
    ConfigUpdate,
    InviteCodeCreate,
    InviteCodeResponse,
)
from app.services.user_service import user_service
from app.services.config_service import config_service

router = APIRouter(prefix="/admin", tags=["管理员"])


# ========== 用户管理 ==========

@router.get("/users", response_model=List[UserResponse])
async def get_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取用户列表（管理员）
    """
    users = await user_service.get_list(db, skip=skip, limit=limit)
    return [UserResponse.model_validate(u) for u in users]


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    更新用户信息（管理员）
    """
    user = await user_service.get_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    # 构建更新数据
    update_data = user_update.model_dump(exclude_unset=True)

    # 不允许修改自己的管理员状态
    if user_id == current_admin.id and "is_admin" in update_data:
        update_data.pop("is_admin")

    updated_user = await user_service.update(db, user, current_admin.id, **update_data)
    return UserResponse.model_validate(updated_user)


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    软删除用户（管理员）
    """
    user = await user_service.get_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    # 不允许删除自己
    if user_id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己",
        )

    await user_service.delete(db, user, current_admin.id)
    return {"message": "用户已删除"}


# ========== 系统配置 ==========

@router.get("/config", response_model=ConfigResponse)
async def get_config(
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取系统配置（管理员）
    """
    configs = await config_service.get_all_configs(db)
    return ConfigResponse(
        registration_enabled=configs.get("registration_enabled", True),
        invite_code_required=configs.get("invite_code_required", False),
        default_map_provider=configs.get("default_map_provider", "osm"),
        geocoding_provider=configs.get("geocoding_provider", "nominatim"),
        geocoding_config=configs.get("geocoding_config", {}),
        map_layers=configs.get("map_layers", {}),
    )


@router.put("/config", response_model=ConfigResponse)
async def update_config(
    config_update: ConfigUpdate,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    更新系统配置（管理员）
    """
    update_data = config_update.model_dump(exclude_unset=True)
    configs = await config_service.update_config(db, update_data, current_admin.id)
    return ConfigResponse(
        registration_enabled=configs.get("registration_enabled", True),
        invite_code_required=configs.get("invite_code_required", False),
        default_map_provider=configs.get("default_map_provider", "osm"),
        geocoding_provider=configs.get("geocoding_provider", "nominatim"),
        geocoding_config=configs.get("geocoding_config", {}),
        map_layers=configs.get("map_layers", {}),
    )


# ========== 邀请码管理 ==========

@router.post("/invite-codes", response_model=InviteCodeResponse)
async def create_invite_code(
    invite_code_data: InviteCodeCreate,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    创建邀请码（管理员）
    """
    invite_code = await config_service.create_invite_code(
        db,
        code=invite_code_data.code,
        max_uses=invite_code_data.max_uses,
        created_by=current_admin.id,
        expires_in_days=invite_code_data.expires_in_days,
    )
    return InviteCodeResponse(
        id=invite_code.id,
        code=invite_code.code,
        max_uses=invite_code.max_uses,
        used_count=invite_code.used_count,
        created_by=invite_code.created_by,
        created_at=invite_code.created_at,
        expires_at=invite_code.expires_at,
        is_valid=invite_code.is_valid,
    )


@router.get("/invite-codes", response_model=List[InviteCodeResponse])
async def get_invite_codes(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取邀请码列表（管理员）
    """
    invite_codes = await config_service.get_invite_codes(db, skip=skip, limit=limit)
    return [
        InviteCodeResponse(
            id=ic.id,
            code=ic.code,
            max_uses=ic.max_uses,
            used_count=ic.used_count,
            created_by=ic.created_by,
            created_at=ic.created_at,
            expires_at=ic.expires_at,
            is_valid=ic.is_valid,
        )
        for ic in invite_codes
    ]


@router.delete("/invite-codes/{invite_code_id}")
async def delete_invite_code(
    invite_code_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    软删除邀请码（管理员）
    """
    from app.models.config import InviteCode
    from sqlalchemy import select, and_

    result = await db.execute(
        select(InviteCode).where(
            and_(InviteCode.id == invite_code_id, InviteCode.is_valid == True)
        )
    )
    invite_code = result.scalar_one_or_none()

    if not invite_code:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="邀请码不存在",
        )

    await config_service.delete_invite_code(db, invite_code, current_admin.id)
    return {"message": "邀请码已删除"}
