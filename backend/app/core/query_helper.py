"""
查询辅助类
提供软删除相关的查询过滤
"""
from typing import Type, TypeVar
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

T = TypeVar('T', bound=DeclarativeBase)


class QueryHelper:
    """查询辅助类，提供软删除过滤功能"""

    @staticmethod
    def with_valid_filter(model: Type[T]):
        """
        返回带有 is_valid=True 过滤的查询

        使用示例:
            stmt = QueryHelper.with_valid_filter(User).where(User.username == "test")
        """
        return select(model).where(model.is_valid == True)

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        model: Type[T],
        item_id: int,
        include_invalid: bool = False,
    ) -> T | None:
        """
        根据 ID 获取单条记录，自动过滤软删除的数据

        Args:
            db: 数据库会话
            model: 模型类
            item_id: 记录 ID
            include_invalid: 是否包含已软删除的数据
        """
        stmt = select(model).where(model.id == item_id)
        if not include_invalid and hasattr(model, 'is_valid'):
            stmt = stmt.where(model.is_valid == True)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_all(
        db: AsyncSession,
        model: Type[T],
        skip: int = 0,
        limit: int = 100,
        include_invalid: bool = False,
    ) -> list[T]:
        """
        获取列表，自动过滤软删除的数据

        Args:
            db: 数据库会话
            model: 模型类
            skip: 跳过记录数
            limit: 返回记录数限制
            include_invalid: 是否包含已软删除的数据
        """
        stmt = select(model).offset(skip).limit(limit)
        if not include_invalid and hasattr(model, 'is_valid'):
            stmt = stmt.where(model.is_valid == True)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def count(
        db: AsyncSession,
        model: Type[T],
        include_invalid: bool = False,
    ) -> int:
        """
        统计记录数，自动过滤软删除的数据

        Args:
            db: 数据库会话
            model: 模型类
            include_invalid: 是否包含已软删除的数据
        """
        from sqlalchemy import func
        stmt = select(func.count(model.id))
        if not include_invalid and hasattr(model, 'is_valid'):
            stmt = stmt.where(model.is_valid == True)
        result = await db.execute(stmt)
        return result.scalar() or 0


class SoftDeleteMixin:
    """软删除混合类，提供软删除操作"""

    @staticmethod
    async def soft_delete(
        db: AsyncSession,
        model: Type[T],
        item_id: int,
        user_id: int,
    ) -> bool:
        """
        软删除记录

        Args:
            db: 数据库会话
            model: 模型类
            item_id: 记录 ID
            user_id: 执行删除的用户 ID

        Returns:
            是否成功删除
        """
        from datetime import datetime

        item = await QueryHelper.get_by_id(db, model, item_id)
        if not item:
            return False

        if hasattr(item, 'is_valid'):
            item.is_valid = False
        if hasattr(item, 'updated_at'):
            item.updated_at = datetime.utcnow()
        if hasattr(item, 'updated_by'):
            item.updated_by = user_id

        await db.commit()
        return True

    @staticmethod
    async def soft_delete_bulk(
        db: AsyncSession,
        items: list[T],
        user_id: int,
    ) -> int:
        """
        批量软删除记录

        Args:
            db: 数据库会话
            items: 要删除的记录列表
            user_id: 执行删除的用户 ID

        Returns:
            删除的记录数
        """
        from datetime import datetime

        now = datetime.utcnow()
        count = 0

        for item in items:
            if hasattr(item, 'is_valid'):
                item.is_valid = False
            if hasattr(item, 'updated_at'):
                item.updated_at = now
            if hasattr(item, 'updated_by'):
                item.updated_by = user_id
            count += 1

        await db.commit()
        return count


class AuditMixin:
    """审计字段混合类，提供创建和更新时的审计字段自动填充"""

    @staticmethod
    def set_created_audit(item: T, user_id: int):
        """
        设置创建审计字段

        Args:
            item: 模型实例
            user_id: 创建用户 ID
        """
        if hasattr(item, 'created_by'):
            item.created_by = user_id

    @staticmethod
    def set_updated_audit(item: T, user_id: int):
        """
        设置更新审计字段

        Args:
            item: 模型实例
            user_id: 更新用户 ID
        """
        from datetime import datetime

        if hasattr(item, 'updated_by'):
            item.updated_by = user_id
        if hasattr(item, 'updated_at'):
            item.updated_at = datetime.utcnow()
