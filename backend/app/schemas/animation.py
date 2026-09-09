# backend/app/schemas/animation.py

from pydantic import BaseModel
from typing import Literal, Optional

class AnimationExportRequest(BaseModel):
    """动画导出请求"""
    resolution: Literal['720p', '1080p', '4k']
    show_hud: bool = True
    speed: float = 1.0
    # 视图状态（导出画面与用户点击导出时一致）
    start_time: float = 0.0  # 起点（播放位置，毫秒）
    camera_mode: Literal['full', 'fixed-center'] = 'full'
    orientation_mode: Literal['north-up', 'track-up'] = 'north-up'
    marker_style: Literal['arrow', 'car', 'person'] = 'arrow'
    show_info_panel: bool = True
    layer_id: Optional[str] = None  # 地图图层（含卫星图等变体）
    zoom: Optional[float] = None  # fixed-center 模式下用户手动缩放
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None
    viewport_width: Optional[float] = None  # 详情页地图画幅宽度（像素），用于 zoom 修正
    viewport_height: Optional[float] = None  # 详情页地图画幅高度（像素）

class AnimationExportTask(BaseModel):
    """动画导出任务"""
    task_id: str
    status: Literal['pending', 'processing', 'completed', 'failed', 'cancelled']
    progress: float = 0.0
    download_url: Optional[str] = None
    error: Optional[str] = None

class AnimationExportProgress(BaseModel):
    """动画导出进度"""
    progress: float = 0.0
    status: Literal['pending', 'processing', 'completed', 'failed', 'cancelled'] = 'pending'
