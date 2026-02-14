# GeoJSON 行政区划导入功能实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 重构行政区划导入功能，统一使用 GeoJSON 作为数据源，支持阿里 DataV 在线拉取和压缩包上传。

**Architecture:** 新建 `DataVGeoService` 处理在线数据获取，重构 `AdminDivisionImportService` 支持两种导入方式，前端管理界面新增导入控制面板。

**Tech Stack:** Python/FastAPI, SQLAlchemy, aiohttp, Vue 3/Element Plus

---

## Task 1: 数据库迁移 - 新增字段

**Files:**
- Create: `backend/alembic/versions/011_add_admin_division_center.sqlite`
- Create: `backend/alembic/versions/011_add_admin_division_center.mysql`
- Create: `backend/alembic/versions/011_add_admin_division_center.postgresql`
- Modify: `backend/app/models/admin_division.py`

**Step 1: 创建 SQLite 迁移脚本**

```sql
-- 011_add_admin_division_center.sqlite
-- Add center point and children_num fields for GeoJSON import

ALTER TABLE admin_divisions ADD COLUMN center_lon INTEGER;
ALTER TABLE admin_divisions ADD COLUMN center_lat INTEGER;
ALTER TABLE admin_divisions ADD COLUMN children_num INTEGER;
```

**Step 2: 创建 MySQL 迁移脚本**

```sql
-- 011_add_admin_division_center.mysql
-- Add center point and children_num fields for GeoJSON import

ALTER TABLE admin_divisions ADD COLUMN center_lon INT NULL;
ALTER TABLE admin_divisions ADD COLUMN center_lat INT NULL;
ALTER TABLE admin_divisions ADD COLUMN children_num INT NULL;
```

**Step 3: 创建 PostgreSQL 迁移脚本**

```sql
-- 011_add_admin_division_center.postgresql
-- Add center point and children_num fields for GeoJSON import

ALTER TABLE admin_divisions ADD COLUMN IF NOT EXISTS center_lon INTEGER;
ALTER TABLE admin_divisions ADD COLUMN IF NOT EXISTS center_lat INTEGER;
ALTER TABLE admin_divisions ADD COLUMN IF NOT EXISTS children_num INTEGER;
```

**Step 4: 更新 AdminDivision 模型**

修改 `backend/app/models/admin_division.py`，在现有字段后添加：

```python
    # 中心点坐标（用于地图显示，坐标 * 1e6 存储为整数）
    center_lon = Column(Integer, nullable=True, comment="中心点经度 * 1e6")
    center_lat = Column(Integer, nullable=True, comment="中心点纬度 * 1e6")

    # 子级数量（用于判断不设区地级市）
    children_num = Column(Integer, nullable=True, comment="子级行政区划数量")
```

**Step 5: 提交**

```bash
git add backend/alembic/versions/011_add_admin_division_center.*
git add backend/app/models/admin_division.py
git commit -m "feat(db): add center_lon, center_lat, children_num to admin_divisions"
```

---

## Task 2: DataV 数据获取服务

**Files:**
- Create: `backend/app/services/datav_geo_service.py`

**Step 1: 创建 DataVGeoService 类**

