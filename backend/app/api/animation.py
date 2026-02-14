# backend/app/api/animation.py

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..core.database import get_db
from ..core.deps import get_current_user
from ..models.user import User
from ..schemas.animation import AnimationExportRequest, AnimationExportTask as AnimationExportTaskSchema
from ..services.animation_export import AnimationExportService


router = APIRouter(tags=['animation'])


@router.post("/animation/export", response_model=AnimationExportTaskSchema)
async def export_animation(
    background_tasks: BackgroundTasks,
    track_id: int,
    request: AnimationExportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    启动动画导出

    需要用户登录，只能导出自己的轨迹。
    """
    # 验证轨迹是否属于当前用户
    from ..models.track import Track

    result = await db.execute(
        select(Track).where(Track.id == track_id, Track.user_id == current_user.id)
    )
    track = result.scalar_one_or_none()

    if not track:
        raise HTTPException(status_code=404, detail="轨迹不存在或无权访问")

    service = AnimationExportService()

    try:
        task = await service.start_export(
            track_id=track_id,
            user_id=current_user.id,
            request=request,
            db=db,
            background_tasks=background_tasks,
        )
        return task
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@router.get("/animation/export/{task_id}", response_model=AnimationExportTaskSchema)
async def get_export_progress(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取导出进度
    """
    from ..models.animation_task import AnimationExportTask

    result = await db.execute(
        select(AnimationExportTask).where(AnimationExportTask.id == task_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问此任务")

    return AnimationExportTaskSchema(
        task_id=task.id,
        status=task.status,
        progress=task.progress,
        download_url=task.download_url,
        error=task.error,
    )


@router.delete("/animation/export/{task_id}")
async def cancel_export(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    取消导出任务
    """
    from ..models.animation_task import AnimationExportTask

    result = await db.execute(
        select(AnimationExportTask).where(AnimationExportTask.id == task_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问此任务")

    if task.status in ['pending', 'processing']:
        # 标记任务为已取消
        task.status = 'cancelled'
        task.error = '用户取消'
        await db.commit()

    return {'message': '任务已取消'}
