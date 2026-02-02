"""
修复地级市的 level 错误

将错误的 level='area' 修正为 level='city'，同时修正 city_code 和 parent_code。
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, text
from app.core.database import async_session_maker
from app.models.admin_division import AdminDivision
from loguru import logger


async def fix_city_level():
    """修复地级市的 level 字段"""
    async with async_session_maker() as db:
        # 查找所有应该被修正为 city 的记录
        # 条件：level='area' 且 code 以 '00' 结尾（地级市代码格式）
        # 且不是不设区地级市和省辖县级行政单位
        CITIES_WITHOUT_DISTRICTS = {"441900", "442000", "460400", "620200"}
        PROVINCE_ADMINISTERED_PREFIXES = ("4190", "4290", "4690", "6590")

        result = await db.execute(
            select(AdminDivision).where(
                AdminDivision.level == "area"
            ).where(
                AdminDivision.code.like("%00")
            )
        )
        areas = result.scalars().all()

        fixed_count = 0
        for div in areas:
            code = div.code
            # 跳过不设区地级市
            if code in CITIES_WITHOUT_DISTRICTS:
                continue

            # 跳过省辖县级行政单位
            if code.startswith(PROVINCE_ADMINISTERED_PREFIXES):
                continue

            # 正常地级市：6位代码且以 '00' 结尾，如 420100
            # 或者 4位代码且以 '00' 结尾（省级别无区县的市）
            if len(code) == 6 and code[2:] == "0000":
                # 这是省级代码，跳过
                continue

            if (len(code) == 6 and code[4:] == "00") or (len(code) == 4 and code[2:] == "00"):
                # 应该是地级市
                logger.info(f"修正: {code} {div.name} level={div.level} -> city")
                div.level = "city"
                div.city_code = code
                div.parent_code = code[:2] + "0000" if len(code) >= 2 else None
                fixed_count += 1

        await db.commit()
        logger.info(f"修复完成，共修正 {fixed_count} 条记录")


if __name__ == "__main__":
    asyncio.run(fix_city_level())
