"""
认证相关 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin, UserResponse, TokenResponse
from app.schemas.config import PublicConfigResponse
from app.services.user_service import user_service
from app.services.config_service import config_service

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", response_model=TokenResponse)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    用户注册

    - 首位注册的用户自动成为管理员
    - 如果开启了邀请码验证，需要提供有效的邀请码
    """
    # 检查用户名是否已存在
    existing_user = await user_service.get_by_username(db, user_data.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已被使用",
        )

    # 检查邮箱是否已存在
    existing_email = await user_service.get_by_email(db, user_data.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被使用",
        )

    # 检查注册是否开启
    registration_enabled = await config_service.get_json(db, "registration_enabled", True)
    if not registration_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="注册功能已关闭",
        )

    # 检查是否需要邀请码
    invite_code_required = await config_service.get_json(db, "invite_code_required", False)
    if invite_code_required:
        if not user_data.invite_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请提供邀请码",
            )
        is_valid = await config_service.validate_invite_code(db, user_data.invite_code)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邀请码无效或已过期",
            )
        # 使用邀请码
        await config_service.use_invite_code(db, user_data.invite_code)

    # 检查是否为首位用户
    user_count = await user_service.count_all(db)
    is_admin = user_count == 0

    # 创建用户
    user = await user_service.create(
        db,
        username=user_data.username,
        email=user_data.email,
        password=user_data.password,
        is_admin=is_admin,
    )

    # 生成访问令牌
    access_token = create_access_token(data={"sub": str(user.id)})

    return TokenResponse(
        access_token=access_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    user_data: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """
    用户登录
    """
    user = await user_service.authenticate(db, user_data.username, user_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )

    # 生成访问令牌
    access_token = create_access_token(data={"sub": str(user.id)})

    return TokenResponse(
        access_token=access_token,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """
    获取当前登录用户信息
    """
    return UserResponse.model_validate(current_user)


@router.post("/logout")
async def logout():
    """
    用户登出

    实际上只需要客户端删除 token 即可，这里主要用于记录日志等
    """
    return {"message": "登出成功"}


@router.get("/config", response_model=PublicConfigResponse)
async def get_public_config(
    db: AsyncSession = Depends(get_db),
):
    """
    获取公开配置（任何用户可访问，包括未登录用户）
    只返回地图相关配置，不返回管理相关配置
    """
    configs = await config_service.get_all_configs(db)
    return PublicConfigResponse(
        default_map_provider=configs.get("default_map_provider", "osm"),
        map_layers=configs.get("map_layers", {}),
    )
