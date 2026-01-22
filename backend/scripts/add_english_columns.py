"""
添加英文列到 track_points 表并更新现有数据

运行方式:
    python scripts/add_english_columns.py
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.core.database import engine, async_session_maker
from loguru import logger


async def add_english_columns():
    """添加英文列到 track_points 表"""
    async with engine.begin() as conn:
        try:
            # 检查现有列
            result = await conn.execute(
                text("PRAGMA table_info(track_points)")
            )
            existing_columns = [row[1] for row in result.fetchall()]
            logger.info(f"现有列: {existing_columns}")

            # 需要添加的列
            columns_to_add = {
                'province_en': 'VARCHAR(100)',
                'city_en': 'VARCHAR(100)',
                'district_en': 'VARCHAR(100)',
                'road_name_en': 'VARCHAR(200)'
            }

            for col_name, col_type in columns_to_add.items():
                if col_name not in existing_columns:
                    await conn.execute(
                        text(f"ALTER TABLE track_points ADD COLUMN {col_name} {col_type}")
                    )
                    logger.info(f"成功添加列: {col_name}")
                else:
                    logger.info(f"列已存在，跳过: {col_name}")

        except Exception as e:
            logger.error(f"添加英文列失败: {e}")
            raise


async def main():
    """主函数"""
    logger.info("开始添加英文列...")
    await add_english_columns()
    logger.info("完成!")


if __name__ == "__main__":
    asyncio.run(main())
