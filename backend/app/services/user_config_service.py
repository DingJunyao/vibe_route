"""
用户配置服务层
"""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_config import UserConfig


class UserConfigService:
    """用户配置服务类"""

    async def get_user_config(self, db: AsyncSession, user_id: int) -> Optional[UserConfig]:
        """获取用户配置"""
        result = await db.execute(
            select(UserConfig).where(
                and_(UserConfig.user_id == user_id, UserConfig.is_valid == True)
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create_config(
        self, db: AsyncSession, user_id: int
    ) -> UserConfig:
        """获取或创建用户配置"""
        config = await self.get_user_config(db, user_id)
        if config:
            return config

        # 创建新配置
        config = UserConfig(
            user_id=user_id,
            map_provider=None,
            map_layers=None,
            is_valid=True,
        )
        db.add(config)
        await db.commit()
        await db.refresh(config)
        return config

    async def update_config(
        self,
        db: AsyncSession,
        user_id: int,
        map_provider: Optional[str] = None,
        map_layers: Optional[dict] = None,
        updated_by: Optional[int] = None,
    ) -> Optional[UserConfig]:
        """更新用户配置"""
        config = await self.get_or_create_config(db, user_id)

        if map_provider is not None:
            config.map_provider = map_provider
        if map_layers is not None:
            config.map_layers = map_layers

        config.updated_by = updated_by
        config.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        await db.commit()
        await db.refresh(config)
        return config

    async def reset_config(
        self, db: AsyncSession, user_id: int, operator_id: int
    ) -> Optional[UserConfig]:
        """重置用户配置为默认（软删除）"""
        config = await self.get_user_config(db, user_id)
        if config:
            config.is_valid = False
            config.updated_by = operator_id
            config.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await db.commit()

        # 返回空配置（前端会使用系统默认）
        return None


user_config_service = UserConfigService()
