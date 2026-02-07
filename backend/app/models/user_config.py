"""
用户配置模型
用户可自定义地图 API Key 等配置
配置优先级：用户配置 > 系统配置
"""
from sqlalchemy import Column, Integer, String, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import AuditMixin


class UserConfig(Base, AuditMixin):
    """
    用户配置表

    每个用户可以有独立的地图配置，包括：
    - 默认地图提供商
    - 自定义 API Key
    - 地图层顺序和启用状态
    """
    __tablename__ = "user_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, comment="关联用户ID")
    map_provider = Column(String(50), nullable=True, comment="默认地图提供商")
    map_layers = Column(JSON, nullable=True, comment="地图层配置")

    # 关系
    user = relationship("User", back_populates="config")

    def __repr__(self):
        return f"<UserConfig(user_id={self.user_id}, map_provider={self.map_provider})>"
