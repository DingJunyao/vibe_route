"""
数据库模型基类
提供软删除和审计字段
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, DateTime, Boolean
from sqlalchemy.orm import declared_attr


def get_utc_now():
    """获取当前 UTC 时间"""
    return datetime.now(timezone.utc)


class AuditMixin:
    """
    审计字段混合类
    提供创建时间、修改时间、创建者、修改者、是否有效字段
    """

    @declared_attr
    def created_at(cls):
        return Column(DateTime, default=get_utc_now, nullable=False, comment="创建时间")

    @declared_attr
    def updated_at(cls):
        return Column(DateTime, default=get_utc_now, onupdate=get_utc_now, nullable=False, comment="修改时间")

    @declared_attr
    def created_by(cls):
        return Column(Integer, nullable=True, index=True, comment="创建者ID")

    @declared_attr
    def updated_by(cls):
        return Column(Integer, nullable=True, index=True, comment="修改者ID")

    @declared_attr
    def is_valid(cls):
        return Column(Boolean, default=True, nullable=False, index=True, comment="是否有效（软删除标记）")
