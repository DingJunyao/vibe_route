"""
行政区划数据导入服务

从 area_code.sqlite 和 area_geojson/*.json 导入数据。
"""
import sqlite3
import json
import asyncio
from pathlib import Path
from typing import Optional, Callable
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from loguru import logger

from app.models.admin_division import AdminDivision
from app.utils.pinyin_generator import load_special_mapping, get_name_en
from app.core.config import settings


class AdminDivisionImportService:
    """行政区划数据导入服务"""

    def __init__(self, data_path: str = None):
        self.data_path = Path(data_path or "data/area_data")
        self.sqlite_path = self.data_path / "area_code.sqlite"
        # 新的数据路径：map 目录
        self.map_path = self.data_path / "map"
        self.province_geojson_path = self.map_path / "province"
        self.city_geojson_path = self.map_path / "city"
        self.china_geojson_path = self.map_path / "china.json"
        # 旧路径保留用于向后兼容
        self.geojson_path = self.data_path / "area_geojson"
        self.special_mapping = None

    async def import_from_sqlite(
        self,
        db: AsyncSession,
        batch_size: int = 1000,
        progress_callback: Optional[Callable] = None,
        force: bool = False
    ) -> dict:
        """
        从 area_code.sqlite 导入行政区划数据

        Args:
            db: 数据库会话
            batch_size: 批量插入大小
            progress_callback: 进度回调函数 callback(level, current, total)
            force: 是否强制重新导入（删除已有数据）

        Returns:
            dict: 导入统计 {"provinces": n, "cities": n, "areas": n}
        """
        stats = {"provinces": 0, "cities": 0, "areas": 0}

        # 加载特殊地名映射
        self.special_mapping = load_special_mapping()

        # 连接 SQLite
        if not self.sqlite_path.exists():
            logger.error(f"SQLite 文件不存在: {self.sqlite_path}")
            return stats

        conn = sqlite3.connect(str(self.sqlite_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # 如果强制重新导入，先删除已有数据
            if force:
                await db.execute(text("DELETE FROM admin_divisions"))
                logger.info("已清空 admin_divisions 表")

            # 按层级导入：province -> city -> area
            await self._import_level(
                db, cursor, "province", stats, batch_size,
                progress_callback, force
            )
            await self._import_level(
                db, cursor, "city", stats, batch_size,
                progress_callback, force
            )
            await self._import_level(
                db, cursor, "area", stats, batch_size,
                progress_callback, force
            )

            await db.commit()
            logger.info(f"行政区划导入完成: {stats}")

        finally:
            conn.close()

        return stats

    async def _import_level(
        self,
        db: AsyncSession,
        cursor: sqlite3.Cursor,
        level: str,
        stats: dict,
        batch_size: int,
        progress_callback: Optional[Callable],
        force: bool
    ):
        """导入单个层级的行政区划"""
        table_map = {
            "province": ("province", None),
            "city": ("city", "provinceCode"),
            "area": ("area", "cityCode"),
        }

        table_name, parent_col = table_map.get(level, (level, None))

        # 查询所有记录
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()

        batch = []
        total = len(rows)
        processed = 0

        for row in rows:
            code = row["code"]
            name = row["name"]
            parent_code = row[parent_col] if parent_col and parent_col in row.keys() else None

            # 确定省代码和市代码
            if level == "province":
                province_code = code
                city_code = None
            elif level == "city":
                province_code = row["provinceCode"] if "provinceCode" in row.keys() else None
                city_code = code
            elif level == "area":
                province_code = row["provinceCode"] if "provinceCode" in row.keys() else None
                city_code = row["cityCode"] if "cityCode" in row.keys() else None
            else:
                province_code = None
                city_code = None

            # 生成英文名称
            name_en = get_name_en(name, code, level, self.special_mapping)

            division = AdminDivision(
                code=code,
                name=name,
                name_en=name_en,
                level=level,
                parent_code=parent_code,
                province_code=province_code,
                city_code=city_code,
            )
            batch.append(division)

            # 批量插入
            if len(batch) >= batch_size:
                await self._insert_batch(db, batch, force)
                batch.clear()

            processed += 1
            if progress_callback and processed % 100 == 0:
                progress_callback(level, processed, total)

        # 插入剩余记录
        if batch:
            await self._insert_batch(db, batch, force)

        stats[f"{level}s"] = total

    async def _insert_batch(
        self,
        db: AsyncSession,
        divisions: list[AdminDivision],
        force: bool
    ):
        """批量插入行政区划数据"""
        database_type = getattr(settings, 'DATABASE_TYPE', 'sqlite')

        if database_type == "postgresql":
            # 使用 PostgreSQL 的 ON CONFLICT 进行 upsert
            data = [
                {
                    "code": d.code,
                    "name": d.name,
                    "name_en": d.name_en,
                    "level": d.level,
                    "parent_code": d.parent_code,
                    "province_code": d.province_code,
                    "city_code": d.city_code,
                }
                for d in divisions
            ]
            stmt = pg_insert(AdminDivision).values(data)
            if not force:
                stmt = stmt.on_conflict_do_nothing()
            await db.execute(stmt)
        else:
            # SQLite 和 MySQL 使用普通插入
            for division in divisions:
                # 检查是否已存在
                if not force:
                    existing = await db.execute(
                        select(AdminDivision.id).where(AdminDivision.code == division.code)
                    )
                    if existing.scalar_one_or_none():
                        continue
                db.add(division)

        await db.commit()

    async def import_geojson_bounds(
        self,
        db: AsyncSession,
        progress_callback: Optional[Callable] = None
    ) -> int:
        """
        从 GeoJSON 文件导入边界框数据

        支持新的数据结构（map 目录）：
        - province/ 目录：省级文件（110000.json）包含直辖市的区县
        - city/ 目录：市级文件（130100.json）包含普通地市的区县
        - china.json：包含省级边界

        Args:
            db: 数据库会话
            progress_callback: 进度回调函数 callback(current, total)

        Returns:
            int: 更新的数量
        """
        total_files = 0
        count = 0

        # 优先使用新数据结构 (map 目录)
        if self.map_path.exists():
            logger.info("使用新的 map 目录数据结构")

            # 1. 从 province/ 目录导入（直辖市的区县）
            if self.province_geojson_path.exists():
                geojson_files = list(self.province_geojson_path.glob("*.json"))
                total_files += len(geojson_files)
                for i, geojson_file in enumerate(geojson_files):
                    try:
                        with open(geojson_file, "r", encoding="utf-8") as f:
                            data = json.load(f)

                        for feature in data.get("features", []):
                            code = feature.get("properties", {}).get("id")
                            if code:
                                c = await self._update_bounds_from_feature(db, feature, code)
                                count += c

                        if (i + 1) % 10 == 0:
                            await db.commit()

                        if progress_callback and i % 10 == 0:
                            progress_callback("province_geojson", i, len(geojson_files))

                    except Exception as e:
                        logger.error(f"处理 province 文件 {geojson_file} 失败: {e}")

            # 2. 从 city/ 目录导入（普通地市的区县）
            if self.city_geojson_path.exists():
                geojson_files = list(self.city_geojson_path.glob("*.json"))
                total_files += len(geojson_files)
                for i, geojson_file in enumerate(geojson_files):
                    try:
                        with open(geojson_file, "r", encoding="utf-8") as f:
                            data = json.load(f)

                        for feature in data.get("features", []):
                            code = feature.get("properties", {}).get("id")
                            if code:
                                c = await self._update_bounds_from_feature(db, feature, code)
                                count += c

                        if (i + 1) % 10 == 0:
                            await db.commit()

                        if progress_callback and i % 10 == 0:
                            progress_callback("city_geojson", i, len(geojson_files))

                    except Exception as e:
                        logger.error(f"处理 city 文件 {geojson_file} 失败: {e}")

            # 3. 从 china.json 导入省级边界
            if self.china_geojson_path.exists():
                try:
                    with open(self.china_geojson_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    for feature in data.get("features", []):
                        code = feature.get("properties", {}).get("id")
                        if code:
                            c = await self._update_bounds_from_feature(db, feature, code)
                            count += c

                    await db.commit()

                except Exception as e:
                    logger.error(f"处理 china.json 失败: {e}")

            await db.commit()
            logger.info(f"GeoJSON 边界框导入完成: {count} 个区域")
            return count

        # 回退到旧数据结构 (area_geojson 目录)
        if not self.geojson_path.exists():
            logger.warning(f"GeoJSON 目录不存在: {self.geojson_path}")
            return 0

        geojson_files = list(self.geojson_path.glob("*.json"))
        total = len(geojson_files)

        for i, geojson_file in enumerate(geojson_files):
            try:
                with open(geojson_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # 提取边界框
                for feature in data.get("features", []):
                    code = feature.get("properties", {}).get("id")
                    if not code:
                        continue

                    coords = self._extract_coordinates(feature.get("geometry", {}))
                    if coords:
                        min_lat = int(min(c[0] for c in coords) * 1e6)
                        max_lat = int(max(c[0] for c in coords) * 1e6)
                        min_lon = int(min(c[1] for c in coords) * 1e6)
                        max_lon = int(max(c[1] for c in coords) * 1e6)

                        # 更新边界框
                        result = await db.execute(
                            select(AdminDivision).where(AdminDivision.code == code)
                        )
                        division = result.scalar_one_or_none()
                        if division:
                            division.min_lat = min_lat
                            division.max_lat = max_lat
                            division.min_lon = min_lon
                            division.max_lon = max_lon
                            count += 1

                # 每处理 10 个文件提交一次
                if (i + 1) % 10 == 0:
                    await db.commit()

                if progress_callback and i % 10 == 0:
                    progress_callback("geojson", i, total)

            except Exception as e:
                logger.error(f"处理 GeoJSON 文件 {geojson_file} 失败: {e}")

        await db.commit()
        logger.info(f"GeoJSON 边界框导入完成: {count} 个区域")
        return count

    async def _update_bounds_from_feature(
        self,
        db: AsyncSession,
        feature: dict,
        code: str
    ) -> int:
        """
        从 GeoJSON feature 更新边界框

        Args:
            db: 数据库会话
            feature: GeoJSON feature
            code: 行政区划代码

        Returns:
            int: 更新的数量（0 或 1）
        """
        coords = self._extract_coordinates(feature.get("geometry", {}))
        if not coords:
            return 0

        min_lat = int(min(c[0] for c in coords) * 1e6)
        max_lat = int(max(c[0] for c in coords) * 1e6)
        min_lon = int(min(c[1] for c in coords) * 1e6)
        max_lon = int(max(c[1] for c in coords) * 1e6)

        # 更新边界框
        result = await db.execute(
            select(AdminDivision).where(AdminDivision.code == code)
        )
        division = result.scalar_one_or_none()
        if division:
            division.min_lat = min_lat
            division.max_lat = max_lat
            division.min_lon = min_lon
            division.max_lon = max_lon
            return 1
        return 0

    def _extract_coordinates(self, geometry: dict) -> list[tuple[float, float]]:
        """从几何对象中提取所有坐标"""
        geom_type = geometry.get("type")
        coords = geometry.get("coordinates", [])

        if geom_type == "Polygon":
            # coords 是 [[[lon, lat], ...]]
            return [(lat, lon) for ring in coords for lon, lat in ring]
        elif geom_type == "MultiPolygon":
            # coords 是 [[[[lon, lat], ...]], ...]
            result = []
            for polygon in coords:
                for ring in polygon:
                    result.extend([(lat, lon) for lon, lat in ring])
            return result
        return []

    async def import_postgis_geometries(
        self,
        db: AsyncSession,
        progress_callback: Optional[Callable] = None
    ) -> int:
        """
        将 GeoJSON 几何数据导入 PostGIS

        仅在 PostgreSQL + PostGIS 环境下使用。

        支持新的数据结构（map 目录）：
        - province/ 目录：省级文件包含直辖市的区县
        - city/ 目录：市级文件包含普通地市的区县
        - china.json：包含省级几何

        Args:
            db: 数据库会话
            progress_callback: 进度回调函数 callback(current, total)

        Returns:
            int: 导入的几何数量
        """
        # 首先检查 PostGIS 表是否存在
        try:
            result = await db.execute(
                text("SELECT 1 FROM admin_divisions_spatial LIMIT 1")
            )
        except Exception:
            logger.warning("PostGIS 空间表不存在，跳过 PostGIS 几何导入")
            return 0

        count = 0
        errors = 0
        geojson_files = []

        # 收集所有 GeoJSON 文件
        if self.map_path.exists():
            if self.province_geojson_path.exists():
                geojson_files.extend(self.province_geojson_path.glob("*.json"))
            if self.city_geojson_path.exists():
                geojson_files.extend(self.city_geojson_path.glob("*.json"))
            if self.china_geojson_path.exists():
                geojson_files.append(self.china_geojson_path)
        elif self.geojson_path.exists():
            geojson_files = list(self.geojson_path.glob("*.json"))
        else:
            logger.warning("找不到 GeoJSON 数据目录")
            return 0

        total = len(geojson_files)

        for i, geojson_file in enumerate(geojson_files):
            try:
                with open(geojson_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                for feature in data.get("features", []):
                    code = feature.get("properties", {}).get("id")
                    geometry = feature.get("geometry")

                    if code and geometry:
                        # 获取 division_id
                        result = await db.execute(
                            text("SELECT id FROM admin_divisions WHERE code = :code"),
                            {"code": code}
                        )
                        row = result.fetchone()
                        if row:
                            division_id = row[0]

                            # 将 GeoJSON 转换为 PostGIS 几何
                            geojson_str = json.dumps(geometry)
                            await db.execute(text("""
                                INSERT INTO admin_divisions_spatial (division_id, geom)
                                VALUES (:division_id, ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326))
                                ON CONFLICT (division_id) DO UPDATE
                                SET geom = EXCLUDED.geom
                            """), {"division_id": division_id, "geojson": geojson_str})
                            count += 1

                # 每处理 10 个文件提交一次
                if (i + 1) % 10 == 0:
                    await db.commit()

                if progress_callback and i % 10 == 0:
                    progress_callback("geojson", i, total)

            except Exception as e:
                logger.error(f"处理 GeoJSON 文件 {geojson_file} 失败: {e}")
                errors += 1
                # 如果连续错误过多，可能是 PostGIS 不可用，停止导入
                if errors >= 10:
                    logger.warning("连续错误过多，停止 PostGIS 几何导入")
                    break
                # 回滚当前事务
                try:
                    await db.rollback()
                except:
                    pass

        await db.commit()
        logger.info(f"PostGIS 几何导入完成: {count} 个")
        return count
