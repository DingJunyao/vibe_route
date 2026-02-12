"""
覆盖层模板模型
"""
from sqlalchemy import Column, String, Integer, Text, Boolean, JSON
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import AuditMixin


class OverlayTemplate(Base, AuditMixin):
    """覆盖层模板表"""

    __tablename__ = "overlay_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="模板名称")
    description = Column(Text, nullable=True, comment="模板描述")
    config = Column(JSON, nullable=False, comment="模板配置（JSON）")
    user_id = Column(Integer, nullable=True, index=True, comment="所有者ID，NULL表示系统模板")
    is_public = Column(Boolean, default=False, nullable=False, comment="是否公开")
    is_system = Column(Boolean, default=False, nullable=False, index=True, comment="是否系统预设模板")

    def __repr__(self):
        return f"<OverlayTemplate(id={self.id}, name='{self.name}', is_system={self.is_system})>"


class Font(Base, AuditMixin):
    """字体表"""

    __tablename__ = "fonts"

    id = Column(String(50), primary_key=True, index=True, comment="字体ID")
    name = Column(String(100), nullable=False, comment="字体显示名称")
    filename = Column(String(255), nullable=False, comment="字体文件名")
    type = Column(String(10), nullable=False, comment="字体类型：system/admin/user")
    owner_id = Column(Integer, nullable=True, index=True, comment="所有者ID（user类型时）")
    file_path = Column(String(500), nullable=False, comment="字体文件路径")
    file_size = Column(Integer, nullable=False, comment="文件大小（字节）")

    # 字体元数据
    family = Column(String(100), nullable=True, comment="字体家族")
    style = Column(String(20), default="normal", comment="字体样式：normal/italic")
    weight = Column(Integer, default=400, comment="字体粗细：100-900")

    # 字符集支持
    supports_latin = Column(Boolean, default=True, nullable=False, comment="支持拉丁字符")
    supports_chinese = Column(Boolean, default=False, nullable=False, comment="支持中文字符")
    supports_japanese = Column(Boolean, default=False, nullable=False, comment="支持日文字符")
    supports_korean = Column(Boolean, default=False, nullable=False, comment="支持韩文字符")

    preview_url = Column(String(500), nullable=True, comment="预览图URL")

    def __repr__(self):
        return f"<Font(id='{self.id}', name='{self.name}', type='{self.type}')>"