```python
"""
阿里 DataV GeoAtlas 数据获取服务

从 https://geo.datav.aliyun.com 获取行政区划 GeoJSON 数据。
"""
import asyncio
import aiohttp
from typing import Optional, Callable
from loguru import logger


class DataVGeoService:
    """阿里 DataV GeoAtlas 数据获取服务"""

    BASE_URL = "https://geo.datav.aliyun.com/areas_v3/bound"

    # 不设区的地级市（全国仅 4 个）
    CITIES_WITHOUT_DISTRICTS = {"441900", "442000", "460400", "620200"}

    # 直辖市
    MUNICIPALITIES = {"110000", "120000", "310000", "500000"}

    def __init__(self, concurrency: int = 10, delay: float = 0.1):
        """
        初始化服务

        Args:
            concurrency: 最大并发请求数
            delay: 请求间隔（秒）
        """
        self.concurrency = concurrency
        self.delay = delay
        self._semaphore: Optional[asyncio.Semaphore] = None

    async def fetch_division(self, adcode: str, with_children: bool = True) -> dict:
        """
        获取单个行政区划的 GeoJSON

        Args:
            adcode: 行政区划代码
            with_children: 是否获取包含子级的完整数据

        Returns:
            GeoJSON FeatureCollection
        """
        suffix = "_full" if with_children else ""
        url = f"{self.BASE_URL}/{adcode}{suffix}.json"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    raise Exception(f"Failed to fetch {url}: HTTP {resp.status}")

    async def fetch_all_recursive(
        self,
        start_code: str = "100000",
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> list[dict]:
        """
        递归获取所有行政区划

        Args:
            start_code: 起始代码（默认全国）
            progress_callback: 进度回调 callback(message, current, total)

        Returns:
            所有 GeoJSON features 列表
        """
        self._semaphore = asyncio.Semaphore(self.concurrency)
        all_features = []

        # 第一步：获取省级数据
        if progress_callback:
            progress_callback("正在获取省级数据...", 0, 100)

        china_data = await self.fetch_division(start_code, with_children=True)
        provinces = china_data.get("features", [])

        # 收集省级 features
        for feature in provinces:
            all_features.append(feature)

        # 第二步：递归获取市级和区县级
        total_provinces = len(provinces)
        for i, province in enumerate(provinces):
            props = province["properties"]
            province_code = str(props["adcode"])
            province_name = props["name"]

            if progress_callback:
                pct = int((i + 1) / total_provinces * 100)
                progress_callback(f"正在获取 {province_name}...", pct, 100)

            # 获取该省的市级数据
            try:
                province_data = await self._fetch_with_semaphore(province_code)
                cities = province_data.get("features", [])

                for city in cities:
                    all_features.append(city)
                    city_props = city["properties"]
                    city_code = str(city_props["adcode"])
                    children_num = city_props.get("childrenNum", 0)
                    level = city_props.get("level", "")

                    # 如果是市级且有子级，继续获取区县
                    if level == "city" and children_num > 0:
                        if city_code not in self.CITIES_WITHOUT_DISTRICTS:
                            try:
                                city_data = await self._fetch_with_semaphore(city_code)
                                districts = city_data.get("features", [])
                                all_features.extend(districts)
                            except Exception as e:
                                logger.warning(f"获取 {city_code} 区县数据失败: {e}")

                await asyncio.sleep(self.delay)

            except Exception as e:
                logger.error(f"获取 {province_name} 数据失败: {e}")

        if progress_callback:
            progress_callback("获取完成", 100, 100)

        return all_features

    async def fetch_province(
        self,
        province_code: str,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> list[dict]:
        """
        获取单个省份的所有数据

        Args:
            province_code: 省级代码
            progress_callback: 进度回调

        Returns:
            该省所有 GeoJSON features 列表
        """
        self._semaphore = asyncio.Semaphore(self.concurrency)
        all_features = []

        # 获取省级数据（包含市级子级）
        province_data = await self.fetch_division(province_code, with_children=True)
        cities = province_data.get("features", [])

        total = len(cities)
        for i, city in enumerate(cities):
            all_features.append(city)
            city_props = city["properties"]
            city_code = str(city_props["adcode"])
            children_num = city_props.get("childrenNum", 0)
            level = city_props.get("level", "")

            if progress_callback:
                pct = int((i + 1) / total * 100)
                progress_callback(f"正在获取 {city_props['name']}...", pct, 100)

            # 如果是市级且有子级，获取区县
            if level == "city" and children_num > 0:
                if city_code not in self.CITIES_WITHOUT_DISTRICTS:
                    try:
                        city_data = await self._fetch_with_semaphore(city_code)
                        districts = city_data.get("features", [])
                        all_features.extend(districts)
                    except Exception as e:
                        logger.warning(f"获取 {city_code} 区县数据失败: {e}")

        return all_features

    async def _fetch_with_semaphore(self, adcode: str) -> dict:
        """带信号量控制的获取"""
        async with self._semaphore:
            await asyncio.sleep(self.delay)
            return await self.fetch_division(adcode, with_children=True)

    @staticmethod
    def classify_division(feature: dict) -> tuple[str, str, str]:
        """
        分类行政区划，返回 (province_code, city_code, level)

        Args:
            feature: GeoJSON feature

        Returns:
            (province_code, city_code, level) 元组
        """
        props = feature["properties"]
        adcode = str(props["adcode"]).zfill(6)
        level = props.get("level", "")
        parent = props.get("parent", {})
        parent_adcode = str(parent.get("adcode", "")).zfill(6) if parent else ""
        children_num = props.get("childrenNum", 0)

        MUNICIPALITIES = {"110000", "120000", "310000", "500000"}
        CITIES_WITHOUT_DISTRICTS = {"441900", "442000", "460400", "620200"}

        if level == "province":
            return (adcode, None, "province")

        elif level == "city":
            if adcode in CITIES_WITHOUT_DISTRICTS:
                # 不设区地级市：省=parent, 市=自己, 县=空
                return (parent_adcode, adcode, "city")
            elif children_num == 0:
                # 省辖县级行政单位：省=parent, 市=空, 县=自己
                return (parent_adcode, None, "area")
            else:
                # 正常地级市
                return (parent_adcode, adcode, "city")

        elif level == "district":
            if parent_adcode in MUNICIPALITIES:
                # 直辖市区县：省=parent, 市=空, 县=自己
                return (parent_adcode, None, "area")
            else:
                # 普通区县
                province_code = adcode[:2] + "0000"
                return (province_code, parent_adcode, "area")

        return (None, None, "unknown")
```

