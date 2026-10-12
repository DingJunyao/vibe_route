# backend/app/api/animation.py

from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..core.config import settings
from ..core.database import get_db
from ..core.deps import get_current_admin_user, get_current_user
from ..models.animation_task import AnimationExportTask
from ..models.track import Track
from ..models.user import User
from ..schemas.animation import (
    AnimationExportRequest,
    AnimationExportTask as AnimationExportTaskSchema,
    AnimationExportTaskList,
)
from ..services.animation_export import ExportQueueLimitError
from ..services.animation_export import animation_export_service as export_service
from ..services.recording_cleanup import recording_cleanup_service

router = APIRouter(tags=['animation'])


def _task_to_schema(
    task: AnimationExportTask,
    track_title: Optional[str] = None,
    username: Optional[str] = None,
    queue_position: Optional[int] = None,
) -> AnimationExportTaskSchema:
    download_url = (
        f"/api/animation/export/{task.id}/download"
        if task.status == 'completed' and task.download_url
        else None
    )
    return AnimationExportTaskSchema(
        task_id=task.id,
        status=task.status,
        progress=task.progress,
        download_url=download_url,
        error=task.error,
        track_id=task.track_id,
        track_title=track_title,
        username=username,
        queue_position=queue_position,
        created_at=task.created_at,
        started_at=task.started_at,
        finished_at=task.finished_at,
    )


async def _get_queue_position(db: AsyncSession, task: AnimationExportTask) -> Optional[int]:
    """排队位次：排在它前面的 pending 任务数 + 1"""
    if task.status != 'pending':
        return None
    result = await db.execute(
        select(func.count())
        .select_from(AnimationExportTask)
        .where(
            AnimationExportTask.status == 'pending',
            AnimationExportTask.is_valid == True,  # noqa: E712
            AnimationExportTask.created_at < task.created_at,
        )
    )
    return (result.scalar() or 0) + 1


async def _attach_queue_positions(
    db: AsyncSession,
    tasks: list[AnimationExportTask],
) -> dict[str, int]:
    """给列表里的 pending 任务计算排队位次（按全局 pending 先后次序），
    返回 {task_id: position}"""
    if not any(t.status == 'pending' for t in tasks):
        return {}
    result = await db.execute(
        select(AnimationExportTask.id)
        .where(
            AnimationExportTask.status == 'pending',
            AnimationExportTask.is_valid == True,  # noqa: E712
        )
        .order_by(AnimationExportTask.created_at.asc(), AnimationExportTask.id.asc())
    )
    return {row[0]: idx + 1 for idx, row in enumerate(result.all())}


