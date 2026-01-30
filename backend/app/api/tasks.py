"""
任务相关 API
"""
import logging
import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.task import Task
from app.services.task_service import task_service
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class TaskResponse(BaseModel):
    """任务响应"""
    id: int
    type: str
    status: str
    progress: int
    result_path: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    is_finished: bool


class CreateOverlayTaskRequest(BaseModel):
    """创建覆盖层任务请求"""
    track_id: int
    image_width: Optional[int] = 1920
    image_height: Optional[int] = 1080
    font_size: Optional[int] = 48
    show_coords: Optional[bool] = True
    show_elevation: Optional[bool] = True
    show_road_info: Optional[bool] = True


def task_to_response(task: Task) -> TaskResponse:
    """转换任务对象为响应"""
    return TaskResponse(
        id=task.id,
        type=task.type,
        status=task.status,
        progress=task.progress,
        result_path=task.result_path,
        error_message=task.error_message,
        created_at=task.created_at.isoformat(),
        is_finished=task.is_finished,
    )


@router.post("/generate-overlay", response_model=TaskResponse)
async def generate_overlay(
    request: CreateOverlayTaskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    生成轨迹信息覆盖层

    创建一个异步任务，为轨迹生成带有道路信息的 PNG 图片序列并打包为 ZIP。
    """
    from app.gpxutil_wrapper.overlay import OverlayConfig

    config = OverlayConfig(
        image_width=request.image_width,
        image_height=request.image_height,
        font_size=request.font_size,
        show_coords=request.show_coords,
        show_elevation=request.show_elevation,
        show_road_info=request.show_road_info,
    )

    try:
        task = await task_service.generate_overlay(
            db=db,
            track_id=request.track_id,
            user_id=current_user.id,
            config=config
        )
        return task_to_response(task)
    except ValueError as e:
        logger.error(f"ValueError in generate_overlay for track {request.track_id}: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Exception in generate_overlay for track {request.track_id}, user {current_user.id}")
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取任务状态"""
    task = await task_service.get_task(db, task_id)

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="无权访问此任务")

    return task_to_response(task)


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    limit: int = Query(50, ge=1, le=200, description="返回数量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的任务列表"""
    tasks = await task_service.get_user_tasks(db, current_user.id, limit)
    return [task_to_response(t) for t in tasks]


@router.get("/{task_id}/download")
async def download_task_result(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    下载任务结果文件

    返回 ZIP 文件下载
    """
    task = await task_service.get_task(db, task_id)

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="无权访问此任务")

    if task.status != "completed" or not task.result_path:
        raise HTTPException(status_code=400, detail="任务未完成或无结果文件")

    if not os.path.exists(task.result_path):
        raise HTTPException(status_code=404, detail="结果文件不存在")

    filename = os.path.basename(task.result_path)
    return FileResponse(
        path=task.result_path,
        filename=filename,
        media_type="application/zip",
    )