**Step 2: 提交**

```bash
git add backend/app/services/datav_geo_service.py
git commit -m "feat: add DataVGeoService for fetching GeoJSON from Aliyun DataV"
```

---

## Task 3: 重构导入服务 - 在线拉取

**Files:**
- Modify: `backend/app/services/admin_division_import_service.py`

**Step 1: 添加在线导入方法**

在 `AdminDivisionImportService` 类中添加新方法：

```python
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
            province_codes: 要导入的省份代码列表，None 表示全国
            progress_callback: 进度回调函数 callback(message, current, total)
            force: 是否强制重新导入（删除已有数据）

        Returns:
            dict: 导入统计 {"provinces": n, "cities": n, "areas": n}
        """
        from app.services.datav_geo_service import DataVGeoService

        stats = {"provinces": 0, "cities": 0, "areas": 0}

        # 加载特殊地名映射
        self.special_mapping = load_special_mapping()

        # 如果强制重新导入，先删除已有数据
        if force:
            if province_codes:
                # 只删除指定省份的数据
                for code in province_codes:
                    await db.execute(
                        text("DELETE FROM admin_divisions WHERE province_code = :code OR code = :code"),
                        {"code": code}
                    )
            else:
                await db.execute(text("DELETE FROM admin_divisions"))
            await db.commit()
            logger.info("已清空指定行政区划数据")

        # 获取数据
        service = DataVGeoService()

        if province_codes:
            # 按省份获取
            all_features = []
            for code in province_codes:
                features = await service.fetch_province(code, progress_callback)
                all_features.extend(features)
        else:
            # 全国获取
            all_features = await service.fetch_all_recursive("100000", progress_callback)

        # 导入数据
        for feature in all_features:
            division = self._create_division_from_datav(feature)
            if division:
                await self._upsert_division(db, division, force)
                level = division.level
                if level == "province":
                    stats["provinces"] += 1
                elif level == "city":
                    stats["cities"] += 1
                else:
                    stats["areas"] += 1

        await db.commit()
        logger.info(f"在线导入完成: {stats}")
        return stats

    def _create_division_from_datav(self, feature: dict) -> Optional[AdminDivision]:
        """
        从 DataV GeoJSON feature 创建 AdminDivision 对象

        Args:
            feature: GeoJSON feature

        Returns:
            AdminDivision 对象，如果无效则返回 None
        """
        from app.services.datav_geo_service import DataVGeoService

        props = feature.get("properties", {})
        adcode = props.get("adcode")
        name = props.get("name")

        if not adcode or not name:
            return None

        code = str(adcode).zfill(6)
        province_code, city_code, level = DataVGeoService.classify_division(feature)

        # 生成英文名称
        name_en = get_name_en(name, code, level, self.special_mapping)

        # 提取中心点
        center = props.get("center", [])
        center_lon = int(center[0] * 1e6) if len(center) >= 2 else None
        center_lat = int(center[1] * 1e6) if len(center) >= 2 else None

        # 提取边界框
        geometry = feature.get("geometry", {})
        coords = self._extract_coordinates(geometry)
        if coords:
            min_lat = int(min(c[0] for c in coords) * 1e6)
            max_lat = int(max(c[0] for c in coords) * 1e6)
            min_lon = int(min(c[1] for c in coords) * 1e6)
            max_lon = int(max(c[1] for c in coords) * 1e6)
        else:
            min_lat = max_lat = min_lon = max_lon = None

        # 父级代码
        parent = props.get("parent", {})
        parent_code = str(parent.get("adcode", "")).zfill(6) if parent.get("adcode") else None

        division = AdminDivision()
        division.code = code
        division.name = name
        division.name_en = name_en
        division.level = level
        division.parent_code = parent_code
        division.province_code = province_code
        division.city_code = city_code
        division.center_lon = center_lon
        division.center_lat = center_lat
        division.children_num = props.get("childrenNum", 0)
        division.min_lat = min_lat
        division.max_lat = max_lat
        division.min_lon = min_lon
        division.max_lon = max_lon
        division.is_valid = True

        return division

    async def _upsert_division(self, db: AsyncSession, division: AdminDivision, force: bool):
        """插入或更新行政区划数据"""
        database_type = getattr(settings, 'DATABASE_TYPE', 'sqlite')

        if database_type == "postgresql":
            data = {
                "code": division.code,
                "name": division.name,
                "name_en": division.name_en,
                "level": division.level,
                "parent_code": division.parent_code,
                "province_code": division.province_code,
                "city_code": division.city_code,
                "center_lon": division.center_lon,
                "center_lat": division.center_lat,
                "children_num": division.children_num,
                "min_lat": division.min_lat,
                "max_lat": division.max_lat,
                "min_lon": division.min_lon,
                "max_lon": division.max_lon,
                "is_valid": True,
            }
            stmt = pg_insert(AdminDivision).values(data)
            stmt = stmt.on_conflict_do_update(
                index_elements=['code'],
                set_=data
            )
            await db.execute(stmt)
        else:
            # SQLite / MySQL
            existing = await db.execute(
                select(AdminDivision).where(AdminDivision.code == division.code)
            )
            existing_div = existing.scalar_one_or_none()
            if existing_div:
                # 更新现有记录
                for key in ['name', 'name_en', 'level', 'parent_code', 'province_code',
                            'city_code', 'center_lon', 'center_lat', 'children_num',
                            'min_lat', 'max_lat', 'min_lon', 'max_lon']:
                    setattr(existing_div, key, getattr(division, key))
                existing_div.is_valid = True
            else:
                db.add(division)
```

