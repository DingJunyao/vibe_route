"""
阿里 DataV GeoAtlas 数据获取服务

从阿里 DataV 平台获取行政区划 GeoJSON 数据。
API 文档：https://datav.aliyun.com/portal/school/atlas/area_selector

注意：DataV 返回的坐标是 GCJ02 坐标系（火星坐标），存储时需要转换为 WGS84。
"""
import asyncio
from typing import Optional, Callable, List
import httpx
from loguru import logger

from app.gpxutil_wrapper.coord_transform import gcj02_to_wgs84


class DataVGeoService:
    """阿里 DataV GeoAtlas 数据获取服务"""

    BASE_URL = "https://geo.datav.aliyun.com/areas_v3/bound"

    # 直辖市代码
    MUNICIPALITIES = {"110000", "120000", "310000", "500000"}

    # 不设区的地级市（硬编码）
    CITIES_WITHOUT_DISTRICTS = {
        "441900",  # 东莞市
        "442000",  # 中山市
        "460400",  # 儋州市
        "620200",  # 嘉峪关市
    }

    def __init__(self, max_concurrent: int = 10, request_interval: float = 0.1):
        """
        初始化服务

        Args:
            max_concurrent: 最大并发请求数
            request_interval: 请求间隔（秒），避免限流
        """
        self.max_concurrent = max_concurrent
        self.request_interval = request_interval
        self._semaphore: Optional[asyncio.Semaphore] = None

    async def fetch_division(self, adcode: str, full: bool = True) -> Optional[dict]:
        """
        获取单个行政区划的 GeoJSON 数据

        Args:
            adcode: 行政区划代码（如 "100000" 表示全国）
            full: 是否获取包含子级的完整数据（_full.json）

        Returns:
            GeoJSON 数据字典，失败返回 None
        """
        suffix = "_full.json" if full else ".json"
        url = f"{self.BASE_URL}/{adcode}{suffix}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.warning(f"获取行政区划数据失败 [{adcode}]: {e}")
            return None
        except Exception as e:
            logger.error(f"解析行政区划数据失败 [{adcode}]: {e}")
            return None

    async def fetch_province(self, province_code: str) -> List[dict]:
        """
        获取单个省份的所有行政区划数据

        Args:
            province_code: 省级行政区划代码（如 "130000" 表示河北省）

        Returns:
            包含省、市、区县的所有 features 列表
        """
        all_features = []

        # 1. 获取省级数据（包含市级）
        province_data = await self.fetch_division(province_code)
        if not province_data:
            return all_features

        features = province_data.get("features", [])
        all_features.extend(features)

        # 2. 对于每个市级单位，获取其区县
        for feature in features:
            props = feature.get("properties", {})
            adcode = str(props.get("adcode", ""))
            level = props.get("level", "")
            children_num = props.get("childrenNum", 0)

            # 只有市级且有子级的才需要继续获取
            if level == "city" and children_num > 0:
                # 跳过不设区的地级市（它们的子级是镇级）
                if adcode in self.CITIES_WITHOUT_DISTRICTS:
                    continue

                await asyncio.sleep(self.request_interval)
                city_data = await self.fetch_division(adcode)
                if city_data:
                    all_features.extend(city_data.get("features", []))

        return all_features

    async def fetch_all_recursive(
        self,
        start_code: str = "100000",
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> List[dict]:
        """
        递归获取所有行政区划数据

        从全国代码开始，递归获取省、市、区县三级数据。

        Args:
            start_code: 起始代码，默认 "100000"（全国）
            progress_callback: 进度回调函数 callback(message, current, total)

        Returns:
            包含所有行政区划的 features 列表
        """
        all_features = []
        self._semaphore = asyncio.Semaphore(self.max_concurrent)

        # 1. 获取全国数据（包含省级）
        if progress_callback:
            progress_callback("获取全国数据...", 0, 100)

        china_data = await self.fetch_division(start_code)
        if not china_data:
            logger.error("获取全国数据失败")
            return all_features

        provinces = china_data.get("features", [])
        all_features.extend(provinces)
        total_provinces = len(provinces)

        # 2. 并发获取各省数据
        async def fetch_province_with_semaphore(idx: int, province_feature: dict):
            async with self._semaphore:
                props = province_feature.get("properties", {})
                adcode = str(props.get("adcode", ""))
                name = props.get("name", "")

                if progress_callback:
                    progress_callback(f"正在获取 {name}...", idx + 1, total_provinces)

                await asyncio.sleep(self.request_interval)
                province_features = await self.fetch_province(adcode)
                return province_features

        tasks = [
            fetch_province_with_semaphore(i, prov)
            for i, prov in enumerate(provinces)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"获取省份数据时出错: {result}")
                continue
            if result:
                all_features.extend(result)

        if progress_callback:
            progress_callback("完成", total_provinces, total_provinces)

        logger.info(f"共获取 {len(all_features)} 个行政区划")
        return all_features

    async def fetch_provinces_selective(
        self,
        province_codes: List[str],
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> List[dict]:
        """
        选择性获取指定省份的数据

        Args:
            province_codes: 省级代码列表
            progress_callback: 进度回调函数

        Returns:
            包含指定省份所有行政区划的 features 列表
        """
        all_features = []
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        total = len(province_codes)

        async def fetch_with_semaphore(idx: int, code: str):
            async with self._semaphore:
                if progress_callback:
                    progress_callback(f"获取省份 {code}...", idx + 1, total)

                await asyncio.sleep(self.request_interval)

                # 先获取省级本身的信息
                province_data = await self.fetch_division(code, full=False)
                if province_data:
                    all_features.extend(province_data.get("features", []))

                # 再获取子级
                features = await self.fetch_province(code)
                return features

        tasks = [
            fetch_with_semaphore(i, code)
            for i, code in enumerate(province_codes)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"获取数据时出错: {result}")
                continue
            if result:
                all_features.extend(result)

        if progress_callback:
            progress_callback("完成", total, total)

        return all_features

    @staticmethod
    def classify_division(feature: dict) -> tuple[str, Optional[str], str]:
        """
        根据 DataV GeoJSON feature 分类行政区划

        Args:
            feature: GeoJSON feature 对象

        Returns:
            (province_code, city_code, level) 三元组
            - province_code: 省级代码
            - city_code: 市级代码（省辖县级单位为 None）
            - level: 层级（province/city/area）
        """
        props = feature.get("properties", {})
        adcode = str(props.get("adcode", "")).zfill(6)
        level = props.get("level", "")
        parent = props.get("parent", {})
        parent_adcode = str(parent.get("adcode", "")).zfill(6) if parent else None
        children_num = props.get("childrenNum", 0)

        MUNICIPALITIES = {"110000", "120000", "310000", "500000"}
        CITIES_WITHOUT_DISTRICTS = {"441900", "442000", "460400", "620200"}

        if level == "province":
            return (adcode, None, "province")

        elif level == "city":
            if adcode in CITIES_WITHOUT_DISTRICTS:
                # 不设区地级市：省=parent, 市=自己, 存为 city
                return (parent_adcode, adcode, "city")
            elif children_num == 0:
                # 省辖县级行政单位（如济源市）：省=parent, 市=空, 存为 area
                return (parent_adcode, None, "area")
            else:
                # 正常地级市
                return (parent_adcode, adcode, "city")

        elif level == "district":
            if parent_adcode in MUNICIPALITIES:
                # 直辖市区县：省=parent, 市=空
                return (parent_adcode, None, "area")
            else:
                # 普通区县：省=代码前2位+0000, 市=parent
                province_code = adcode[:2] + "0000"
                return (province_code, parent_adcode, "area")

        # 其他情况（如特殊区域）
        return (parent_adcode, None, level)

    @staticmethod
    def extract_center(feature: dict, convert_to_wgs84: bool = True) -> tuple[Optional[float], Optional[float]]:
        """
        从 GeoJSON feature 中提取中心点坐标

        Args:
            feature: GeoJSON feature 对象
            convert_to_wgs84: 是否将 GCJ02 坐标转换为 WGS84（DataV 数据默认需要转换）

        Returns:
            (center_lon, center_lat) 原始浮点坐标，无数据返回 (None, None)
        """
        props = feature.get("properties", {})
        center = props.get("center")

        if center and len(center) == 2:
            try:
                center_lon = float(center[0])
                center_lat = float(center[1])
                if convert_to_wgs84:
                    center_lon, center_lat = gcj02_to_wgs84(center_lon, center_lat)
                return (center_lon, center_lat)
            except (ValueError, TypeError):
                pass

        # 如果没有 center 属性，尝试从 centroid 获取
        centroid = props.get("centroid")
        if centroid and len(centroid) == 2:
            try:
                center_lon = float(centroid[0])
                center_lat = float(centroid[1])
                if convert_to_wgs84:
                    center_lon, center_lat = gcj02_to_wgs84(center_lon, center_lat)
                return (center_lon, center_lat)
            except (ValueError, TypeError):
                pass

        return (None, None)

    @staticmethod
    def convert_geometry_to_wgs84(geometry: dict) -> dict:
        """
        将 GeoJSON 几何从 GCJ02 转换为 WGS84

        支持 Polygon 和 MultiPolygon 类型。

        Args:
            geometry: GeoJSON 几何对象

        Returns:
            转换后的几何对象（深拷贝，不修改原对象）
        """
        import copy

        result = copy.deepcopy(geometry)
        geom_type = result.get("type")

        def convert_ring(ring):
            """转换一个坐标环"""
            return [list(gcj02_to_wgs84(lon, lat)) for lon, lat in ring]

        if geom_type == "Polygon":
            result["coordinates"] = [convert_ring(ring) for ring in result["coordinates"]]
        elif geom_type == "MultiPolygon":
            result["coordinates"] = [
                [convert_ring(ring) for ring in polygon]
                for polygon in result["coordinates"]
            ]

        return result

    @staticmethod
    def extract_bounds(feature: dict, convert_to_wgs84: bool = True) -> tuple[Optional[int], Optional[int], Optional[int], Optional[int]]:
        """
        从 GeoJSON feature 中提取边界框

        Args:
            feature: GeoJSON feature 对象
            convert_to_wgs84: 是否将 GCJ02 坐标转换为 WGS84（DataV 数据默认需要转换）

        Returns:
            (min_lon, min_lat, max_lon, max_lat) 坐标 * 1e6 的整数值
        """
        geometry = feature.get("geometry", {})
        geom_type = geometry.get("type")
        coords = geometry.get("coordinates", [])

        def flatten_coords(data):
            """递归展平坐标数组"""
            if not data:
                return []
            if isinstance(data[0], (int, float)):
                return [data]
            result = []
            for item in data:
                result.extend(flatten_coords(item))
            return result

        if geom_type in ("Polygon", "MultiPolygon"):
            all_coords = flatten_coords(coords)
            if all_coords:
                # 如果需要转换坐标系，逐点转换
                if convert_to_wgs84:
                    converted_coords = []
                    for coord in all_coords:
                        wgs_lon, wgs_lat = gcj02_to_wgs84(coord[0], coord[1])
                        converted_coords.append([wgs_lon, wgs_lat])
                    all_coords = converted_coords

                lons = [c[0] for c in all_coords]
                lats = [c[1] for c in all_coords]
                return (
                    int(min(lons) * 1e6),
                    int(min(lats) * 1e6),
                    int(max(lons) * 1e6),
                    int(max(lats) * 1e6)
                )

        return (None, None, None, None)


# 单例实例
datav_geo_service = DataVGeoService()
