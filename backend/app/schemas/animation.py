# backend/app/schemas/animation.py

from pydantic import BaseModel
from typing import Literal, Optional

class AnimationExportRequest(BaseModel):
    """动画导出请求"""
    resolution: Literal['720p', '1080p', '4k']
    fps: Literal[30, 60]
    show_hud: bool = True
    speed: float = 1.0

class AnimationExportTask(BaseModel):
    """动画导出任务"""
    task_id: str
    status: Literal['pending', 'processing', 'completed', 'failed']
    progress: float = 0.0
    download_url: Optional[str] = None
    error: Optional[str] = None

class AnimationExportProgress(BaseModel):
    """动画导出进度"""
    progress: float = 0.0
    status: Literal['pending', 'processing', 'completed', 'failed'] = 'pending'
