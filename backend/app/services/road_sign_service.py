"""
道路标志服务
"""
import os
import hashlib
from typing import Optional
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.road_sign import RoadSignCache
from app.gpxutil_wrapper.svg_gen import generate_road_sign
from app.core.config import settings
from loguru import logger


class RoadSignService:
    """道路标志服务类"""

    def _get_cache_dir(self) -> str:
        """获取缓存目录"""
        cache_dir = os.path.join(settings.BASE_DIR, "data", "road_signs")
        os.makedirs(cache_dir, exist_ok=True)
        return cache_dir

    def _generate_cache_key(
        self,
        sign_type: str,
        code: str,
        province: Optional[str] = None,
        name: Optional[str] = None
    ) -> str:
        """生成缓存键"""
        key_data = f"{sign_type}:{code}:{province or ''}:{name or ''}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _get_svg_path(self, cache_key: str) -> str:
        """获取 SVG 文件路径"""
        return os.path.join(self._get_cache_dir(), f"{cache_key}.svg")

    async def get_or_create_sign(
        self,
        db: AsyncSession,
        sign_type: str,
        code: str,
        province: Optional[str] = None,
        name: Optional[str] = None
    ) -> tuple[str, bool]:
        """
        获取或创建道路标志

        Args:
            db: 数据库会话
            sign_type: 标志类型 ('way' 或 'expwy')
            code: 道路编号
            province: 省份（仅高速用）
            name: 道路名称

        Returns:
            (SVG 内容, 是否是缓存)
        """
        cache_key = self._generate_cache_key(sign_type, code, province, name)
        svg_path = self._get_svg_path(cache_key)

        # 检查缓存
        result = await db.execute(
            select(RoadSignCache).where(RoadSignCache.id == cache_key)
        )
        cached = result.scalar_one_or_none()

        if cached and os.path.exists(cached.svg_path):
            # 从缓存读取
            try:
                with open(cached.svg_path, 'r', encoding='utf-8') as f:
                    return f.read(), True
            except Exception as e:
                logger.warning(f"Failed to read cached sign {cache_key}: {e}")

        # 生成新的 SVG
        try:
            svg_content = generate_road_sign(
                sign_type=sign_type,
                code=code,
                province=province,
                name=name,
                output_path=svg_path
            )

            # 保存到缓存
            if cached:
                cached.svg_path = svg_path
            else:
                cached = RoadSignCache(
                    id=cache_key,
                    code=code,
                    province=province,
                    name=name,
                    svg_path=svg_path
                )
                db.add(cached)

            await db.commit()

            # 读取生成的文件
            with open(svg_path, 'r', encoding='utf-8') as f:
                return f.read(), False

        except Exception as e:
            logger.error(f"Failed to generate road sign: {e}")
            raise

    async def get_list(
        self,
        db: AsyncSession,
        sign_type: Optional[str] = None,
        limit: int = 50
    ) -> list[RoadSignCache]:
        """
        获取缓存的标志列表

        Args:
            db: 数据库会话
            sign_type: 筛选标志类型
            limit: 返回数量

        Returns:
            标志缓存列表
        """
        query = select(RoadSignCache)

        # 根据代码前缀筛选类型
        if sign_type == 'way':
            # G, S, X, Y, Z, C 开头的
            query = query.where(
                or_(
                    RoadSignCache.code.like('G%'),
                    RoadSignCache.code.like('S%'),
                    RoadSignCache.code.like('X%'),
                    RoadSignCache.code.like('Y%'),
                    RoadSignCache.code.like('Z%'),
                    RoadSignCache.code.like('C%'),
                )
            )
        elif sign_type == 'expwy':
            # 有省份或名称的，或 G/S 开头的长编号
            query = query.where(
                or_(
                    RoadSignCache.province.isnot(None),
                    RoadSignCache.name.isnot(None),
                )
            )

        query = query.order_by(RoadSignCache.id.desc()).limit(limit)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def clear_cache(self, db: AsyncSession, sign_type: Optional[str] = None) -> int:
        """
        清除缓存

        Args:
            db: 数据库会话
            sign_type: 筛选标志类型

        Returns:
            清除的数量
        """
        # 获取要删除的缓存
        caches = await self.get_list(db, sign_type, limit=999999)

        count = 0
        for cache in caches:
            # 删除文件
            try:
                if os.path.exists(cache.svg_path):
                    os.remove(cache.svg_path)
            except Exception as e:
                logger.warning(f"Failed to delete cache file {cache.svg_path}: {e}")

            # 删除数据库记录
            await db.delete(cache)
            count += 1

        await db.commit()
        return count


road_sign_service = RoadSignService()
