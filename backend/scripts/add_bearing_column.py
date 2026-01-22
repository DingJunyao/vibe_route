"""
添加 bearing 列到 track_points 表

运行方式:
    python scripts/add_bearing_column.py
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.core.database import engine, async_session_maker
from loguru import logger


async def add_bearing_column():
    """添加 bearing 列到 track_points 表"""
    async with engine.begin() as conn:
        try:
            # 检查列是否已存在
            result = await conn.execute(
                text("PRAGMA table_info(track_points)")
            )
            columns = [row[1] for row in result.fetchall()]

            if 'bearing' in columns:
                logger.info("bearing 列已存在，无需添加")
                return

            # 添加 bearing 列
            await conn.execute(
                text("ALTER TABLE track_points ADD COLUMN bearing FLOAT")
            )
            logger.info("成功添加 bearing 列到 track_points 表")

        except Exception as e:
            logger.error(f"添加 bearing 列失败: {e}")
            raise


async def update_existing_bearings():
    """为现有轨迹计算并更新方位角"""
    from app.services.track_service import track_service

    logger.info("开始为现有轨迹更新方位角...")

    # 使用数据库会话而不是 engine
    async with async_session_maker() as db:
        result = await track_service.update_bearings_for_all_tracks(db)
        logger.info(f"方位角更新完成: {result}")


async def main():
    """主函数"""
    logger.info("开始添加 bearing 列...")
    await add_bearing_column()

    # 询问是否更新现有数据
    response = input("是否为现有轨迹计算方位角? (y/n): ")
    if response.lower() == 'y':
        await update_existing_bearings()
    else:
        logger.info("跳过现有数据的方位角计算")

    logger.info("完成!")


if __name__ == "__main__":
    asyncio.run(main())
