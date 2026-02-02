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
from sqlalchemy import select, and_, text, func
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
        # PostGIS 可用性缓存
        self._postgis_available: Optional[bool] = None

    async def _is_postgis_available(self, db: AsyncSession) -> bool:
        """
        检测 PostGIS 是否可用，并自动补全空间表结构

        条件：
        1. 数据库类型为 PostgreSQL
        2. 已安装 PostGIS 扩展

        如果 PostGIS 可用但空间表结构不完整，会自动创建。

        Returns:
            bool: PostGIS 是否可用
        """
        # 使用缓存
        if self._postgis_available is not None:
            return self._postgis_available

        if settings.DATABASE_TYPE != "postgresql":
            self._postgis_available = False
            return False

        try:
            # 检查 PostGIS 扩展是否存在
            result = await db.execute(
                text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'postgis')")
            )
            postgis_installed = result.scalar_one()

            if not postgis_installed:
                self._postgis_available = False
                return False

            # PostGIS 已安装，检查并补全空间表结构
            await self._ensure_spatial_table(db)
            self._postgis_available = True

        except Exception as e:
            logger.warning(f"PostGIS 检测失败: {e}")
            self._postgis_available = False

        return self._postgis_available

    async def _ensure_spatial_table(self, db: AsyncSession) -> None:
        """
        确保 PostGIS 空间表结构完整

        如果表不存在或 geom 字段不存在，自动创建。
        """
        try:
            # 检查表是否存在
            result = await db.execute(text("""
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = 'admin_divisions_spatial'
                )
            """))
            table_exists = result.scalar_one()

            if not table_exists:
                # 创建完整的空间表
                logger.info("创建 admin_divisions_spatial 表")
                await db.execute(text("""
                    CREATE TABLE admin_divisions_spatial (
                        division_id INTEGER PRIMARY KEY REFERENCES admin_divisions(id) ON DELETE CASCADE,
                        geom GEOMETRY(GEOMETRY, 4326)
                    )
                """))
                await db.execute(text("""
                    CREATE INDEX idx_admin_divisions_spatial_geom
                        ON admin_divisions_spatial USING GIST(geom)
                """))
                await db.commit()
                logger.info("admin_divisions_spatial 表创建成功")
            else:
                # 表存在，检查 geom 字段是否存在
                result = await db.execute(text("""
                    SELECT EXISTS(
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'admin_divisions_spatial' AND column_name = 'geom'
                    )
                """))
                geom_exists = result.scalar_one()

                if not geom_exists:
                    # 添加 geom 字段
                    logger.info("添加 geom 字段到 admin_divisions_spatial 表")
                    await db.execute(text("""
                        ALTER TABLE admin_divisions_spatial
                        ADD COLUMN geom GEOMETRY(GEOMETRY, 4326)
                    """))
                    await db.execute(text("""
                        CREATE INDEX IF NOT EXISTS idx_admin_divisions_spatial_geom
                            ON admin_divisions_spatial USING GIST(geom)
                    """))
                    await db.commit()
                    logger.info("geom 字段添加成功")

        except Exception as e:
            logger.error(f"确保空间表结构失败: {e}")
            await db.rollback()
            raise

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

        stats = {"provinces": 0, "cities": 0, "areas": 0, "updated": 0, "postgis": 0}

        # 加载特殊地名映射
        self.special_mapping = load_special_mapping()

        # 检测 PostGIS 可用性
        postgis_available = await self._is_postgis_available(db)
        if postgis_available:
            logger.info("PostGIS 可用，将同时保存几何数据")

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
                    updated = await self._import_datav_feature(
                        db, feature, force,
                        convert_coords=True,
                        save_postgis=postgis_available
                    )
                    if updated:
                        stats["updated"] += 1
                        if postgis_available and feature.get("geometry"):
                            stats["postgis"] += 1

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

            # 自动同步 PostGIS 几何数据（如果环境支持）
            if settings.DATABASE_TYPE == "postgresql":
                try:
                    # 检查 PostGIS 扩展是否可用
                    result = await db.execute(
                        text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'postgis')")
                    )
                    postgis_enabled = result.scalar_one()

                    if postgis_enabled:
                        if progress_callback:
                            progress_callback("正在同步 PostGIS 几何数据...", 1, 1)

                        # 确保空间表存在
                        await self._ensure_spatial_table_exists(db)

                        # 同步到 PostGIS 空间表
                        sync_stats = {"success": 0, "skipped": 0, "failed": 0}

                        result = await db.execute(
                            select(AdminDivision.id, AdminDivision.code, AdminDivision.name, AdminDivision.geometry)
                            .where(
                                and_(
                                    AdminDivision.geometry.isnot(None),
                                    AdminDivision.is_valid == True
                                )
                            )
                        )
                        divisions = result.fetchall()

                        for div_id, code, name, geometry_json in divisions:
                            try:
                                geometry_data = json.loads(geometry_json) if isinstance(geometry_json, str) else geometry_json
                                if geometry_data and "type" in geometry_data:
                                    await db.execute(text("""
                                        INSERT INTO admin_divisions_spatial (division_id, geom)
                                        VALUES (:division_id, ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326))
                                        ON CONFLICT (division_id) DO UPDATE
                                        SET geom = EXCLUDED.geom
                                    """), {
                                        "division_id": div_id,
                                        "geojson": json.dumps(geometry_data, ensure_ascii=False)
                                    })
                                    sync_stats["success"] += 1

                                    if sync_stats["success"] % 100 == 0:
                                        await db.commit()

                            except Exception as e:
                                sync_stats["failed"] += 1
                                logger.warning(f"同步 PostGIS 失败 [{code} {name}]: {e}")

                        await db.commit()
                        logger.info(f"PostGIS 自动同步完成: 成功={sync_stats['success']}, 失败={sync_stats['failed']}")
                        stats["postgis_sync"] = sync_stats

                except Exception as e:
                    logger.warning(f"PostGIS 自动同步失败: {e}")

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

            # 解析省级名称映射（解压后才能找到文件）
            province_name_mapping = self._parse_province_name_mapping(temp_dir)

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
                            # 旧格式转换后导入（传入省级名称映射）
                            updated = await self._import_legacy_feature(db, feature, force, province_name_mapping)

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

            # 自动同步 PostGIS 几何数据（如果环境支持）
            if settings.DATABASE_TYPE == "postgresql":
                try:
                    # 检查 PostGIS 扩展是否可用
                    result = await db.execute(
                        text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'postgis')")
                    )
                    postgis_enabled = result.scalar_one()

                    if postgis_enabled:
                        if progress_callback:
                            progress_callback("正在同步 PostGIS 几何数据...", 1, 1)

                        # 确保空间表存在
                        await self._ensure_spatial_table_exists(db)

                        # 统计需要同步的记录数
                        result = await db.execute(
                            select(func.count(AdminDivision.id)).where(
                                and_(
                                    AdminDivision.geometry.isnot(None),
                                    AdminDivision.is_valid == True
                                )
                            )
                        )
                        total_sync = result.scalar() or 0

                        if total_sync > 0:
                            logger.info(f"开始自动同步 PostGIS 几何数据，共 {total_sync} 条记录")

                            # 同步到 PostGIS 空间表
                            sync_stats = {"success": 0, "skipped": 0, "failed": 0}

                            result = await db.execute(
                                select(AdminDivision.id, AdminDivision.code, AdminDivision.name, AdminDivision.geometry)
                                .where(
                                    and_(
                                        AdminDivision.geometry.isnot(None),
                                        AdminDivision.is_valid == True
                                    )
                                )
                            )
                            divisions = result.fetchall()

                            for div_id, code, name, geometry_json in divisions:
                                try:
                                    geometry_data = json.loads(geometry_json) if isinstance(geometry_json, str) else geometry_json
                                    if geometry_data and "type" in geometry_data:
                                        await db.execute(text("""
                                            INSERT INTO admin_divisions_spatial (division_id, geom)
                                            VALUES (:division_id, ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326))
                                            ON CONFLICT (division_id) DO UPDATE
                                            SET geom = EXCLUDED.geom
                                        """), {
                                            "division_id": div_id,
                                            "geojson": json.dumps(geometry_data, ensure_ascii=False)
                                        })
                                        sync_stats["success"] += 1

                                        if sync_stats["success"] % 100 == 0:
                                            await db.commit()

                                except Exception as e:
                                    sync_stats["failed"] += 1
                                    logger.warning(f"同步 PostGIS 失败 [{code} {name}]: {e}")

                            await db.commit()
                            logger.info(f"PostGIS 自动同步完成: 成功={sync_stats['success']}, 失败={sync_stats['failed']}")
                            stats["postgis_sync"] = sync_stats

                except Exception as e:
                    logger.warning(f"PostGIS 自动同步失败: {e}")

            return stats

        finally:
            # 清理临时目录
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _parse_province_name_mapping(self, temp_dir: Path) -> dict[str, str]:
        """
        从压缩包中的"地图数据目录.txt"解析省级名称映射

        格式：--- 110000 北京市 ---
        返回：{"110000": "北京市", ...}

        Args:
            temp_dir: 临时解压目录

        Returns:
            省级代码到完整名称的映射
        """
        mapping = {}
        # 尝试常见的文件名和编码
        possible_names = ["地图数据目录.txt", "地图数据目录"]
        possible_encodings = ["utf-8", "gbk", "gb2312"]

        # 递归搜索所有 txt 文件
        txt_files = list(temp_dir.rglob("*.txt"))

        for txt_file in txt_files:
            # 检查文件名是否匹配
            if not any(name in txt_file.name for name in possible_names):
                continue

            for encoding in possible_encodings:
                try:
                    with open(txt_file, "r", encoding=encoding) as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("--- ") and line.endswith(" ---"):
                                # 解析格式：--- 110000 北京市 ---
                                parts = line[4:-4].strip().split()
                                if len(parts) >= 2:
                                    code = parts[0]
                                    name = " ".join(parts[1:])  # 名称可能包含空格
                                    mapping[code] = name
                    if mapping:
                        logger.info(f"从 {txt_file.relative_to(temp_dir)} 解析到 {len(mapping)} 个省级名称映射")
                        return mapping
                except Exception:
                    continue

        if mapping:
            logger.info(f"解析到 {len(mapping)} 个省级名称映射")
        else:
            logger.debug("未找到或无法解析'地图数据目录.txt'")

        return mapping

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
        convert_coords: bool = True,
        save_postgis: bool = False
    ) -> bool:
        """
        导入单个 DataV 格式的 GeoJSON feature

        Args:
            db: 数据库会话
            feature: GeoJSON feature
            force: 是否强制覆盖
            convert_coords: 是否将坐标从 GCJ02 转换为 WGS84（DataV 在线数据需要转换）
            save_postgis: 是否保存几何到 PostGIS 空间表

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

        # 提取并转换 geometry（用于 shapely 多边形判断）
        geometry = feature.get("geometry")
        geometry_json = None
        if geometry:
            if convert_coords:
                geometry = DataVGeoService.convert_geometry_to_wgs84(geometry)
            geometry_json = json.dumps(geometry)

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

        division_id = None

        if existing:
            division_id = existing.id
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
                if geometry_json is not None:
                    existing.geometry = geometry_json
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
                if existing.geometry is None and geometry_json is not None:
                    existing.geometry = geometry_json
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
                geometry=geometry_json,
            )
            db.add(division)
            # 刷新以获取 ID
            await db.flush()
            division_id = division.id

        # 保存 PostGIS 几何（如果启用）
        if save_postgis and division_id:
            geometry = feature.get("geometry")
            if geometry:
                try:
                    # 使用 savepoint 隔离 PostGIS 操作，避免失败时影响整个事务
                    async with db.begin_nested():
                        # 坐标转换
                        if convert_coords:
                            geometry = DataVGeoService.convert_geometry_to_wgs84(geometry)

                        # 插入或更新 PostGIS 几何
                        geojson_str = json.dumps(geometry)
                        await db.execute(text("""
                            INSERT INTO admin_divisions_spatial (division_id, geom)
                            VALUES (:division_id, ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326))
                            ON CONFLICT (division_id) DO UPDATE SET geom = EXCLUDED.geom
                        """), {"division_id": division_id, "geojson": geojson_str})
                except Exception as e:
                    logger.warning(f"保存 PostGIS 几何失败 [{adcode}]: {e}")

        return True

    async def _import_legacy_feature(
        self,
        db: AsyncSession,
        feature: dict,
        force: bool,
        province_name_mapping: dict[str, str] = None
    ) -> bool:
        """
        导入旧格式（map 目录）的 GeoJSON feature

        Args:
            db: 数据库会话
            feature: GeoJSON feature
            force: 是否强制覆盖
            province_name_mapping: 省级代码到完整名称的映射（来自"地图数据目录.txt"）

        Returns:
            bool: 是否成功导入/更新
        """
        props = feature.get("properties", {})
        code = str(props.get("id", ""))
        name = props.get("name", "")
        level_num = props.get("level", 0)

        if not code or not name:
            return False

        # 对于省级单位，使用映射中的完整名称（如果存在）
        if level_num == 2 and province_name_mapping and code in province_name_mapping:
            name = province_name_mapping[code]

        if not code or not name:
            return False

        # 不设区地级市（只有这 4 个，level=3 但应存为 city）
        CITIES_WITHOUT_DISTRICTS = {"441900", "442000", "460400", "620200"}

        # 省辖县级行政单位列表（手动维护，因为旧格式数据没有 childrenNum 字段）
        # 这些城市代码的 level=3，但实际是省直辖的县级行政单位
        PROVINCE_ADMINISTERED_AREAS = {
            "419000",  # 湖北省直辖（仙桃市、潜江市、天门市等）
            "429000",  # 湖北省直辖（潜江市）
            "469000",  # 海南省直辖
            "659000",  # 新疆兵团城市
        }

        # 转换层级
        level_map = {2: "province", 3: "city", 4: "area"}
        level = level_map.get(level_num, "area")

        # 特殊处理：省辖县级行政单位转换为 area
        # 通过代码前缀判断（如 4190 表示湖北省直辖）
        is_province_administered = False
        if level == "city" and code not in CITIES_WITHOUT_DISTRICTS:
            # 检查代码是否属于省辖县级行政单位范围
            code_prefix = code[:4] if len(code) >= 4 else ""
            if code_prefix in PROVINCE_ADMINISTERED_AREAS or any(code.startswith(p) for p in ["4190", "4290", "4690", "6590"]):
                is_province_administered = True
                level = "area"

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
            # area 级别
            province_code = code[:2] + "0000" if len(code) >= 2 else None
            if is_province_administered:
                # 省辖县级行政单位（原 level=3）：没有市级
                city_code = None
                parent_code = province_code
            else:
                # 正常区县（原 level=4）：有市级
                city_code = code[:4] + "00" if len(code) >= 4 else None
                parent_code = city_code

        # 生成英文名称
        name_en = get_name_en(name, code, level, self.special_mapping)

        # 提取边界和 geometry
        geometry = feature.get("geometry")
        geometry_json = None
        if geometry:
            geometry_json = json.dumps(geometry)

        coords = self._extract_coordinates(geometry)
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
                if geometry_json is not None:
                    existing.geometry = geometry_json
                return True
            else:
                if existing.min_lon is None and min_lon is not None:
                    existing.min_lon = min_lon
                    existing.min_lat = min_lat
                    existing.max_lon = max_lon
                    existing.max_lat = max_lat
                if existing.geometry is None and geometry_json is not None:
                    existing.geometry = geometry_json
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
                geometry=geometry_json,
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

    async def sync_postgis_from_geometry(
        self,
        db: AsyncSession,
        progress_callback: Optional[Callable] = None
    ) -> dict:
        """
        从 geometry 字段同步数据到 PostGIS 空间表

        将 admin_divisions.geometry 字段中的 GeoJSON 数据
        同步到 admin_divisions_spatial.geom 字段。

        Args:
            db: 数据库会话
            progress_callback: 进度回调函数

        Returns:
            dict: 同步统计 {"success": 成功数, "skipped": 跳过数, "failed": 失败数}
        """
        stats = {"success": 0, "skipped": 0, "failed": 0}

        # 1. 检查是否为 PostgreSQL 数据库
        if settings.DATABASE_TYPE != "postgresql":
            raise ValueError("PostGIS 几何同步仅支持 PostgreSQL 数据库")

        # 2. 检查 PostGIS 扩展是否可用
        try:
            result = await db.execute(
                text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'postgis')")
            )
            postgis_enabled = result.scalar_one()
            if not postgis_enabled:
                raise ValueError("PostGIS 扩展未启用，请先安装 PostGIS 扩展")
        except Exception as e:
            raise ValueError(f"检查 PostGIS 扩展失败: {e}")

        # 3. 确保 admin_divisions_spatial 表存在
        await self._ensure_spatial_table_exists(db)

        # 4. 查询所有有 geometry 的记录
        result = await db.execute(
            select(AdminDivision.id, AdminDivision.code, AdminDivision.name, AdminDivision.geometry)
            .where(
                and_(
                    AdminDivision.geometry.is_not(None),
                    AdminDivision.is_valid == True
                )
            )
        )
        divisions = result.fetchall()

        total = len(divisions)
        if total == 0:
            logger.info("没有找到需要同步的 geometry 数据")
            return stats

        logger.info(f"开始同步 {total} 条记录到 PostGIS 空间表")

        # 5. 逐条同步
        for i, (div_id, code, name, geometry_json) in enumerate(divisions):
            try:
                # 验证 GeoJSON 格式
                geometry_data = json.loads(geometry_json) if isinstance(geometry_json, str) else geometry_json
                if not geometry_data or "type" not in geometry_data:
                    stats["skipped"] += 1
                    logger.warning(f"跳过无效的 geometry [{code} {name}]")
                    continue

                # 插入或更新 PostGIS 几何
                await db.execute(text("""
                    INSERT INTO admin_divisions_spatial (division_id, geom)
                    VALUES (:division_id, ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326))
                    ON CONFLICT (division_id) DO UPDATE
                    SET geom = EXCLUDED.geom
                """), {
                    "division_id": div_id,
                    "geojson": json.dumps(geometry_data, ensure_ascii=False)
                })

                stats["success"] += 1

                # 每处理 100 条提交一次
                if (i + 1) % 100 == 0:
                    await db.commit()

                # 进度回调
                if progress_callback and i % 10 == 0:
                    progress_callback("同步中", i + 1, total)

            except Exception as e:
                stats["failed"] += 1
                logger.warning(f"同步失败 [{code} {name}]: {e}")

        # 最终提交
        await db.commit()

        logger.info(f"PostGIS 几何同步完成: 成功={stats['success']}, 跳过={stats['skipped']}, 失败={stats['failed']}")

        return stats

    async def _ensure_spatial_table_exists(self, db: AsyncSession) -> None:
        """
        确保 admin_divisions_spatial 表存在

        如果表不存在则创建，如果 geom 字段不存在则添加。
        """
        # 检查表是否存在
        result = await db.execute(text("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'admin_divisions_spatial'
            )
        """))
        table_exists = result.scalar_one()

        if not table_exists:
            logger.info("创建 admin_divisions_spatial 表")
            await db.execute(text("""
                CREATE TABLE admin_divisions_spatial (
                    division_id INTEGER PRIMARY KEY REFERENCES admin_divisions(id) ON DELETE CASCADE,
                    geom GEOMETRY(GEOMETRY, 4326)
                )
            """))
            await db.execute(text("""
                CREATE INDEX idx_admin_divisions_spatial_geom
                    ON admin_divisions_spatial USING GIST(geom)
            """))
            await db.commit()
            logger.info("admin_divisions_spatial 表创建成功")
            return

        # 表存在，检查 geom 字段是否存在
        result = await db.execute(text("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'admin_divisions_spatial' AND column_name = 'geom'
            )
        """))
        geom_exists = result.scalar_one()

        if not geom_exists:
            logger.info("添加 geom 字段到 admin_divisions_spatial 表")
            await db.execute(text("""
                ALTER TABLE admin_divisions_spatial
                ADD COLUMN geom GEOMETRY(GEOMETRY, 4326)
            """))
            await db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_admin_divisions_spatial_geom
                    ON admin_divisions_spatial USING GIST(geom)
            """))
            await db.commit()
            logger.info("geom 字段添加成功")

    async def get_postgis_sync_status(self, db: AsyncSession) -> dict:
        """
        获取 PostGIS 同步状态

        返回 geometry 字段有数据的记录数和 PostGIS 空间表有数据的记录数。

        Args:
            db: 数据库会话

        Returns:
            dict: 同步状态信息
        """
        status = {
            "has_geometry": 0,
            "has_postgis": 0,
            "need_sync": 0,
            "postgis_enabled": False,
            "spatial_table_exists": False
        }

        # 检查是否为 PostgreSQL
        if settings.DATABASE_TYPE != "postgresql":
            return status

        # 检查 PostGIS 扩展
        try:
            result = await db.execute(
                text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'postgis')")
            )
            status["postgis_enabled"] = result.scalar_one()
        except Exception:
            pass

        if not status["postgis_enabled"]:
            return status

        # 检查空间表是否存在
        try:
            result = await db.execute(text("""
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = 'admin_divisions_spatial'
                )
            """))
            status["spatial_table_exists"] = result.scalar_one()
        except Exception:
            pass

        if not status["spatial_table_exists"]:
            return status

        # 统计有 geometry 的记录数
        result = await db.execute(
            select(func.count(AdminDivision.id)).where(
                and_(
                    AdminDivision.geometry.is_not(None),
                    AdminDivision.is_valid == True
                )
            )
        )
        status["has_geometry"] = result.scalar() or 0

        # 统计有 PostGIS 几何的记录数
        try:
            result = await db.execute(
                text("SELECT COUNT(*) FROM admin_divisions_spatial")
            )
            status["has_postgis"] = result.scalar() or 0
        except Exception:
            pass

        # 计算需要同步的数量
        status["need_sync"] = max(0, status["has_geometry"] - status["has_postgis"])

        return status
