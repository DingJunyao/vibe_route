# backend/app/services/animation_export.py

import asyncio
import uuid
from typing import Optional
from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..schemas.animation import AnimationExportRequest, AnimationExportTask as AnimationExportTaskSchema
from ..models.animation_task import AnimationExportTask
from ..models.track import Track, TrackPoint


class AnimationExportService:
    """动画导出服务"""

    def __init__(self):
        self.active_tasks: dict[str, asyncio.Task] = {}

    async def start_export(
        self,
        track_id: int,
        user_id: int,
        request: AnimationExportRequest,
        db: AsyncSession,
        background_tasks: BackgroundTasks,
    ) -> AnimationExportTaskSchema:
        """
        启动动画导出任务
        """
        # 获取轨迹点
        result = await db.execute(
            select(TrackPoint)
            .where(TrackPoint.track_id == track_id)
            .order_by(TrackPoint.index)
        )
        points = result.scalars().all()

        if len(points) < 2:
            raise ValueError("轨迹点数量不足，至少需要2个点")

        # 创建导出任务
        task_id = str(uuid.uuid4())
        task = AnimationExportTask(
            id=task_id,
            track_id=track_id,
            user_id=user_id,
            status='pending',
            progress=0.0,
        )
        db.add(task)
        await db.commit()

        # 添加后台任务
        background_tasks.add_task(
            self._export_video,
            track_id=track_id,
            points=points,
            task_id=task_id,
            request=request,
        )

        return AnimationExportTaskSchema(
            task_id=task_id,
            status='pending',
            progress=0.0,
        )

    async def _export_video(
        self,
        track_id: int,
        points: list[TrackPoint],
        task_id: str,
        request: AnimationExportRequest,
    ):
        """
        执行视频导出
        """
        from ..core.database import async_session_maker

        async with async_session_maker() as db:
            # 更新状态为处理中
            result = await db.execute(
                select(AnimationExportTask).where(AnimationExportTask.id == task_id)
            )
            task = result.scalar_one_or_none()
            if task:
                task.status = 'processing'
                await db.commit()

        try:
            # 使用 Playwright 录制视频
            from ..utils.playwright_export import capture_animation_video

            async def progress_callback(p: float):
                """进度回调"""
                async with async_session_maker() as db:
                    result = await db.execute(
                        select(AnimationExportTask).where(AnimationExportTask.id == task_id)
                    )
                    task = result.scalar_one_or_none()
                    if task:
                        task.progress = p
                        await db.commit()

            download_url = await capture_animation_video(
                track_id=track_id,
                points=points,
                resolution=request.resolution,
                fps=request.fps,
                show_hud=request.show_hud,
                speed=request.speed,
                progress_callback=progress_callback,
            )

            # 更新为完成状态
            async with async_session_maker() as db:
                result = await db.execute(
                    select(AnimationExportTask).where(AnimationExportTask.id == task_id)
                )
                task = result.scalar_one_or_none()
                if task:
                    task.status = 'completed'
                    task.progress = 100.0
                    task.download_url = download_url
                    await db.commit()

        except Exception as e:
            # 更新为失败状态
            async with async_session_maker() as db:
                result = await db.execute(
                    select(AnimationExportTask).where(AnimationExportTask.id == task_id)
                )
                task = result.scalar_one_or_none()
                if task:
                    task.status = 'failed'
                    task.error = str(e)
                    await db.commit()
            raise

        finally:
            # 清理任务引用
            self.active_tasks.pop(task_id, None)

    async def cancel_task(
        self,
        task_id: str,
    ) -> bool:
        """
        取消导出任务
        """
        if task_id in self.active_tasks:
            task = self.active_tasks.pop(task_id)
            task.cancel()
            return True
        return False