**Step 2: 提交**

```bash
git add backend/app/services/admin_division_import_service.py
git commit -m "feat: add import_from_datav_online method for online GeoJSON import"
```

---

## Task 4: 重构导入服务 - 压缩包上传

**Files:**
- Modify: `backend/app/services/admin_division_import_service.py`

**Step 1: 添加压缩包导入和格式检测方法**

```python
    async def import_from_geojson_archive(
        self,
        db: AsyncSession,
        archive_path: Path,
        progress_callback: Optional[Callable] = None,
        force: bool = False
    ) -> dict:
        """
        从上传的压缩包导入行政区划数据

        支持两种格式：
        1. DataV 格式：包含 adcode, name, level, parent 等字段
        2. 旧格式（map 目录）：包含 id, name, level(数字) 等字段

        Args:
            db: 数据库会话
            archive_path: 压缩包路径
            progress_callback: 进度回调函数
            force: 是否强制重新导入

        Returns:
            dict: 导入统计
        """
        import zipfile
        import tempfile

        stats = {"provinces": 0, "cities": 0, "areas": 0}
        self.special_mapping = load_special_mapping()

        # 解压到临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            with zipfile.ZipFile(archive_path, 'r') as zf:
                zf.extractall(temp_path)

            # 查找所有 GeoJSON 文件
            geojson_files = list(temp_path.rglob("*.json"))

            if not geojson_files:
                raise ValueError("压缩包中未找到 JSON 文件")

            # 检测格式
            sample_file = geojson_files[0]
            with open(sample_file, "r", encoding="utf-8") as f:
                sample_data = json.load(f)

            format_type = self._detect_geojson_format(sample_data)
            logger.info(f"检测到 GeoJSON 格式: {format_type}")

            # 加载省份名称映射（用于旧格式）
            province_names = {}
            if format_type == "legacy":
                province_names = self._load_province_full_names(temp_path)

            # 如果强制重新导入，先删除已有数据
            if force:
                await db.execute(text("DELETE FROM admin_divisions"))
                await db.commit()

            # 处理所有文件
            total_files = len(geojson_files)
            all_features = []

            for i, geojson_file in enumerate(geojson_files):
                if progress_callback:
                    pct = int((i + 1) / total_files * 50)  # 前 50% 用于读取
                    progress_callback(f"读取文件 {geojson_file.name}...", pct, 100)

                try:
                    with open(geojson_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    features = data.get("features", [])
                    for feature in features:
                        if format_type == "legacy":
                            feature = self._convert_legacy_feature(feature, province_names)
                        if feature:
                            all_features.append(feature)

                except Exception as e:
                    logger.warning(f"处理文件 {geojson_file} 失败: {e}")

            # 导入数据
            total_features = len(all_features)
            for i, feature in enumerate(all_features):
                if progress_callback and i % 100 == 0:
                    pct = 50 + int((i + 1) / total_features * 50)  # 后 50% 用于导入
                    progress_callback(f"导入数据...", pct, 100)

                division = self._create_division_from_datav(feature)
                if division:
                    await self._upsert_division(db, division, force)
                    level = division.level
                    if level == "province":
                        stats["provinces"] += 1
                    elif level == "city":
                        stats["cities"] += 1
                    else:
                        stats["areas"] += 1

            await db.commit()

        logger.info(f"压缩包导入完成: {stats}")
        return stats

    def _detect_geojson_format(self, data: dict) -> str:
        """
        检测 GeoJSON 格式类型

        Args:
            data: GeoJSON 数据

        Returns:
            "datav" 或 "legacy"
        """
        features = data.get("features", [])
        if not features:
            return "unknown"

        sample = features[0].get("properties", {})

        if "adcode" in sample and "parent" in sample:
            return "datav"
        elif "id" in sample and isinstance(sample.get("level"), int):
            return "legacy"
        else:
            return "unknown"

    def _load_province_full_names(self, map_path: Path) -> dict[str, str]:
        """
        从地图数据目录.txt 加载省级全称

        Args:
            map_path: 地图数据目录

        Returns:
            {代码: 全称} 映射
        """
        import re

        mapping = {}

        # 尝试多个可能的位置
        possible_paths = [
            map_path / "地图数据目录.txt",
            map_path / "map" / "地图数据目录.txt",
        ]

        for txt_file in possible_paths:
            if txt_file.exists():
                try:
                    content = txt_file.read_text(encoding="utf-8")
                    for line in content.splitlines():
                        match = re.match(r"---\s+(\d+)\s+(.+?)\s+---", line.strip())
                        if match:
                            code, full_name = match.groups()
                            mapping[code] = full_name
                    break
                except Exception as e:
                    logger.warning(f"读取 {txt_file} 失败: {e}")

        return mapping

    def _convert_legacy_feature(self, feature: dict, province_names: dict) -> Optional[dict]:
        """
        将旧格式 GeoJSON feature 转换为 DataV 兼容格式

        Args:
            feature: 旧格式 feature
            province_names: 省份名称映射

        Returns:
            DataV 兼容格式的 feature
        """
        props = feature.get("properties", {})
        code = props.get("id")
        level_num = props.get("level")

        if not code or level_num is None:
            return None

        # 省级名称从映射表获取全称
        if level_num == 2:
            name = province_names.get(code, props.get("name", ""))
        else:
            name = props.get("name", "")

        # 层级映射
        level_map = {2: "province", 3: "city", 4: "district"}
        level = level_map.get(level_num, "district")

        # 推断父级代码
        parent_adcode = None
        if level_num == 3:  # 市级，父级是省
            parent_adcode = code[:2] + "0000"
        elif level_num == 4:  # 区县级，父级是市
            parent_adcode = code[:4] + "00"

        # 构造 DataV 兼容格式
        new_props = {
            "adcode": int(code),
            "name": name,
            "level": level,
            "childrenNum": props.get("childNum", 0),
            "parent": {"adcode": int(parent_adcode)} if parent_adcode else {},
            "center": props.get("cp", []),
        }

        return {
            "type": "Feature",
            "properties": new_props,
            "geometry": feature.get("geometry", {}),
        }
```

