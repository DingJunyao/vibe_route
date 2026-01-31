"""
修复轨迹点 point_index 脚本
用于修复轨迹 ID 72 的 point_index 全部为 0 的问题
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from loguru import logger
from datetime import datetime, timezone

from app.models.track import TrackPoint
from app.core.config import settings


async def fix_point_index(track_id: int):
    """
    修复指定轨迹的 point_index

    按 created_at 时间顺序重新分配 point_index（从 0 开始）

    Args:
        track_id: 要修复的轨迹 ID
    """
    # 创建数据库引擎（DATABASE_URL 已经包含了正确的驱动）
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        # 1. 查询所有点，按 created_at 排序
        logger.info(f"正在查询轨迹 {track_id} 的所有点...")
        result = await session.execute(
            select(TrackPoint)
            .where(TrackPoint.track_id == track_id)
            .order_by(TrackPoint.created_at)
        )
        points = result.scalars().all()

        if not points:
            logger.warning(f"轨迹 {track_id} 没有找到任何点")
            return

        logger.info(f"找到 {len(points)} 个点")

        # 2. 批量更新 point_index
        logger.info("开始更新 point_index...")
        for index, point in enumerate(points):
            point.point_index = index
            point.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

            # 每 100 个点提交一次
            if (index + 1) % 100 == 0:
                await session.commit()
                logger.info(f"已更新 {index + 1}/{len(points)} 个点")

        # 提交剩余的更改
        await session.commit()

        logger.info(f"完成！已更新 {len(points)} 个点的 point_index")

        # 3. 验证结果
        logger.info("验证结果...")
        verify_result = await session.execute(
            select(TrackPoint.point_index)
            .where(TrackPoint.track_id == track_id)
            .order_by(TrackPoint.created_at)
            .limit(10)
        )
        sample_indices = [row[0] for row in verify_result.all()]
        logger.info(f"前 10 个点的 point_index: {sample_indices}")

        # 检查是否有重复
        count_result = await session.execute(
            select(func.count(TrackPoint.id)).where(TrackPoint.track_id == track_id)
        )
        total_count = count_result.scalar_one()

        unique_result = await session.execute(
            select(func.count(func.distinct(TrackPoint.point_index)))
            .where(TrackPoint.track_id == track_id)
        )
        unique_count = unique_result.scalar_one()

        logger.info(f"总点数: {total_count}, 唯一索引数: {unique_count}")

        if total_count == unique_count:
            logger.success("验证通过！所有 point_index 都是唯一的")
        else:
            logger.error(f"验证失败！存在重复的 point_index")

    await engine.dispose()


if __name__ == "__main__":
    # 修复轨迹 ID 72
    asyncio.run(fix_point_index(72))
