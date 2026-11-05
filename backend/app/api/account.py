from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.rate_limit import limiter
from app.models.user import User
from app.schemas.user import ChangePasswordRequest, ProfileUpdate, UserResponse
from app.services.user_service import user_service

router = APIRouter(prefix='/auth', tags=['account'])


@router.post('/change-password')
@limiter.limit('5/minute')
async def change_password(
    request: Request,
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    changed = await user_service.change_password(
        db,
        current_user,
        password_data.old_password,
        password_data.new_password,
    )
    if not changed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='\u65e7\u5bc6\u7801\u9519\u8bef',
        )
    return {'message': '\u5bc6\u7801\u4fee\u6539\u6210\u529f'}


@router.put('/profile', response_model=UserResponse)
async def update_profile(
    profile_data: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新个人资料（当前仅支持修改用户名）"""
    new_username = profile_data.username.strip()

    if new_username != current_user.username:
        existing = await user_service.get_by_username(db, new_username)
        if existing and existing.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='用户名已被使用',
            )

    try:
        # 目标用户名若被软删除用户的墓碑占用，先改写墓碑名释放该名称
        await user_service.release_deleted_username(
            db, new_username, operator_id=current_user.id
        )
        updated = await user_service.update(
            db, current_user, current_user.id, username=new_username
        )
    except IntegrityError:
        # 兜底：唯一索引冲突仍按"用户名已被使用"处理
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='用户名已被使用',
        )

    return UserResponse.model_validate(updated)
