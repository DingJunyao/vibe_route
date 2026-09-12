from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.rate_limit import limiter
from app.models.user import User
from app.schemas.user import ChangePasswordRequest
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