**Step 2: 提交**

```bash
git add backend/app/services/admin_division_import_service.py
git commit -m "feat: add import_from_geojson_archive for ZIP upload import"
```

---

## Task 5: API 端点

**Files:**
- Modify: `backend/app/api/admin.py`
- Modify: `backend/app/schemas/admin.py` (如需要)

**Step 1: 添加导入相关 API 端点**

在 `backend/app/api/admin.py` 中添加：

```python
from fastapi import UploadFile, File, BackgroundTasks
from pathlib import Path
import tempfile
import uuid

# 存储导入任务状态
_import_tasks: dict[str, dict] = {}


@router.get("/admin-divisions/status")
async def get_division_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """获取行政区划数据状态"""
    from sqlalchemy import func

    # 统计各级数量
    result = await db.execute(
        select(
            AdminDivision.level,
            func.count(AdminDivision.id)
        ).where(
            AdminDivision.is_valid == True
        ).group_by(AdminDivision.level)
    )
    counts = {row[0]: row[1] for row in result.fetchall()}

    # 获取省份列表
    result = await db.execute(
        select(AdminDivision.code, AdminDivision.name).where(
            AdminDivision.level == "province",
            AdminDivision.is_valid == True
        ).order_by(AdminDivision.code)
    )
    provinces = [{"code": row[0], "name": row[1]} for row in result.fetchall()]

    return {
        "total_count": sum(counts.values()),
        "provinces_count": counts.get("province", 0),
        "cities_count": counts.get("city", 0),
        "areas_count": counts.get("area", 0),
        "provinces": provinces,
    }


@router.post("/admin-divisions/import/online")
async def import_divisions_online(
    background_tasks: BackgroundTasks,
    province_codes: list[str] = None,
    force: bool = False,
    bounds_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """从阿里 DataV 在线拉取行政区划数据"""
    task_id = str(uuid.uuid4())

    _import_tasks[task_id] = {
        "status": "pending",
        "progress": 0,
        "message": "准备中...",
    }

    async def run_import():
        try:
            _import_tasks[task_id]["status"] = "running"

            def progress_callback(message: str, current: int, total: int):
                _import_tasks[task_id]["progress"] = current
                _import_tasks[task_id]["message"] = message

            service = AdminDivisionImportService()

            # 创建新的数据库会话
            async with async_session_maker() as session:
                stats = await service.import_from_datav_online(
                    session,
                    province_codes=province_codes,
                    progress_callback=progress_callback,
                    force=force
                )

            _import_tasks[task_id]["status"] = "completed"
            _import_tasks[task_id]["progress"] = 100
            _import_tasks[task_id]["message"] = f"导入完成: {stats}"
            _import_tasks[task_id]["stats"] = stats

        except Exception as e:
            logger.error(f"在线导入失败: {e}")
            _import_tasks[task_id]["status"] = "failed"
            _import_tasks[task_id]["message"] = str(e)

    background_tasks.add_task(run_import)

    return {"task_id": task_id}


@router.post("/admin-divisions/import/upload")
async def import_divisions_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    force: bool = False,
    current_user: User = Depends(get_current_admin_user)
):
    """从上传的压缩包导入行政区划数据"""
    task_id = str(uuid.uuid4())

    # 保存上传的文件
    temp_dir = Path(tempfile.gettempdir())
    temp_file = temp_dir / f"admin_division_{task_id}.zip"

    with open(temp_file, "wb") as f:
        content = await file.read()
        f.write(content)

    _import_tasks[task_id] = {
        "status": "pending",
        "progress": 0,
        "message": "准备中...",
    }

    async def run_import():
        try:
            _import_tasks[task_id]["status"] = "running"

            def progress_callback(message: str, current: int, total: int):
                _import_tasks[task_id]["progress"] = current
                _import_tasks[task_id]["message"] = message

            service = AdminDivisionImportService()

            async with async_session_maker() as session:
                stats = await service.import_from_geojson_archive(
                    session,
                    archive_path=temp_file,
                    progress_callback=progress_callback,
                    force=force
                )

            _import_tasks[task_id]["status"] = "completed"
            _import_tasks[task_id]["progress"] = 100
            _import_tasks[task_id]["message"] = f"导入完成: {stats}"
            _import_tasks[task_id]["stats"] = stats

        except Exception as e:
            logger.error(f"压缩包导入失败: {e}")
            _import_tasks[task_id]["status"] = "failed"
            _import_tasks[task_id]["message"] = str(e)
        finally:
            # 清理临时文件
            if temp_file.exists():
                temp_file.unlink()

    background_tasks.add_task(run_import)

    return {"task_id": task_id}


@router.get("/admin-divisions/import/progress/{task_id}")
async def get_import_progress(
    task_id: str,
    current_user: User = Depends(get_current_admin_user)
):
    """获取导入任务进度"""
    if task_id not in _import_tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    return _import_tasks[task_id]
```

