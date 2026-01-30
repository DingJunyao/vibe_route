"""
依赖注入模块
"""
from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.models.live_recording import LiveRecording
from app.services.live_recording_service import live_recording_service


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    获取当前登录用户

    Args:
        request: FastAPI Request 对象
        db: 数据库会话

    Returns:
        当前用户对象

    Raises:
        HTTPException: 认证失败时
    """
    # 获取 Authorization header
    authorization = request.headers.get("authorization")

    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少认证凭据",
        )

    # 解析 Bearer token
    parts = authorization.split()
    if parts[0].lower() != "bearer" or len(parts) != 2:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证格式",
        )

    token = parts[1]
    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
        )

    user_id: Optional[int] = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
        )

    # 将字符串转换为整数
    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
        )

    from app.services.user_service import user_service
    user = await user_service.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    获取当前活跃用户

    Args:
        current_user: 当前用户

    Returns:
        活跃用户对象

    Raises:
        HTTPException: 用户未激活时
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )
    return current_user


async def get_current_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    获取当前管理员用户

    Args:
        current_user: 当前用户

    Returns:
        管理员用户对象

    Raises:
        HTTPException: 用户不是管理员时
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return current_user


async def get_live_recording(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> LiveRecording:
    """
    通过 token 获取实时记录

    Args:
        token: 实时记录 token
        db: 数据库会话

    Returns:
        实时记录对象

    Raises:
        HTTPException: token 无效或记录不存在时
    """
    recording = await live_recording_service.get_by_token(db, token)
    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="无效的 token",
        )

    if recording.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="记录已结束",
        )

    return recording
