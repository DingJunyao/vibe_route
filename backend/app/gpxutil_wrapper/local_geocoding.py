"""
本地地理编码服务

使用本地存储的行政区划数据进行反向地理编码。
支持边界框查询和 PostGIS 空间查询。
"""
from typing import Any, Optional
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, text

from app.gpxutil_wrapper.geocoding import GeocodingService
from app.models.admin_division import AdminDivision
from app.core.database import async_session_maker
from app.core.config import settings
from loguru import logger

# 添加 GDF 专用日志文件
gdf_logger = logger.bind(service="gdf")
_log_path = Path(settings.LOG_DIR) / "gdf_query.log"
_log_path.parent.mkdir(parents=True, exist_ok=True)
logger.add(
    _log_path,
    rotation="10 MB",
    retention="7 days",
    filter=lambda record: record["extra"].get("service") == "gdf",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {message}",
    level="DEBUG"
)


class LocalGeocodingService(GeocodingService):
    """
    本地地理编码服务

    使用数据库存储的行政区划数据进行反向地理编码。
    支持省/市/区三级查询，不包含街道级别和道路信息。
    """

    def __init__(self, config: dict):
        super().__init__(config)
        # 使用 spatial_backend 配置（向后兼容旧的 query_mode 参数）
        spatial_backend = config.get("spatial_backend", config.get("query_mode", "auto"))
        self._database_type = getattr(settings, 'DATABASE_TYPE', 'sqlite')
        self._spatial_backend = spatial_backend

        # 根据 spatial_backend 设置是否使用 PostGIS
        if spatial_backend == "auto":
            self.use_postgis = (self._database_type == "postgresql")
        elif spatial_backend == "postgis":
            self.use_postgis = True
        else:  # spatial_backend == "python"
            self.use_postgis = False

        # PostGIS 可用性缓存（None 表示未检测）
        self._postgis_available: Optional[bool] = None

        gdf_logger.info(f"GDF 初始化: database={self._database_type}, spatial_backend={spatial_backend}, use_postgis={self.use_postgis}")

    async def _check_postgis_available(self, db) -> bool:
        """
        检测 PostGIS 是否真正可用（有数据）

        检查条件：
        1. PostGIS 扩展已安装
        2. admin_divisions_spatial 表存在且有数据

        如果不可用，会自动回退到边界框查询。
        """
        if self._postgis_available is not None:
            return self._postgis_available

        try:
            # 检查 PostGIS 扩展
            result = await db.execute(
                text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'postgis')")
            )
            if not result.scalar_one():
                gdf_logger.info("PostGIS 扩展未安装，回退到边界框查询")
                self._postgis_available = False
                return False

            # 检查空间表是否有数据
            result = await db.execute(
                text("SELECT EXISTS(SELECT 1 FROM admin_divisions_spatial LIMIT 1)")
            )
            has_data = result.scalar_one()

            if not has_data:
                gdf_logger.info("PostGIS 空间表无数据，回退到边界框查询")
                self._postgis_available = False
                return False

            self._postgis_available = True
            return True

        except Exception as e:
            gdf_logger.warning(f"PostGIS 可用性检测失败: {e}，回退到边界框查询")
            self._postgis_available = False
            return False

    async def get_point_info(self, lat: float, lon: float) -> dict[str, Any]:
        """
        获取点的地理信息

        Args:
            lat: 纬度
            lon: 经度

        Returns:
            dict: 地理信息
        """
        result = {
            'province': '',
            'city': '',
            'area': '',
            'town': '',
            'road_name': '',
            'road_num': '',
            'province_en': '',
            'city_en': '',
            'area_en': '',
            'town_en': '',
            'road_name_en': '',
            'memo': ''
        }

        try:
            async with async_session_maker() as db:
                # 检测是否应该使用 PostGIS
                use_postgis_query = self.use_postgis and await self._check_postgis_available(db)

                if use_postgis_query:
                    gdf_logger.debug(f"使用 PostGIS 查询: ({lat}, {lon})")
                    divisions = await self._query_with_postgis(db, lat, lon)
                else:
                    gdf_logger.debug(f"使用边界框查询: ({lat}, {lon})")
                    divisions = await self._query_with_bounds(db, lat, lon)

                if not divisions:
                    result['memo'] = 'Location not found in admin divisions'
                    return result

                # 构建层级结果
                await self._build_hierarchy(db, result, divisions, lat, lon)

        except Exception as e:
            result['memo'] = str(e)
            gdf_logger.error(f"本地地理编码错误: {e}")

        return result

    async def _query_with_postgis(
        self,
        db: AsyncSession,
        lat: float,
        lon: float
    ) -> list[AdminDivision]:
        """
        使用 PostGIS 进行空间查询

        使用 ST_Within 判断点是否在多边形内。
        """
        try:
            sql = text("""
                SELECT d.id, d.code, d.name, d.name_en, d.level, d.parent_code,
                       d.province_code, d.city_code
                FROM admin_divisions d
                INNER JOIN admin_divisions_spatial s ON d.id = s.division_id
                WHERE ST_Within(
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                    s.geom
                )
                AND d.is_valid = TRUE
            """)

            result = await db.execute(sql, {"lat": lat, "lon": lon})
            rows = result.fetchall()

            # 转换为 AdminDivision 对象
            divisions = []
            for row in rows:
                div = AdminDivision()
                div.id = row[0]
                div.code = row[1]
                div.name = row[2]
                div.name_en = row[3]
                div.level = row[4]
                div.parent_code = row[5]
                div.province_code = row[6]
                div.city_code = row[7]
                divisions.append(div)
                gdf_logger.debug(f"PostGIS 查询结果: {div.name}({div.level}), "
                           f"code={div.code}, city_code={div.city_code}, province_code={div.province_code}")

            return divisions

        except Exception as e:
            gdf_logger.warning(f"PostGIS 查询失败，回退到边界框查询: {e}")
            # 回滚事务以清除错误状态
            await db.rollback()
            return await self._query_with_bounds(db, lat, lon)

    async def _query_with_bounds(
        self,
        db: AsyncSession,
        lat: float,
        lon: float
    ) -> list[AdminDivision]:
        """
        使用边界框进行查询

        先用边界框快速过滤，然后使用射线法判断点是否在多边形内。
        """
        gdf_logger.debug(f"边界框查询: ({lat}, {lon})")

        # 将坐标转换为整数（* 1e6）
        lat_scaled = int(lat * 1e6)
        lon_scaled = int(lon * 1e6)

        # 边界框过滤
        result = await db.execute(
            select(AdminDivision).where(
                and_(
                    AdminDivision.min_lat <= lat_scaled,
                    AdminDivision.max_lat >= lat_scaled,
                    AdminDivision.min_lon <= lon_scaled,
                    AdminDivision.max_lon >= lon_scaled,
                    AdminDivision.is_valid == True
                )
            )
        )

        divisions = list(result.scalars().all())

        if divisions:
            levels_found = [d.level for d in divisions]
            names_found = [d.name for d in divisions]
            gdf_logger.debug(f"边界框查询结果: 层级={levels_found}, 名称={names_found}, 总数={len(divisions)}")
        else:
            gdf_logger.debug(f"边界框查询结果: 无匹配")

        # TODO: 可以添加射线法进一步精确判断
        # 目前边界框对于区县级别的精度已经足够

        return divisions

    async def _build_hierarchy(self, db: AsyncSession, result: dict, divisions: list[AdminDivision], lat: float, lon: float):
        """
        从行政区划列表构建层级结果

        处理特殊情况：
        1. 直辖市：区级的 city_code 和 province_code 相同
        2. 不设区县的地级市：如中山市、东莞市，查询返回 city 级别但无 area
        3. 省辖县级行政单位：如济源市、仙桃市，区级的 parent_code 直接指向省

        Args:
            db: 数据库会话
            result: 结果字典
            divisions: 行政区划列表
            lat: 查询点纬度
            lon: 查询点经度
        """
        # 日志：返回的层级
        levels_found = [d.level for d in divisions]
        gdf_logger.debug(f"查询到的层级: {levels_found}, 总数: {len(divisions)}")

        # 按代码创建字典
        div_dict = {d.code: d for d in divisions}

        # 直辖市代码列表
        MUNICIPALITY_CODES = {
            '11': '北京市',
            '12': '天津市',
            '31': '上海市',
            '50': '重庆市',
        }

        # 不设区的地级市（硬编码列表）
        CITIES_WITHOUT_DISTRICTS = {"441900", "442000", "460400", "620200"}

        # 中心距离计算函数
        def center_distance(div: AdminDivision, query_lat: float, query_lon: float) -> float:
            if div.min_lat is None or div.max_lat is None or div.min_lon is None or div.max_lon is None:
                return float('inf')
            # 计算中心点（边界框中心）
            center_lat = (div.min_lat + div.max_lat) / 2 / 1e6  # 转换回原始坐标
            center_lon = (div.min_lon + div.max_lon) / 2 / 1e6
            # 计算距离（简单的欧氏距离，对于小范围足够）
            return ((query_lat - center_lat) ** 2 + (query_lon - center_lon) ** 2) ** 0.5

        # 获取 city 和 area 级别记录
        city_divs = [d for d in divisions if d.level == "city"]
        area_divs = [d for d in divisions if d.level == "area"]

        # ========== 优先检查不设区地级市 ==========
        # 如果查询结果包含不设区地级市，且它比所有 area 都更近，则优先使用
        special_cities = [d for d in city_divs if d.code in CITIES_WITHOUT_DISTRICTS]
        if special_cities:
            # 计算每个特殊城市的距离
            special_cities.sort(key=lambda d: center_distance(d, lat, lon))
            closest_special_city = special_cities[0]
            special_city_dist = center_distance(closest_special_city, lat, lon)

            # 如果有 area，比较距离
            if area_divs:
                area_divs_sorted = sorted(area_divs, key=lambda d: center_distance(d, lat, lon))
                closest_area_dist = center_distance(area_divs_sorted[0], lat, lon)

                gdf_logger.debug(f"不设区地级市距离比较: {closest_special_city.name}={special_city_dist:.6f} vs "
                               f"最近区县 {area_divs_sorted[0].name}={closest_area_dist:.6f}")

                # 如果不设区地级市更近，直接使用它
                if special_city_dist < closest_area_dist:
                    gdf_logger.debug(f"选择不设区地级市: {closest_special_city.name}")
                    result['city'] = closest_special_city.name
                    if closest_special_city.name_en:
                        result['city_en'] = closest_special_city.name_en
                    result['area'] = ''
                    result['area_en'] = ''

                    # 填充省级
                    if closest_special_city.province_code:
                        province = div_dict.get(closest_special_city.province_code)
                        if not province:
                            province_result = await db.execute(
                                select(AdminDivision).where(AdminDivision.code == closest_special_city.province_code)
                            )
                            province = province_result.scalar_one_or_none()
                        if province:
                            result['province'] = province.name
                            if province.name_en:
                                result['province_en'] = province.name_en

                    gdf_logger.debug(f"构建结果: province={result.get('province')}, city={result.get('city')}, area={result.get('area')}")
                    return  # 提前返回，不再处理 area
            else:
                # 没有 area，直接使用不设区地级市
                gdf_logger.debug(f"无 area，选择不设区地级市: {closest_special_city.name}")
                result['city'] = closest_special_city.name
                if closest_special_city.name_en:
                    result['city_en'] = closest_special_city.name_en
                result['area'] = ''
                result['area_en'] = ''

                # 填充省级
                if closest_special_city.province_code:
                    province = div_dict.get(closest_special_city.province_code)
                    if not province:
                        province_result = await db.execute(
                            select(AdminDivision).where(AdminDivision.code == closest_special_city.province_code)
                        )
                        province = province_result.scalar_one_or_none()
                    if province:
                        result['province'] = province.name
                        if province.name_en:
                            result['province_en'] = province.name_en

                gdf_logger.debug(f"构建结果: province={result.get('province')}, city={result.get('city')}, area={result.get('area')}")
                return  # 提前返回

        # ========== 处理区县级查询（最常见情况）==========
        if area_divs:
            area_divs.sort(key=lambda d: center_distance(d, lat, lon))
            area_div = area_divs[0]

            gdf_logger.debug(f"区县数据: code={area_div.code}, name={area_div.name}, "
                        f"city_code={area_div.city_code}, province_code={area_div.province_code}")

            # 如果有多个区县，记录一下
            if len(area_divs) > 1:
                gdf_logger.debug(f"找到 {len(area_divs)} 个区县，选择距离最近的: {area_div.name}")
                for i, div in enumerate(area_divs[:5]):  # 只记录前5个
                    dist = center_distance(div, lat, lon)
                    gdf_logger.debug(f"  [{i}] {div.name}({div.code}), 距离={dist:.6f}km")

            # 特殊情况：不设区县的地级市（中山、东莞、儋州、嘉峪关等）
            # 数据库中同时存在 city 和 area 两条记录，area 的 city_code 与 code 高位相同
            # 例如：中山市 area code=442000, city_code=4420（前几位相同）
            # 这种情况下应该使用 city 记录作为市名，area 留空
            is_city_without_district = False

            # 查找对应的 city 记录（注意：边界框查询可能不返回 city 记录，因为 city 可能没有边界框数据）
            matching_city = next((d for d in city_divs if d.code == area_div.city_code), None)

            # 如果边界框查询没有返回 city 记录，尝试从数据库查询
            if not matching_city and area_div.city_code:
                city_result = await db.execute(
                    select(AdminDivision).where(AdminDivision.code == area_div.city_code)
                )
                matching_city = city_result.scalar_one_or_none()

            # 判断条件：
            # 1. 必须有 matching_city（防止正常区县被误判）
            # 2. 名称相同或高度相似
            if matching_city:
                # 排除直辖市的虚拟 city_code（如 1101、1201 表示"市辖区"）
                # 直辖市的 city_code 通常以 01 结尾
                is_virtual_municipality_city = (
                    len(area_div.city_code) == 4 and
                    area_div.city_code.endswith('01') and
                    area_div.province_code and
                    len(area_div.province_code) >= 2 and
                    area_div.province_code[:2] in MUNICIPALITY_CODES and
                    area_div.city_code[:2] == area_div.province_code[:2]
                )

                # 排除省直辖县级行政单位（如济源 4190、仙桃 4290 等）
                # 这些 city_code 的第3位通常是 9
                is_province_administered_area = (
                    len(area_div.city_code) == 4 and
                    area_div.city_code[2] == '9'
                )

                if not is_virtual_municipality_city and not is_province_administered_area:
                    if (matching_city.name == area_div.name or
                        matching_city.name[:2] == area_div.name[:2] or  # 前两个字相同
                        area_div.city_code == area_div.code):  # code 完全相同
                        is_city_without_district = True
                        gdf_logger.debug(f"检测到不设区县的地级市: area={area_div.name}({area_div.code}), "
                                       f"city_code={area_div.city_code}, city={matching_city.name}")

            if is_city_without_district:
                # 这是一个不设区县的地级市，area 记录是冗余的
                # 使用对应的 city 记录
                result['city'] = matching_city.name
                if matching_city.name_en:
                    result['city_en'] = matching_city.name_en
                # 明确清空 area 字段，因为不设区县的地级市没有区县级别
                result['area'] = ''
                result['area_en'] = ''
                gdf_logger.debug(f"使用 city 记录: {matching_city.name}，清空 area")
            else:
                # 正常情况：填充区县信息
                result['area'] = area_div.name
                if area_div.name_en:
                    result['area_en'] = area_div.name_en

            # 通过 city_code 查询市级（仅在非不设区县的地级市情况下）
            if not is_city_without_district and area_div.city_code and not result.get('city'):
                city = div_dict.get(area_div.city_code)
                if not city:
                    city_result = await db.execute(
                        select(AdminDivision).where(AdminDivision.code == area_div.city_code)
                    )
                    city = city_result.scalar_one_or_none()
                    if city:
                        gdf_logger.debug(f"从数据库查询市级: code={area_div.city_code}, result={city.name}")
                    else:
                        gdf_logger.debug(f"从数据库查询市级: code={area_div.city_code}, result=None（可能是省辖县级行政单位）")

                # 检查是否是省/自治区直辖县级行政区划
                # 如果 city 名称包含"省直辖"或类似关键词，说明这是虚拟的市级，应该清空
                is_province_administered = False
                if city:
                    # 检查城市名称是否是虚拟的省/自治区直辖分类
                    virtual_city_names = [
                        '省直辖县级行政区划',
                        '省直辖行政单位',
                        '省直管县级行政区划',
                        '自治区直辖县级行政区划',
                        '自治区直辖行政单位',
                        '自治区直管县级行政区划',
                    ]
                    if any(virtual_name in city.name for virtual_name in virtual_city_names):
                        is_province_administered = True
                        gdf_logger.debug(f"检测到省/自治区直辖县级行政区划: city_name={city.name}，清空 city")

                # 只有在非省直辖的情况下才填充 city
                if city and not is_province_administered:
                    result['city'] = city.name
                    if city.name_en:
                        result['city_en'] = city.name_en
                elif is_province_administered:
                    # 省直辖：清空 city
                    result['city'] = ''
                    result['city_en'] = ''

            # 通过 province_code 查询省级
            if area_div.province_code and not result.get('province'):
                province = div_dict.get(area_div.province_code)
                if not province:
                    province_result = await db.execute(
                        select(AdminDivision).where(AdminDivision.code == area_div.province_code)
                    )
                    province = province_result.scalar_one_or_none()
                    gdf_logger.debug(f"从数据库查询省级: code={area_div.province_code}, result={province}")
                if province:
                    result['province'] = province.name
                    if province.name_en:
                        result['province_en'] = province.name_en

            # 处理直辖市：检查 province_code 前两位是否是直辖市代码
            # 直辖市的区县级记录，其 city_code 指向的是"市辖区"这个虚拟市级
            # 对于直辖市，我们应该清空 city，只保留 province 和 area
            is_municipality = (
                area_div.province_code and
                len(area_div.province_code) >= 2 and
                area_div.province_code[:2] in MUNICIPALITY_CODES
            )

            if is_municipality:
                # 直辖市：清空 city 字段
                result['city'] = ''
                result['city_en'] = ''
                gdf_logger.debug(f"检测到直辖市: province_code={area_div.province_code}，清空 city")

        # 处理市级查询（不设区县的地级市）
        # 当只查询到 city 级别时（无 area），填充 city 和 province
        if city_divs and not area_divs:
            # 不设区地级市硬编码列表
            CITIES_WITHOUT_DISTRICTS = {"441900", "442000", "460400", "620200"}

            # 如果有多个 city，计算中心距离选择最近的
            def city_center_distance(div: AdminDivision, query_lat: float, query_lon: float) -> float:
                if div.min_lat is None or div.max_lat is None or div.min_lon is None or div.max_lon is None:
                    return float('inf')
                center_lat = (div.min_lat + div.max_lat) / 2 / 1e6
                center_lon = (div.min_lon + div.max_lon) / 2 / 1e6
                return ((query_lat - center_lat) ** 2 + (query_lon - center_lon) ** 2) ** 0.5

            city_divs.sort(key=lambda d: city_center_distance(d, lat, lon))
            city_div = city_divs[0]

            gdf_logger.debug(f"仅查询到 city 级别: code={city_div.code}, name={city_div.name}, "
                           f"province_code={city_div.province_code}")

            # 检查是否是不设区地级市
            if city_div.code in CITIES_WITHOUT_DISTRICTS:
                # 不设区地级市：填充 city，清空 area
                result['city'] = city_div.name
                if city_div.name_en:
                    result['city_en'] = city_div.name_en
                result['area'] = ''
                result['area_en'] = ''
                gdf_logger.debug(f"检测到不设区地级市: {city_div.name}({city_div.code})")
            else:
                # 其他情况：可能是边界框查询不精确，暂时填充 city
                result['city'] = city_div.name
                if city_div.name_en:
                    result['city_en'] = city_div.name_en
                gdf_logger.debug(f"填充 city: {city_div.name}({city_div.code})")

            # 通过 province_code 查询省级
            if city_div.province_code and not result.get('province'):
                province = div_dict.get(city_div.province_code)
                if not province:
                    province_result = await db.execute(
                        select(AdminDivision).where(AdminDivision.code == city_div.province_code)
                    )
                    province = province_result.scalar_one_or_none()
                if province:
                    result['province'] = province.name
                    if province.name_en:
                        result['province_en'] = province.name_en

        gdf_logger.debug(f"构建结果: province={result.get('province')}, city={result.get('city')}, area={result.get('area')}")