**Step 2: 添加必要的导入**

确保文件顶部有以下导入：

```python
from app.services.admin_division_import_service import AdminDivisionImportService
from app.models.admin_division import AdminDivision
from app.core.database import async_session_maker
```

**Step 3: 提交**

```bash
git add backend/app/api/admin.py
git commit -m "feat(api): add admin division import endpoints"
```

---

## Task 6: 前端管理界面

**Files:**
- Modify: `frontend/src/views/Admin.vue`
- Modify: `frontend/src/api/admin.ts`

**Step 1: 添加 API 函数**

在 `frontend/src/api/admin.ts` 中添加：

```typescript
// 行政区划导入相关
export interface DivisionStatus {
  total_count: number
  provinces_count: number
  cities_count: number
  areas_count: number
  provinces: Array<{ code: string; name: string }>
}

export interface ImportProgress {
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  message: string
  stats?: {
    provinces: number
    cities: number
    areas: number
  }
}

export const getDivisionStatus = () => {
  return request.get<DivisionStatus>('/admin/admin-divisions/status')
}

export const importDivisionsOnline = (params: {
  province_codes?: string[]
  force?: boolean
}) => {
  return request.post<{ task_id: string }>('/admin/admin-divisions/import/online', null, { params })
}

export const importDivisionsUpload = (file: File, force: boolean = false) => {
  const formData = new FormData()
  formData.append('file', file)
  return request.post<{ task_id: string }>(`/admin/admin-divisions/import/upload?force=${force}`, formData)
}

export const getImportProgress = (taskId: string) => {
  return request.get<ImportProgress>(`/admin/admin-divisions/import/progress/${taskId}`)
}
```

