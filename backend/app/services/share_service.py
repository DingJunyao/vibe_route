"""
分享服务层
"""
import random
import string
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track
from app.models.user_config import UserConfig


def generate_share_token(length: int = 8) -> str:
    """生成随机分享令牌（字母数字混合）"""
    # 使用大写字母和数字，去除易混淆的字符（0OIl1）
    charset = string.ascii_uppercase.replace('O', '').replace('I', '') + string.digits.replace('0', '').replace('1', '')
    # 添加小写字母以增加空间
    charset += string.ascii_lowercase.replace('l', '').replace('o', '')
    return ''.join(random.choices(charset, k=length))


async def ensure_unique_token(db: AsyncSession, length: int = 8, max_attempts: int = 10) -> str:
    """确保生成的 token 在数据库中唯一"""
    for _ in range(max_attempts):
        token = generate_share_token(length)
        result = await db.execute(
            select(Track.share_token).where(Track.share_token == token)
        )
        if result.scalar_one_or_none() is None:
            return token
    # 如果多次尝试都失败，增加长度重试
    return await ensure_unique_token(db, length + 1, max_attempts)


class ShareService:
    """分享服务类"""

    async def create_share(
        self, db: AsyncSession, track_id: int, user_id: int
    ) -> Optional[Track]:
        """创建分享（生成 token 并启用）"""
        result = await db.execute(
            select(Track).where(
                and_(
                    Track.id == track_id,
                    Track.user_id == user_id,
                    Track.is_valid == True
                )
            )
        )
        track = result.scalar_one_or_none()
        if not track:
            return None

        # 如果没有 token，生成新的
        if not track.share_token:
            track.share_token = await ensure_unique_token(db, 8)

        track.is_shared = True
        track.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        await db.commit()
        await db.refresh(track)
        return track

    async def enable_share(
        self, db: AsyncSession, track_id: int, user_id: int
    ) -> Optional[Track]:
        """启用分享（使用已有 token）"""
        result = await db.execute(
            select(Track).where(
                and_(
                    Track.id == track_id,
                    Track.user_id == user_id,
                    Track.is_valid == True
                )
            )
        )
        track = result.scalar_one_or_none()
        if not track:
            return None

        # 确保 token 存在
        if not track.share_token:
            track.share_token = await ensure_unique_token(db, 8)

        track.is_shared = True
        track.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        await db.commit()
        await db.refresh(track)
        return track

    async def disable_share(
        self, db: AsyncSession, track_id: int, user_id: int
    ) -> Optional[Track]:
        """禁用分享（不删除 token）"""
        result = await db.execute(
            select(Track).where(
                and_(
                    Track.id == track_id,
                    Track.user_id == user_id,
                    Track.is_valid == True
                )
            )
        )
        track = result.scalar_one_or_none()
        if not track:
            return None

        track.is_shared = False
        track.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        await db.commit()
        await db.refresh(track)
        return track

    async def get_share_status(
        self, db: AsyncSession, track_id: int, user_id: int
    ) -> Optional[dict]:
        """获取分享状态"""
        result = await db.execute(
            select(Track).where(
                and_(
                    Track.id == track_id,
                    Track.user_id == user_id,
                    Track.is_valid == True
                )
            )
        )
        track = result.scalar_one_or_none()
        if not track:
            return None

        return {
            "is_shared": track.is_shared,
            "share_token": track.share_token,
        }

    async def get_shared_track(
        self, db: AsyncSession, token: str
    ) -> Optional[Track]:
        """根据分享 token 获取轨迹"""
        result = await db.execute(
            select(Track).where(
                and_(
                    Track.share_token == token,
                    Track.is_shared == True,
                    Track.is_valid == True
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_shared_user_config(
        self, db: AsyncSession, track: Track
    ) -> Optional[UserConfig]:
        """获取分享者的用户配置"""
        result = await db.execute(
            select(UserConfig).where(
                and_(
                    UserConfig.user_id == track.user_id,
                    UserConfig.is_valid == True
                )
            )
        )
        return result.scalar_one_or_none()


share_service = ShareService()
