"""
行政区划数据导入 CLI 命令

用法：
    python -m app.cli.import_admin_divisions
    python -m app.cli.import_admin_divisions --force
    python -m app.cli.import_admin_divisions --skip-geojson
"""
import argparse
import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import select, func
from loguru import logger

from app.core.database import async_session_maker
from app.models.admin_division import AdminDivision
from app.services.admin_division_import_service import AdminDivisionImportService
from app.core.config import settings


async def import_divisions(
    force: bool = False,
    skip_geojson: bool = False,
    skip_postgis: bool = False
):
    """
    导入行政区划数据

    Args:
        force: 是否强制重新导入（删除已有数据）
        skip_geojson: 是否跳过 GeoJSON 边界框导入
        skip_postgis: 是否跳过 PostGIS 几何导入
    """
    service = AdminDivisionImportService()
    stats = {}

    # 使用独立的数据库会话
    db = async_session_maker()

    try:
        # 检查现有数据
        result = await db.execute(
            select(func.count(AdminDivision.id))
        )
        existing_count = result.scalar() or 0

        if existing_count > 0 and not force:
            logger.info(f"数据库中已有 {existing_count} 条行政区划数据")
            logger.info("使用 --force 参数强制重新导入")
            return

        # 进度回调
        def progress_callback(level, current, total):
            pct = current * 100 // total if total > 0 else 0
            logger.info(f"导入 {level}: {current}/{total} ({pct}%)")
            sys.stdout.flush()

        # 1. 从 SQLite 导入行政区划数据
        logger.info("开始从 area_code.sqlite 导入行政区划数据...")
        sys.stdout.flush()

        stats = await service.import_from_sqlite(
            db,
            progress_callback=progress_callback,
            force=force
        )
        logger.info(f"行政区划数据导入完成: {stats}")
        sys.stdout.flush()

        # 2. 从 GeoJSON 导入边界框
        if not skip_geojson:
            logger.info("开始从 GeoJSON 导入边界框数据...")
            sys.stdout.flush()
            bounds_count = await service.import_geojson_bounds(
                db,
                progress_callback=progress_callback
            )
            logger.info(f"边界框数据导入完成: {bounds_count} 个区域")
            sys.stdout.flush()

        # 3. PostGIS 几何导入（仅 PostgreSQL）
        database_type = getattr(settings, 'DATABASE_TYPE', 'sqlite')
        if database_type == "postgresql" and not skip_postgis:
            logger.info("检测到 PostgreSQL，开始导入 PostGIS 几何数据...")
            sys.stdout.flush()
            postgis_count = await service.import_postgis_geometries(
                db,
                progress_callback=progress_callback
            )
            logger.info(f"PostGIS 几何数据导入完成: {postgis_count} 个")
            sys.stdout.flush()

        # 显示最终统计
        logger.info("\n=== 导入完成 ===")
        for level, count in stats.items():
            logger.info(f"  {level}: {count}")

    finally:
        # 确保数据库会话关闭
        await db.close()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="导入行政区划数据")
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重新导入（删除已有数据）"
    )
    parser.add_argument(
        "--skip-geojson",
        action="store_true",
        help="跳过 GeoJSON 边界框导入"
    )
    parser.add_argument(
        "--skip-postgis",
        action="store_true",
        help="跳过 PostGIS 几何导入"
    )

    args = parser.parse_args()

    # 运行导入
    try:
        asyncio.run(import_divisions(
            force=args.force,
            skip_geojson=args.skip_geojson,
            skip_postgis=args.skip_postgis
        ))
    except KeyboardInterrupt:
        logger.info("\n导入已取消")
        os._exit(130)
    except SystemExit as e:
        # SystemExit 是我们主动调用 sys.exit() 时产生的，直接退出
        os._exit(int(e.code) if e.code is not None else 1)
    except Exception as e:
        logger.error(f"导入失败: {e}")
        import traceback
        traceback.print_exc()
        os._exit(1)

    # 成功完成，使用 os._exit 强制退出（绕过 SQLAlchemy 的清理）
    logger.info("程序即将退出...")
    os._exit(0)


if __name__ == "__main__":
    main()