**Step 2: 在 Admin.vue 中添加行政区划管理区块**

在模板中适当位置添加：

```vue
<!-- 行政区划数据管理 -->
<el-card class="config-card">
  <template #header>
    <span>行政区划数据管理</span>
  </template>

  <!-- 当前状态 -->
  <div class="division-status" v-if="divisionStatus">
    <el-descriptions :column="isMobile ? 1 : 4" border size="small">
      <el-descriptions-item label="总数">{{ divisionStatus.total_count }}</el-descriptions-item>
      <el-descriptions-item label="省级">{{ divisionStatus.provinces_count }}</el-descriptions-item>
      <el-descriptions-item label="市级">{{ divisionStatus.cities_count }}</el-descriptions-item>
      <el-descriptions-item label="区县级">{{ divisionStatus.areas_count }}</el-descriptions-item>
    </el-descriptions>
  </div>

  <!-- 导入按钮 -->
  <div class="division-actions">
    <el-button type="primary" @click="startOnlineImport" :loading="importLoading">
      <el-icon><Download /></el-icon>
      在线更新
    </el-button>
    <el-upload
      :show-file-list="false"
      :before-upload="handleUploadBefore"
      accept=".zip"
    >
      <el-button type="default" :loading="importLoading">
        <el-icon><Upload /></el-icon>
        上传压缩包
      </el-button>
    </el-upload>
  </div>

  <!-- 高级选项 -->
  <el-collapse v-model="divisionAdvancedOpen">
    <el-collapse-item title="高级选项" name="advanced">
      <el-form label-width="120px" size="small">
        <el-form-item label="更新范围">
          <el-radio-group v-model="importMode">
            <el-radio value="full">全量更新（推荐）</el-radio>
            <el-radio value="province">按省份更新</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item v-if="importMode === 'province'" label="选择省份">
          <el-select v-model="selectedProvinces" multiple placeholder="选择省份" style="width: 100%">
            <el-option
              v-for="p in divisionStatus?.provinces || []"
              :key="p.code"
              :label="p.name"
              :value="p.code"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="强制覆盖">
          <el-switch v-model="importForce" />
          <span class="form-hint">删除现有数据后重新导入</span>
        </el-form-item>
      </el-form>
    </el-collapse-item>
  </el-collapse>

  <!-- 进度条 -->
  <div class="import-progress" v-if="importTaskId">
    <el-progress
      :percentage="importProgress?.progress || 0"
      :status="importProgress?.status === 'failed' ? 'exception' : importProgress?.status === 'completed' ? 'success' : ''"
    />
    <div class="progress-message">{{ importProgress?.message }}</div>
  </div>
</el-card>
```

**Step 3: 添加相关逻辑**

在 `<script setup>` 中添加：