@router.post("/animation/export", response_model=AnimationExportTaskSchema)
async def export_animation(
    req: Request,
    track_id: int,
    request: AnimationExportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    启动动画导出（进入录屏任务队列）

    需要用户登录，只能导出自己的轨迹。任务入队后立即返回，
    进度请通过录屏任务页（GET /animation/export/my）查看。
    """
    # 验证轨迹是否属于当前用户
    result = await db.execute(
        select(Track).where(Track.id == track_id, Track.user_id == current_user.id)
    )
    track = result.scalar_one_or_none()

    if not track:
        raise HTTPException(status_code=404, detail="轨迹不存在或无权访问")

    # 提取 token（供 Playwright 注入页面复用登录会话）
    authorization = req.headers.get("authorization") or ""
    scheme, _, credentials = authorization.partition(" ")
    token = credentials.strip() if scheme.lower() == "bearer" else ""

    try:
        task = await export_service.start_export(
            track_id=track_id,
            user_id=current_user.id,
            token=token,
            request=request,
            db=db,
        )
        return task
    except ExportQueueLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="导出失败")


@router.get("/animation/export/my", response_model=AnimationExportTaskList)
async def list_my_exports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """我的录屏任务列表（分页，按创建时间倒序）"""
    conditions = [
        AnimationExportTask.user_id == current_user.id,
        AnimationExportTask.is_valid == True,  # noqa: E712
    ]
    if status:
        conditions.append(AnimationExportTask.status == status)

    total_result = await db.execute(
        select(func.count()).select_from(AnimationExportTask).where(*conditions)
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        select(AnimationExportTask, Track.name)
        .join(Track, Track.id == AnimationExportTask.track_id)
        .where(*conditions)
        .order_by(AnimationExportTask.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = result.all()
    positions = await _attach_queue_positions(db, [task for task, _ in rows])
    items = [
        _task_to_schema(task, track_title=track_name, queue_position=positions.get(task.id))
        for task, track_name in rows
    ]
    return AnimationExportTaskList(total=total, items=items)


@router.get("/animation/export/admin/tasks", response_model=AnimationExportTaskList)
async def list_all_exports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    username: Optional[str] = Query(None),
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """全部用户的录屏任务列表（管理员，分页，可按状态/用户名筛选）"""
    conditions = [AnimationExportTask.is_valid == True]  # noqa: E712
    if status:
        conditions.append(AnimationExportTask.status == status)
    if username:
        conditions.append(User.username.contains(username))

    total_result = await db.execute(
        select(func.count())
        .select_from(AnimationExportTask)
        .join(User, User.id == AnimationExportTask.user_id)
        .where(*conditions)
    )
    total = total_result.scalar() or 0

    result = await db.execute(
        select(AnimationExportTask, Track.name, User.username)
        .join(Track, Track.id == AnimationExportTask.track_id)
        .join(User, User.id == AnimationExportTask.user_id)
        .where(*conditions)
        .order_by(AnimationExportTask.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = result.all()
    positions = await _attach_queue_positions(db, [task for task, _, _ in rows])
    items = [
        _task_to_schema(
            task,
            track_title=track_name,
            username=username_,
            queue_position=positions.get(task.id),
        )
        for task, track_name, username_ in rows
    ]
    return AnimationExportTaskList(total=total, items=items)


@router.post("/animation/export/admin/cleanup")
async def cleanup_expired_exports(
    current_admin: User = Depends(get_current_admin_user),
):
    """立即清理超过保存时限的录屏文件（管理员，返回处理数量）"""
    cleaned = await recording_cleanup_service.cleanup_expired()
    return {"cleaned": cleaned}


@router.get("/animation/export/{task_id}", response_model=AnimationExportTaskSchema)
async def get_export_progress(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取导出任务详情（本人或管理员）
    """
    result = await db.execute(
        select(AnimationExportTask, Track.name)
        .join(Track, Track.id == AnimationExportTask.track_id)
        .where(AnimationExportTask.id == task_id)
    )
    row = result.first()

    if not row:
        raise HTTPException(status_code=404, detail="任务不存在")

    task, track_title = row
    if task.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="无权访问此任务")

    queue_position = await _get_queue_position(db, task)
    return _task_to_schema(task, track_title=track_title, queue_position=queue_position)


@router.get("/animation/export/{task_id}/download")
async def download_export(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """下载任务结果文件，并校验任务所有权。"""
    result = await db.execute(
        select(AnimationExportTask).where(AnimationExportTask.id == task_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="无权访问此任务")
    if task.status != 'completed' or not task.download_url:
        raise HTTPException(status_code=400, detail="任务未完成或无结果文件")

    relative = task.download_url.replace('\\', '/').lstrip('/')
    if relative.startswith('exports/'):
        relative = relative[len('exports/'):]
    export_root = Path(settings.EXPORT_DIR).resolve()
    file_path = (export_root / relative).resolve()

    if not file_path.is_relative_to(export_root) or not file_path.is_file():
        raise HTTPException(status_code=404, detail="结果文件不存在")

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="video/mp4",
    )


@router.delete("/animation/export/{task_id}")
async def cancel_or_delete_export(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    取消或删除导出任务（本人或管理员）

    - pending / processing：取消任务，正在排队的任务立即出队，
      正在录制的任务中断，并马上调度下一个排队任务；
    - completed / failed / cancelled / expired：删除任务记录与视频文件。
    """
    result = await db.execute(
        select(AnimationExportTask).where(AnimationExportTask.id == task_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="无权访问此任务")

    if task.status in ('pending', 'processing'):
        new_status = await export_service.cancel_task(task_id)
        if new_status is None:
            raise HTTPException(status_code=404, detail="任务不存在")
        return {'message': '任务已取消', 'status': new_status}

    # 终态任务：删除记录与文件
    if task.download_url:
        relative = task.download_url.replace('\\', '/').lstrip('/')
        if relative.startswith('exports/'):
            relative = relative[len('exports/'):]
        export_root = Path(settings.EXPORT_DIR).resolve()
        file_path = (export_root / relative).resolve()
        if file_path.is_relative_to(export_root) and file_path.is_file():
            try:
                file_path.unlink()
            except OSError:
                pass  # 文件删除失败不阻塞记录清理

    task.is_valid = False
    task.updated_by = current_user.id
    await db.commit()
    return {'message': '任务已删除', 'status': task.status}
