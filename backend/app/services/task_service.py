"""
任务处理服务
管理异步任务的创建、更新和执行
"""
import os
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.task import Task
from app.models.track import Track
from app.gpxutil_wrapper.overlay import OverlayGenerator, OverlayConfig


class TaskService:
    """任务服务"""

    @staticmethod
    async def create_task(
        db: AsyncSession,
        user_id: int,
        task_type: str
    ) -> Task:
        """创建新任务"""
        task = Task(
            user_id=user_id,
            type=task_type,
            status="pending",
            progress=0
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task

    @staticmethod
    async def get_task(db: AsyncSession, task_id: int) -> Optional[Task]:
        """获取任务"""
        result = await db.execute(
            select(Task).where(Task.id == task_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def update_task(
        db: AsyncSession,
        task_id: int,
        status: Optional[str] = None,
        progress: Optional[int] = None,
        result_path: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> Optional[Task]:
        """更新任务状态"""
        update_values = {}
        if status is not None:
            update_values["status"] = status
        if progress is not None:
            update_values["progress"] = progress
        if result_path is not None:
            update_values["result_path"] = result_path
        if error_message is not None:
            update_values["error_message"] = error_message

        if update_values:
            await db.execute(
                update(Task)
                .where(Task.id == task_id)
                .values(**update_values)
            )
            await db.commit()

        return await TaskService.get_task(db, task_id)

    @staticmethod
    async def get_user_tasks(
        db: AsyncSession,
        user_id: int,
        limit: int = 50
    ) -> list[Task]:
        """获取用户的任务列表"""
        result = await db.execute(
            select(Task)
            .where(Task.user_id == user_id)
            .order_by(Task.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def generate_overlay(
        db: AsyncSession,
        track_id: int,
        user_id: int,
        config: Optional[OverlayConfig] = None
    ) -> Task:
        """
        生成信息覆盖层

        Returns:
            Task: 创建的任务对象
        """
        # 验证轨迹存在且属于该用户
        result = await db.execute(
            select(Track).where(Track.id == track_id, Track.user_id == user_id)
        )
        track = result.scalar_one_or_none()
        if not track:
            raise ValueError("轨迹不存在或无权访问")

        # 创建任务
        task = await TaskService.create_task(db, user_id, "overlay_generate")

        try:
            # 更新状态为运行中
            await TaskService.update_task(db, task.id, status="running", progress=10)

            # 生成覆盖层
            generator = OverlayGenerator(config)
            result_path, image_count = await generator.generate(db, track_id, user_id)

            # 更新任务为完成
            await TaskService.update_task(
                db, task.id,
                status="completed",
                progress=100,
                result_path=result_path
            )

            # 重新获取任务返回
            return await TaskService.get_task(db, task.id)

        except Exception as e:
            # 更新任务为失败
            await TaskService.update_task(
                db, task.id,
                status="failed",
                error_message=str(e)
            )
            raise


task_service = TaskService()
