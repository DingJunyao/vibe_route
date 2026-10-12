# backend/app/services/recording_cleanup.py
"""录屏文件保留期清理服务

按管理员配置的保存天数（animation_export_retention_days，按任务结束时间起算），
周期删除过期的录屏文件并将任务标记为 expired；同时回收失败任务遗留的逐帧目录。
0 = 永久保留，跳过清理。
"""
import asyncio
import shutil
from datetime import timedelta
from pathlib import Path
from typing import Optional
from loguru import logger
from sqlalchemy import select, func

from ..core.config import settings
from ..models.animation_task import AnimationExportTask
from ..models.base import get_utc_now

# 周期清理间隔：6 小时（启动时也会先执行一次）
CLEANUP_INTERVAL_S = 6 * 3600


class RecordingCleanupService:
    """录屏文件保留期清理"""

    def __init__(self):
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())
            logger.info("Recording cleanup task started")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            logger.info("Recording cleanup task stopped")

    async def _loop(self) -> None:
        while True:
            try:
                cleaned = await self.cleanup_expired()
                if cleaned:
                    logger.info(f"Recording cleanup: removed {cleaned} expired items")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Recording cleanup error: {e}")
            await asyncio.sleep(CLEANUP_INTERVAL_S)

    @staticmethod
    def _resolve_file(export_root: Path, download_url: str) -> Optional[Path]:
        """把任务里的相对路径解析到 EXPORT_DIR 下（防穿越），与下载端点同一规则"""
        relative = download_url.replace('\\', '/').lstrip('/')
        if relative.startswith('exports/'):
            relative = relative[len('exports/'):]
        file_path = (export_root / relative).resolve()
        if not file_path.is_relative_to(export_root):
            return None
        return file_path

    async def cleanup_expired(self) -> int:
        """删除超过保留期的录屏文件并标记任务过期，返回处理数量"""
        from ..core.database import async_session_maker
        from .config_service import config_service

        async with async_session_maker() as db:
            try:
                days = int(await config_service.get_json(db, 'animation_export_retention_days', 30))
            except (TypeError, ValueError):
                days = 30
            if days <= 0:
                return 0

            cutoff = get_utc_now() - timedelta(days=days)
            now = get_utc_now()

            result = await db.execute(
                select(AnimationExportTask).where(
                    AnimationExportTask.status == 'completed',
                    AnimationExportTask.is_valid == True,  # noqa: E712
                    # 历史任务无 finished_at，按创建时间起算
                    func.coalesce(AnimationExportTask.finished_at, AnimationExportTask.created_at) < cutoff,
                )
            )
            tasks = result.scalars().all()
            if not tasks:
                return 0

            export_root = Path(settings.EXPORT_DIR).resolve()
            cleaned = 0
            for task in tasks:
                if task.download_url:
                    file_path = self._resolve_file(export_root, task.download_url)
                    if file_path is not None and file_path.is_file():
                        try:
                            file_path.unlink()
                        except OSError as e:
                            logger.warning(f"Recording cleanup: failed to remove {file_path}: {e}")
                task.status = 'expired'
                task.download_url = None
                task.updated_at = now
                cleaned += 1

            await db.commit()

        # 兜底回收失败任务遗留的逐帧目录（按目录修改时间判断，超过保留期即删）
        self._cleanup_stale_frames(export_root, cutoff)
        return cleaned

    @staticmethod
    def _cleanup_stale_frames(export_root: Path, cutoff) -> None:
        frames_root = export_root / 'animation' / 'frames'
        if not frames_root.is_dir():
            return
        try:
            cutoff_ts = cutoff.timestamp()
            for entry in frames_root.iterdir():
                if entry.is_dir():
                    try:
                        if entry.stat().st_mtime < cutoff_ts:
                            shutil.rmtree(entry, ignore_errors=True)
                    except OSError:
                        continue
        except OSError:
            pass


recording_cleanup_service = RecordingCleanupService()
