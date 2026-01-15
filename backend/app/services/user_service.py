"""
用户服务层
"""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.core.security import get_password_hash, verify_password


class UserService:
    """用户服务类"""

    async def get_by_id(self, db: AsyncSession, user_id: int) -> Optional[User]:
        """根据 ID 获取用户"""
        result = await db.execute(
            select(User).where(and_(User.id == user_id, User.is_valid == True))
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, db: AsyncSession, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        result = await db.execute(
            select(User).where(and_(User.username == username, User.is_valid == True))
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        """根据邮箱获取用户"""
        result = await db.execute(
            select(User).where(and_(User.email == email, User.is_valid == True))
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        db: AsyncSession,
        username: str,
        email: str,
        password: str,
        is_admin: bool = False,
        created_by: int = None,
    ) -> User:
        """创建用户"""
        user = User(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            is_admin=is_admin,
            created_by=created_by,
            updated_by=created_by,
            is_valid=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    async def authenticate(
        self,
        db: AsyncSession,
        username: str,
        password: str,
    ) -> Optional[User]:
        """验证用户凭据"""
        user = await self.get_by_username(db, username)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    async def count_all(self, db: AsyncSession) -> int:
        """获取所有用户数量"""
        from sqlalchemy import func
        result = await db.execute(
            select(func.count(User.id)).where(User.is_valid == True)
        )
        return result.scalar() or 0

    async def get_list(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
    ) -> list[User]:
        """获取用户列表"""
        result = await db.execute(
            select(User)
            .where(User.is_valid == True)
            .offset(skip)
            .limit(limit)
            .order_by(User.id)
        )
        return list(result.scalars().all())

    async def update(
        self,
        db: AsyncSession,
        user: User,
        user_id: int = None,
        **kwargs
    ) -> User:
        """更新用户"""
        for key, value in kwargs.items():
            if value is not None and hasattr(user, key):
                setattr(user, key, value)
        if user_id:
            user.updated_by = user_id
        user.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(user)
        return user

    async def delete(self, db: AsyncSession, user: User, operator_id: int) -> None:
        """软删除用户"""
        user.is_valid = False
        user.updated_by = operator_id
        user.updated_at = datetime.now(timezone.utc)
        await db.commit()


user_service = UserService()
