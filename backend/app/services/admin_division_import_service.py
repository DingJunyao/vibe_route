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
        [DEPRECATED] 从 area_code.sqlite 导入行政区划数据

        .. deprecated::
            请使用 import_from_datav_online() 从阿里 DataV API 获取数据，
            或使用 import_from_geojson_archive() 从压缩包导入。

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

    # ========== 新增：DataV GeoJSON 导入方法 ==========

    # 不设区的地级市（硬编码）
    CITIES_WITHOUT_DISTRICTS = {
        "441900",  # 东莞市
        "442000",  # 中山市
        "460400",  # 儋州市
        "620200",  # 嘉峪关市
    }

    # 直辖市代码
    MUNICIPALITIES = {"110000", "120000", "310000", "500000"}

    async def import_from_datav_online(
        self,
        db: AsyncSession,
        province_codes: list[str] = None,
        progress_callback: Optional[Callable] = None,
        force: bool = False
    ) -> dict:
        """
        从阿里 DataV 在线拉取并导入行政区划数据

        Args:
            db: 数据库会话
            province_codes: 省级代码列表，None 表示全国
            progress_callback: 进度回调函数 callback(message, current, total)
            force: 是否强制重新导入（删除已有数据）

        Returns:
            dict: 导入统计 {"provinces": n, "cities": n, "areas": n, "updated": n}
        """
        from app.services.datav_geo_service import datav_geo_service

        stats = {"provinces": 0, "cities": 0, "areas": 0, "updated": 0}

        # 加载特殊地名映射
        self.special_mapping = load_special_mapping()

        try:
            # 如果强制重新导入，先删除已有数据
            if force:
                if province_codes:
                    # 只删除指定省份的数据
                    for prov_code in province_codes:
                        await db.execute(
                            text("DELETE FROM admin_divisions WHERE province_code = :code OR code = :code"),
                            {"code": prov_code}
                        )
                else:
                    await db.execute(text("DELETE FROM admin_divisions"))
                await db.commit()
                logger.info("已清空指定行政区划数据")

            # 获取数据
            if province_codes:
                features = await datav_geo_service.fetch_provinces_selective(
                    province_codes, progress_callback
                )
            else:
                features = await datav_geo_service.fetch_all_recursive(
                    progress_callback=progress_callback
                )

            # 导入数据
            if progress_callback:
                progress_callback("正在导入数据库...", 0, len(features))

            for i, feature in enumerate(features):
                try:
                    # DataV 在线数据使用 GCJ02 坐标系，需要转换为 WGS84
                    updated = await self._import_datav_feature(db, feature, force, convert_coords=True)
                    if updated:
                        stats["updated"] += 1

                    # 统计层级
                    props = feature.get("properties", {})
                    level = props.get("level", "")
                    if level == "province":
                        stats["provinces"] += 1
                    elif level == "city":
                        stats["cities"] += 1
                    elif level == "district":
                        stats["areas"] += 1

                    # 每 100 条提交一次
                    if (i + 1) % 100 == 0:
                        await db.commit()
                        if progress_callback:
                            progress_callback("正在导入数据库...", i + 1, len(features))

                except Exception as e:
                    logger.warning(f"导入 feature 失败: {e}")

            await db.commit()
            logger.info(f"DataV 在线导入完成: {stats}")
            return stats

        except Exception as e:
            logger.error(f"DataV 在线导入失败: {e}")
            await db.rollback()
            raise

    async def import_from_geojson_archive(
        self,
        db: AsyncSession,
        archive_path: Path,
        progress_callback: Optional[Callable] = None,
        force: bool = False
    ) -> dict:
        """
        从上传的 GeoJSON 压缩包导入行政区划数据

        支持 ZIP 和 RAR 格式，压缩包内应包含 DataV 格式的 GeoJSON 文件。

        Args:
            db: 数据库会话
            archive_path: 压缩包路径
            progress_callback: 进度回调函数
            force: 是否强制重新导入

        Returns:
            dict: 导入统计
        """
        import tempfile
        import shutil
        from app.utils.archive_helper import ArchiveExtractor

        stats = {"provinces": 0, "cities": 0, "areas": 0, "updated": 0, "files": 0}

        # 加载特殊地名映射
        self.special_mapping = load_special_mapping()

        # 创建临时目录
        temp_dir = Path(tempfile.mkdtemp())

        try:
            # 解压文件
            if progress_callback:
                progress_callback("正在解压文件...", 0, 100)

            extracted_files = ArchiveExtractor.extract(archive_path, temp_dir)
            geojson_files = ArchiveExtractor.list_geojson_files(temp_dir)

            if not geojson_files:
                raise ValueError("压缩包中未找到 GeoJSON 文件")

            stats["files"] = len(geojson_files)

            # 如果强制重新导入，先删除已有数据
            if force:
                await db.execute(text("DELETE FROM admin_divisions"))
                await db.commit()
                logger.info("已清空 admin_divisions 表")

            # 处理每个 GeoJSON 文件
            total_files = len(geojson_files)
            for i, geojson_file in enumerate(geojson_files):
                try:
                    with open(geojson_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    # 检测格式
                    format_type = self._detect_geojson_format(data)

                    for feature in data.get("features", []):
                        if format_type == "datav":
                            # 压缩包中的 DataV 格式：需要判断数据来源
                            # 如果压缩包是从 DataV 下载的，可能是 GCJ02 坐标系
                            # 如果压缩包是用户自己准备的 WGS84 数据，不需要转换
                            # 目前默认假设压缩包是 WGS84（用户需确认数据源）
                            updated = await self._import_datav_feature(db, feature, force, convert_coords=False)
                        else:
                            # 旧格式转换后导入
                            updated = await self._import_legacy_feature(db, feature, force)

                        if updated:
                            stats["updated"] += 1

                        # 统计层级
                        props = feature.get("properties", {})
                        level = props.get("level", "")
                        if level == "province":
                            stats["provinces"] += 1
                        elif level in ("city", "3"):
                            stats["cities"] += 1
                        elif level in ("district", "4"):
                            stats["areas"] += 1

                    # 每处理一个文件提交一次
                    await db.commit()

                    if progress_callback:
                        progress_callback(f"处理文件 {geojson_file.name}...", i + 1, total_files)

                except Exception as e:
                    logger.warning(f"处理文件 {geojson_file} 失败: {e}")

            await db.commit()
            logger.info(f"GeoJSON 压缩包导入完成: {stats}")
            return stats

        finally:
            # 清理临时目录
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def import_bounds_only(
        self,
        db: AsyncSession,
        features: list[dict],
        progress_callback: Optional[Callable] = None,
        convert_coords: bool = True
    ) -> int:
        """
        仅更新边界数据（不创建新记录）

        Args:
            db: 数据库会话
            features: GeoJSON features 列表
            progress_callback: 进度回调函数
            convert_coords: 是否将坐标从 GCJ02 转换为 WGS84（DataV 在线数据需要转换）

        Returns:
            int: 更新的记录数
        """
        from app.services.datav_geo_service import DataVGeoService

        updated = 0
        total = len(features)

        for i, feature in enumerate(features):
            try:
                props = feature.get("properties", {})
                adcode = str(props.get("adcode", ""))

                if not adcode:
                    continue

                # 提取边界和中心点（根据数据来源决定是否转换坐标）
                bounds = DataVGeoService.extract_bounds(feature, convert_to_wgs84=convert_coords)
                center = DataVGeoService.extract_center(feature, convert_to_wgs84=convert_coords)

                # 更新已有记录
                result = await db.execute(
                    select(AdminDivision).where(AdminDivision.code == adcode)
                )
                division = result.scalar_one_or_none()

                if division:
                    if bounds[0] is not None:
                        division.min_lon = bounds[0]
                        division.min_lat = bounds[1]
                        division.max_lon = bounds[2]
                        division.max_lat = bounds[3]
                    if center[0] is not None:
                        division.center_lon = center[0]
                        division.center_lat = center[1]
                    updated += 1

                # 每 100 条提交一次
                if (i + 1) % 100 == 0:
                    await db.commit()
                    if progress_callback:
                        progress_callback("更新边界数据...", i + 1, total)

            except Exception as e:
                logger.warning(f"更新边界失败 [{adcode}]: {e}")

        await db.commit()
        logger.info(f"边界数据更新完成: {updated} 条")
        return updated

    async def _import_datav_feature(
        self,
        db: AsyncSession,
        feature: dict,
        force: bool,
        convert_coords: bool = True
    ) -> bool:
        """
        导入单个 DataV 格式的 GeoJSON feature

        Args:
            db: 数据库会话
            feature: GeoJSON feature
            force: 是否强制覆盖
            convert_coords: 是否将坐标从 GCJ02 转换为 WGS84（DataV 在线数据需要转换）

        Returns:
            bool: 是否成功导入/更新
        """
        from app.services.datav_geo_service import DataVGeoService

        props = feature.get("properties", {})
        adcode = str(props.get("adcode", "")).zfill(6)
        name = props.get("name", "")
        children_num = props.get("childrenNum", 0)

        if not adcode or not name:
            return False

        # 分类行政区划
        province_code, city_code, level = DataVGeoService.classify_division(feature)

        # 提取边界和中心点（根据数据来源决定是否转换坐标）
        bounds = DataVGeoService.extract_bounds(feature, convert_to_wgs84=convert_coords)
        center = DataVGeoService.extract_center(feature, convert_to_wgs84=convert_coords)

        # 获取父级代码
        parent = props.get("parent", {})
        parent_code = str(parent.get("adcode", "")).zfill(6) if parent and parent.get("adcode") else None

        # 生成英文名称
        name_en = get_name_en(name, adcode, level, self.special_mapping)

        # 检查是否已存在
        result = await db.execute(
            select(AdminDivision).where(AdminDivision.code == adcode)
        )
        existing = result.scalar_one_or_none()

        if existing:
            if force:
                # 更新已有记录
                existing.name = name
                existing.name_en = name_en
                existing.level = level
                existing.parent_code = parent_code
                existing.province_code = province_code
                existing.city_code = city_code
                existing.children_num = children_num
                if bounds[0] is not None:
                    existing.min_lon = bounds[0]
                    existing.min_lat = bounds[1]
                    existing.max_lon = bounds[2]
                    existing.max_lat = bounds[3]
                if center[0] is not None:
                    existing.center_lon = center[0]
                    existing.center_lat = center[1]
                return True
            else:
                # 仅更新边界和中心点（如果之前没有）
                if existing.min_lon is None and bounds[0] is not None:
                    existing.min_lon = bounds[0]
                    existing.min_lat = bounds[1]
                    existing.max_lon = bounds[2]
                    existing.max_lat = bounds[3]
                if existing.center_lon is None and center[0] is not None:
                    existing.center_lon = center[0]
                    existing.center_lat = center[1]
                if existing.children_num is None:
                    existing.children_num = children_num
                return True
        else:
            # 创建新记录
            division = AdminDivision(
                code=adcode,
                name=name,
                name_en=name_en,
                level=level,
                parent_code=parent_code,
                province_code=province_code,
                city_code=city_code,
                children_num=children_num,
                min_lon=bounds[0],
                min_lat=bounds[1],
                max_lon=bounds[2],
                max_lat=bounds[3],
                center_lon=center[0],
                center_lat=center[1],
            )
            db.add(division)
            return True

    async def _import_legacy_feature(
        self,
        db: AsyncSession,
        feature: dict,
        force: bool
    ) -> bool:
        """
        导入旧格式（map 目录）的 GeoJSON feature

        Args:
            db: 数据库会话
            feature: GeoJSON feature
            force: 是否强制覆盖

        Returns:
            bool: 是否成功导入/更新
        """
        props = feature.get("properties", {})
        code = str(props.get("id", ""))
        name = props.get("name", "")
        level_num = props.get("level", 0)

        if not code or not name:
            return False

        # 转换层级
        level_map = {2: "province", 3: "city", 4: "area"}
        level = level_map.get(level_num, "area")

        # 确定省市代码
        if level == "province":
            province_code = code
            city_code = None
            parent_code = None
        elif level == "city":
            province_code = code[:2] + "0000" if len(code) >= 2 else None
            city_code = code
            parent_code = province_code
        else:
            province_code = code[:2] + "0000" if len(code) >= 2 else None
            city_code = code[:4] + "00" if len(code) >= 4 else None
            parent_code = city_code

        # 生成英文名称
        name_en = get_name_en(name, code, level, self.special_mapping)

        # 提取边界
        coords = self._extract_coordinates(feature.get("geometry", {}))
        if coords:
            min_lon = int(min(c[1] for c in coords) * 1e6)
            min_lat = int(min(c[0] for c in coords) * 1e6)
            max_lon = int(max(c[1] for c in coords) * 1e6)
            max_lat = int(max(c[0] for c in coords) * 1e6)
        else:
            min_lon = min_lat = max_lon = max_lat = None

        # 检查是否已存在
        result = await db.execute(
            select(AdminDivision).where(AdminDivision.code == code)
        )
        existing = result.scalar_one_or_none()

        if existing:
            if force:
                existing.name = name
                existing.name_en = name_en
                existing.level = level
                existing.parent_code = parent_code
                existing.province_code = province_code
                existing.city_code = city_code
                if min_lon is not None:
                    existing.min_lon = min_lon
                    existing.min_lat = min_lat
                    existing.max_lon = max_lon
                    existing.max_lat = max_lat
                return True
            else:
                if existing.min_lon is None and min_lon is not None:
                    existing.min_lon = min_lon
                    existing.min_lat = min_lat
                    existing.max_lon = max_lon
                    existing.max_lat = max_lat
                return True
        else:
            division = AdminDivision(
                code=code,
                name=name,
                name_en=name_en,
                level=level,
                parent_code=parent_code,
                province_code=province_code,
                city_code=city_code,
                min_lon=min_lon,
                min_lat=min_lat,
                max_lon=max_lon,
                max_lat=max_lat,
            )
            db.add(division)
            return True

    def _detect_geojson_format(self, data: dict) -> str:
        """
        检测 GeoJSON 格式类型

        Args:
            data: GeoJSON 数据

        Returns:
            str: 格式类型 ("datav" 或 "legacy")
        """
        features = data.get("features", [])
        if not features:
            return "unknown"

        sample = features[0].get("properties", {})

        if "adcode" in sample and "parent" in sample:
            return "datav"  # 阿里 DataV 格式
        elif "id" in sample and "level" in sample:
            return "legacy"  # 当前 map 目录格式
        else:
            return "unknown"
