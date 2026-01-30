"""
系统配置相关模型
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import AuditMixin


def get_utc_now():
    """获取当前 UTC 时间（不带时区信息）"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Config(Base, AuditMixin):
    """系统配置表"""

    __tablename__ = "configs"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(50), unique=True, index=True, nullable=False)
    value = Column(Text, nullable=False)  # JSON 字符串

    def __repr__(self):
        return f"<Config(key='{self.key}')>"


class InviteCode(Base):
    """邀请码表"""

    __tablename__ = "invite_codes"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    max_uses = Column(Integer, default=1, nullable=False)
    used_count = Column(Integer, default=0, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)  # 创建者 ID（外键）
    expires_at = Column(DateTime, nullable=True)

    # 审计字段（手动添加，因为 created_by 已有特殊含义）
    created_at = Column(DateTime, default=get_utc_now, nullable=False, comment="创建时间")
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now, nullable=False, comment="修改时间")
    updated_by = Column(Integer, nullable=True, index=True, comment="修改者ID")
    is_valid = Column(Boolean, default=True, nullable=False, index=True, comment="是否有效（软删除标记）")

    # 关系
    created_by_user = relationship("User", back_populates="created_invite_codes")

    @property
    def is_usable(self) -> bool:
        """邀请码是否可用（考虑使用次数、过期时间）"""
        if self.used_count >= self.max_uses:
            return False
        if self.expires_at and self.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
            return False
        return True

    def __repr__(self):
        return f"<InviteCode(code='{self.code}', used={self.used_count}/{self.max_uses})>"
