"""
用户相关的 Pydantic schemas
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_serializer


class UserBase(BaseModel):
    """用户基础 schema"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr


class UserCreate(UserBase):
    """用户创建 schema"""
    password: str = Field(..., min_length=6, max_length=100)
    invite_code: Optional[str] = None


class UserLogin(BaseModel):
    """用户登录 schema"""
    username: str
    password: str


class UserUpdate(BaseModel):
    """用户更新 schema（管理员用）"""
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None


class ResetPassword(BaseModel):
    """重置密码 schema（管理员用）"""
    new_password: str = Field(..., min_length=6, max_length=100)


class UserResponse(UserBase):
    """用户响应 schema"""
    id: int
    is_admin: bool
    is_active: bool
    created_at: datetime

    @field_serializer('created_at')
    def serialize_datetime(self, dt: datetime) -> str:
        """序列化 datetime 为带时区的 ISO 格式字符串（UTC）"""
        return dt.isoformat() + '+00:00'

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """令牌响应 schema"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
