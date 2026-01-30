"""
简单内存缓存工具
用于缓存频繁访问的配置数据
"""
import asyncio
from typing import Dict, Optional, Any, Callable
from datetime import datetime, timedelta, timezone
from loguru import logger


class SimpleCache:
    """简单的内存缓存实现"""

    def __init__(self, default_ttl: int = 300):
        """
        初始化缓存

        Args:
            default_ttl: 默认过期时间（秒），默认 5 分钟
        """
        self._cache: Dict[str, tuple[Any, datetime]] = {}
        self.default_ttl = default_ttl
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start_cleanup_task(self):
        """启动定期清理过期缓存的任务"""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self):
        """定期清理过期缓存"""
        while True:
            try:
                await asyncio.sleep(60)  # 每分钟清理一次
                self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cache cleanup error: {e}")

    def _cleanup_expired(self):
        """清理过期的缓存项"""
        now = datetime.now(timezone.utc)
        expired_keys = [
            key for key, (_, expires_at) in self._cache.items()
            if expires_at < now
        ]
        for key in expired_keys:
            del self._cache[key]
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

    async def stop_cleanup_task(self):
        """停止清理任务"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，如果不存在或已过期则返回 None
        """
        if key not in self._cache:
            return None

        value, expires_at = self._cache[key]
        if datetime.now(timezone.utc) > expires_at:
            del self._cache[key]
            return None

        return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），默认使用 default_ttl
        """
        if ttl is None:
            ttl = self.default_ttl
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)
        self._cache[key] = (value, expires_at)

    def delete(self, key: str) -> None:
        """删除缓存值"""
        self._cache.pop(key, None)

    def clear(self) -> None:
        """清空所有缓存"""
        self._cache.clear()

    def get_or_set(self, key: str, factory: Callable[[], Any], ttl: Optional[int] = None) -> Any:
        """
        获取缓存值，如果不存在则通过 factory 函数创建

        Args:
            key: 缓存键
            factory: 创建值的函数
            ttl: 过期时间（秒）

        Returns:
            缓存值或新创建的值
        """
        value = self.get(key)
        if value is not None:
            return value

        value = factory()
        self.set(key, value, ttl)
        return value


# 全局缓存实例
config_cache = SimpleCache(default_ttl=300)  # 配置缓存 5 分钟
