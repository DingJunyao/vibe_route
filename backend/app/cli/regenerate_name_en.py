"""
重新生成行政区划英文名称

修复由于 pinyin_generator.py bug 导致的错误英文名称。
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import select
from app.core.database import async_session_maker
from app.models.admin_division import AdminDivision
from app.utils.pinyin_generator import name_to_pinyin


async def regenerate_name_en():
    """重新生成所有行政区划的英文名称"""
    print("开始重新生成行政区划英文名称...")

    async with async_session_maker() as db:
        # 查询所有行政区划
        result = await db.execute(select(AdminDivision))
        divisions = list(result.scalars().all())

        total = len(divisions)
        updated = 0
        errors = []

        for i, div in enumerate(divisions, 1):
            try:
                # 生成新的英文名称
                new_name_en = name_to_pinyin(div.name, div.level)

                # 检查是否需要更新
                if div.name_en != new_name_en:
                    old_name_en = div.name_en
                    div.name_en = new_name_en
                    updated += 1

                    if i <= 10 or updated <= 20:
                        # 打印前几个和前20个更新
                        print(f"[{i}/{total}] {div.name}({div.level}): {old_name_en} -> {new_name_en}")
                    elif updated == 21:
                        print("... (后续更新省略)")
            except Exception as e:
                errors.append((div.code, div.name, str(e)))
                print(f"[{i}/{total}] ERROR: {div.name}({div.code}): {e}")

        # 提交更改
        await db.commit()

        print(f"\n完成！")
        print(f"总计: {total} 条记录")
        print(f"更新: {updated} 条记录")
        if errors:
            print(f"错误: {len(errors)} 条")
            for code, name, error in errors[:10]:
                print(f"  - {name}({code}): {error}")


if __name__ == "__main__":
    asyncio.run(regenerate_name_en())
