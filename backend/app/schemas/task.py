"""
任务相关的 Pydantic schemas
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class TaskCreate(BaseModel):
    """任务创建 schema"""
    type: str  # overlay_generate 等
    track_id: int


class TaskResponse(BaseModel):
    """任务响应 schema"""
    id: int
    user_id: int
    type: str
    status: str
    progress: int
    result_path: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    is_finished: bool

    class Config:
        from_attributes = True