```typescript
import { ref, onMounted } from 'vue'
import { Download, Upload } from '@element-plus/icons-vue'
import {
  getDivisionStatus,
  importDivisionsOnline,
  importDivisionsUpload,
  getImportProgress,
  type DivisionStatus,
  type ImportProgress
} from '@/api/admin'

// 行政区划相关状态
const divisionStatus = ref<DivisionStatus | null>(null)
const divisionAdvancedOpen = ref<string[]>([])
const importMode = ref<'full' | 'province'>('full')
const selectedProvinces = ref<string[]>([])
const importForce = ref(false)
const importLoading = ref(false)
const importTaskId = ref<string | null>(null)
const importProgress = ref<ImportProgress | null>(null)

// 获取行政区划状态
const loadDivisionStatus = async () => {
  try {
    const res = await getDivisionStatus()
    divisionStatus.value = res.data
  } catch (e) {
    console.error('获取行政区划状态失败', e)
  }
}

// 在线导入
const startOnlineImport = async () => {
  importLoading.value = true
  try {
    const params: any = { force: importForce.value }
    if (importMode.value === 'province' && selectedProvinces.value.length > 0) {
      params.province_codes = selectedProvinces.value
    }

    const res = await importDivisionsOnline(params)
    importTaskId.value = res.data.task_id
    pollImportProgress()
  } catch (e: any) {
    ElMessage.error(e.message || '启动导入失败')
    importLoading.value = false
  }
}

// 上传压缩包
const handleUploadBefore = async (file: File) => {
  importLoading.value = true
  try {
    const res = await importDivisionsUpload(file, importForce.value)
    importTaskId.value = res.data.task_id
    pollImportProgress()
  } catch (e: any) {
    ElMessage.error(e.message || '上传失败')
    importLoading.value = false
  }
  return false // 阻止默认上传
}

// 轮询进度
const pollImportProgress = async () => {
  if (!importTaskId.value) return

  try {
    const res = await getImportProgress(importTaskId.value)
    importProgress.value = res.data

    if (res.data.status === 'completed') {
      ElMessage.success('导入完成')
      importLoading.value = false
      importTaskId.value = null
      loadDivisionStatus()
    } else if (res.data.status === 'failed') {
      ElMessage.error(res.data.message || '导入失败')
      importLoading.value = false
      importTaskId.value = null
    } else {
      // 继续轮询
      setTimeout(pollImportProgress, 1000)
    }
  } catch (e) {
    console.error('获取进度失败', e)
    importLoading.value = false
  }
}

onMounted(() => {
  loadDivisionStatus()
})
```

**Step 4: 添加样式**

```css
.division-status {
  margin-bottom: 16px;
}

.division-actions {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.import-progress {
  margin-top: 16px;
}

.progress-message {
  margin-top: 8px;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

.form-hint {
  margin-left: 8px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
```

**Step 5: 提交**

```bash
git add frontend/src/api/admin.ts
git add frontend/src/views/Admin.vue
git commit -m "feat(ui): add admin division import UI in Admin.vue"
```

---

## Task 7: 测试与验证

**Step 1: 运行后端测试（如有）**

```bash
cd backend
conda activate vibe_route
pytest tests/ -v --tb=short
```

**Step 2: 启动后端服务验证**

```bash
cd backend
uvicorn app.main:app --reload
```

访问 `http://localhost:8000/docs` 验证新 API 端点存在。

**Step 3: 启动前端验证**

```bash
cd frontend
npm run dev
```

访问管理界面，验证行政区划管理区块显示正常。

**Step 4: 功能测试**

1. 点击"在线更新"，观察进度条
2. 上传测试压缩包，验证导入
3. 检查数据库中导入的数据

**Step 5: 提交测试通过**

```bash
git add .
git commit -m "test: verify admin division import functionality"
```

---

## Task 8: 清理与文档

**Step 1: 标记废弃方法**

在 `admin_division_import_service.py` 中，为旧方法添加 deprecation 警告：

```python
import warnings

async def import_from_sqlite(self, ...):
    """
    从 area_code.sqlite 导入行政区划数据

    .. deprecated::
        使用 import_from_datav_online 或 import_from_geojson_archive 代替
    """
    warnings.warn(
        "import_from_sqlite is deprecated, use import_from_datav_online instead",
        DeprecationWarning,
        stacklevel=2
    )
    # ... 原有代码
```

**Step 2: 更新 CLAUDE.md**

在 CLAUDE.md 中添加关于行政区划导入的说明。

**Step 3: 最终提交**

```bash
git add .
git commit -m "docs: mark deprecated methods and update documentation"
```

---

## 完成检查清单

- [ ] 数据库迁移脚本（3个版本）
- [ ] DataVGeoService 类
- [ ] AdminDivisionImportService 重构
- [ ] API 端点
- [ ] 前端界面
- [ ] 功能测试
- [ ] 文档更新
