"""
地理编码服务集成
支持 Nominatim、高德地图、百度地图
"""
import time
import asyncio
from typing import Optional, Literal, Any
import httpx

from app.gpxutil_wrapper.coord_transform import convert_point, CoordinateType

GeocodingProvider = Literal['nominatim', 'gdf', 'amap', 'baidu']


# 省份名称到简称的映射（用于自动为省级高速添加省份前缀）
PROVINCE_NAME_TO_SHORT = {
    '北京市': '京', '天津市': '津', '河北省': '冀', '山西省': '晋',
    '内蒙古自治区': '蒙', '辽宁省': '辽', '吉林省': '吉', '黑龙江省': '黑',
    '上海市': '沪', '江苏省': '苏', '浙江省': '浙', '安徽省': '皖',
    '福建省': '闽', '江西省': '赣', '山东省': '鲁', '河南省': '豫',
    '湖北省': '鄂', '湖南省': '湘', '广东省': '粤', '广西壮族自治区': '桂',
    '海南省': '琼', '重庆市': '渝', '四川省': '川', '贵州省': '贵',
    '云南省': '云', '西藏自治区': '藏', '陕西省': '陕', '甘肃省': '甘',
    '青海省': '青', '宁夏回族自治区': '宁', '新疆维吾尔自治区': '新',
    # 台湾、香港、澳门暂不处理
}

# 省份英文名到简称的映射
PROVINCE_EN_TO_SHORT = {
    'Beijing': '京', 'Tianjin': '津', 'Hebei': '冀', 'Shanxi': '晋',
    'Inner Mongolia': '蒙', 'Liaoning': '辽', 'Jilin': '吉', 'Heilongjiang': '黑',
    'Shanghai': '沪', 'Jiangsu': '苏', 'Zhejiang': '浙', 'Anhui': '皖',
    'Fujian': '闽', 'Jiangxi': '赣', 'Shandong': '鲁', 'Henan': '豫',
    'Hubei': '鄂', 'Hunan': '湘', 'Guangdong': '粤', 'Guangxi': '桂',
    'Hainan': '琼', 'Chongqing': '渝', 'Sichuan': '川', 'Guizhou': '贵',
    'Yunnan': '云', 'Tibet': '藏', 'Shaanxi': '陕', 'Gansu': '甘',
    'Qinghai': '青', 'Ningxia': '宁', 'Xinjiang': '新',
}


class GeocodingService:
    """地理编码服务基类"""

    def __init__(self, config: dict):
        self.config = config

    async def get_point_info(self, lat: float, lon: float) -> dict[str, Any]:
        """获取点的地理信息"""
        raise NotImplementedError


class NominatimGeocoding(GeocodingService):
    """Nominatim 地理编码服务（自建）"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.url = config.get('url', 'http://localhost:8080')

    async def get_point_info(self, lat: float, lon: float) -> dict[str, Any]:
        """获取点的地理信息"""
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
            async with httpx.AsyncClient(timeout=10.0) as client:
                # 中文请求
                params = {
                    'lat': lat,
                    'lon': lon,
                    'format': 'geocodejson',
                    'layer': 'address',
                    'extratags': 1,
                    'zoom': 17,
                    'accept-language': 'zh-CN'
                }

                response = await client.get(f"{self.url}/reverse", params=params)
                rev = response.json()

                # 英文请求
                params['accept-language'] = 'en'
                response_en = await client.get(f"{self.url}/reverse", params=params)
                rev_en = response_en.json()

                if 'features' not in rev or not rev['features']:
                    result['memo'] = 'No results found'
                    return result

                admin_dict = rev['features'][0]['properties']['geocoding']['admin']
                admin_dict_en = rev_en['features'][0]['properties']['geocoding']['admin']

                result['province'] = admin_dict.get('level4', '')
                result['city'] = admin_dict.get('level5', '')
                result['area'] = admin_dict.get('level6', '')
                result['town'] = admin_dict.get('level8', '')
                result['province_en'] = admin_dict_en.get('level4', '')
                result['city_en'] = admin_dict_en.get('level5', '')
                result['area_en'] = admin_dict_en.get('level6', '')
                result['town_en'] = admin_dict_en.get('level8', '')

                # 获取道路信息
                if rev['features'][0]['properties']['geocoding']['osm_type'] == 'way':
                    result['road_name'] = rev['features'][0]['properties']['geocoding']['name']
                    result['road_name_en'] = rev_en['features'][0]['properties']['geocoding']['name']
                    if result['road_name_en'] == result['road_name']:
                        result['road_name_en'] = ''

                    # 获取道路编号
                    place_id = rev['features'][0]['properties']['geocoding']['place_id']
                    details_response = await client.get(f"{self.url}/details", params={'place_id': place_id})
                    details = details_response.json()
                    if 'names' in details and 'ref' in details['names']:
                        road_nums = details['names']['ref'].split(';')
                        # 为省级高速添加省份前缀（如果还没有前缀）
                        processed_nums = []
                        for num in road_nums:
                            num = num.strip().upper()
                            # 判断是否是省级高速（S开头 + 1-4位数字）
                            if num.startswith('S') and len(num) >= 2 and num[1:].isdigit():
                                # 检查是否已经有省份前缀
                                has_province_prefix = any(
                                    num.startswith(prefix)
                                    for prefix in PROVINCE_NAME_TO_SHORT.values()
                                )
                                if not has_province_prefix:
                                    # 尝试从省份信息中获取简称
                                    province_short = None
                                    if result['province']:
                                        province_short = PROVINCE_NAME_TO_SHORT.get(result['province'])
                                    elif result['province_en']:
                                        province_short = PROVINCE_EN_TO_SHORT.get(result['province_en'])
                                    if province_short:
                                        num = f"{province_short}{num}"
                            processed_nums.append(num)
                        result['road_num'] = ','.join(processed_nums)

        except Exception as e:
            result['memo'] = str(e)

        return result


class AmapGeocoding(GeocodingService):
    """高德地图地理编码服务"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.api_key = config.get('api_key', '')
        self.freq = config.get('freq', 3)  # 默认每秒 3 次请求

    async def get_point_info(self, lat: float, lon: float) -> dict[str, Any]:
        """获取点的地理信息"""
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

        if not self.api_key:
            result['memo'] = 'API key not configured'
            return result

        try:
            # 高德使用 GCJ02 坐标系，需要转换
            gcj_lon, gcj_lat = convert_point(lon, lat, 'wgs84', 'gcj02')

            # 限流
            if self.freq > 0:
                await asyncio.sleep(1 / self.freq)

            async with httpx.AsyncClient(timeout=10.0) as client:
                params = {
                    'key': self.api_key,
                    'location': f'{gcj_lon},{gcj_lat}',
                    'poitype': 180000,
                    'radius': 500,
                    'extensions': 'all',
                }

                response = await client.get(
                    'https://restapi.amap.com/v3/geocode/regeo',
                    params=params
                )
                resp = response.json()

                if resp.get('status') == '1' and resp.get('infocode') == '10000':
                    address = resp['regeocode']['addressComponent']
                    result['province'] = address.get('province', '')
                    result['city'] = address.get('city', '')
                    result['area'] = address.get('district', '')
                    result['town'] = address.get('township', '')

                    # 获取道路名称
                    if 'streetNumber' in address and address['streetNumber']:
                        street = address['streetNumber'].get('street', '')
                        if isinstance(street, list):
                            result['road_name'] = ','.join(street)
                        else:
                            result['road_name'] = street

                    # 如果没有获取到道路名称，尝试从最近的道路获取
                    if not result['road_name'] and 'roads' in resp['regeocode']:
                        roads = resp['regeocode']['roads']
                        if roads:
                            min_distance = min(r['distance'] for r in roads)
                            nearest_roads = [r for r in roads if r['distance'] == min_distance]
                            result['road_name'] = ', '.join(
                                [r['name'] for r in nearest_roads if r.get('name')]
                            )
                else:
                    result['memo'] = resp.get('info', 'Unknown error')

        except Exception as e:
            result['memo'] = str(e)

        return result


class BaiduGeocoding(GeocodingService):
    """百度地图地理编码服务"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.api_key = config.get('api_key', '')
        self.freq = config.get('freq', 3)  # 默认每秒 3 次请求
        self.get_en_result = config.get('get_en_result', False)

    async def get_point_info(self, lat: float, lon: float) -> dict[str, Any]:
        """获取点的地理信息"""
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

        if not self.api_key:
            result['memo'] = 'API key not configured'
            return result

        try:

            # 限流
            if self.freq > 0:
                await asyncio.sleep(1 / self.freq)

            async with httpx.AsyncClient(timeout=10.0) as client:
                # 中文请求
                params = {
                    'coordtype': 'wgs84ll',
                    'output': 'json',
                    'ak': self.api_key,
                    'location': f'{lat},{lon}',
                    'extensions_poi': 0,
                    'poi_types': '道路',
                    'language': 'zh-CN',
                }

                response = await client.get(
                    'https://api.map.baidu.com/reverse_geocoding/v3/',
                    params=params
                )
                resp = response.json()

                if resp.get('status') == 0:
                    address = resp.get('result', {}).get('addressComponent', {})
                    result['province'] = address.get('province', '')
                    result['city'] = address.get('city', '')
                    result['area'] = address.get('district', '')
                    result['town'] = address.get('town', '')
                    result['road_name'] = address.get('street', '')
                    
                    if address.get('street', '') == '':
                        roads = resp.get('result', {}).get('business_info', [])
                        if roads:
                            min_distance = min(roads, key=lambda x: x['distance'])['distance']
                            nearest_roads = [road for road in roads if road['distance'] == min_distance]
                            if nearest_roads:
                                result['road_name'] = ', '.join([road['name'] for road in nearest_roads if road['name']])

                    # 如果启用了英文结果，再请求一次英文版本
                    if self.get_en_result:
                        params['language'] = 'en'

                        # 限流
                        if self.freq > 0:
                            await asyncio.sleep(1 / self.freq)

                        response_en = await client.get(
                            'https://api.map.baidu.com/reverse_geocoding/v3/',
                            params=params
                        )
                        resp_en = response_en.json()

                        if resp_en.get('status') == 0:
                            address_en = resp_en.get('result', {}).get('addressComponent', {})
                            result['province_en'] = address_en.get('province', '')
                            result['city_en'] = address_en.get('city', '')
                            result['area_en'] = address_en.get('district', '')
                            result['town_en'] = address_en.get('town', '')
                            result['road_name_en'] = address_en.get('street', '')
                            if result['road_name_en'] == '':
                                roads = resp_en.get('result', {}).get('business_info', [])
                                if roads:
                                    min_distance = min(roads, key=lambda x: x['distance'])['distance']
                                    nearest_roads = [road for road in roads if road['distance'] == min_distance]
                                    if nearest_roads:
                                        result['road_name_en'] = ', '.join([road['name'] for road in nearest_roads if road['name']])
                            if result['province_en'] ==  result['province']:
                                result['province_en'] = ''
                            if result['city_en'] == result['city']:
                                result['city_en'] = ''
                            if result['area_en'] == result['area']:
                                result['area_en'] = ''
                            if result['town_en'] == result['town']:
                                result['town_en'] = ''
                            if  result['road_name_en'] == result['road_name']:
                                result['road_name_en'] = ''
                else:
                    result['memo'] = resp.get('message', 'Unknown error')

        except Exception as e:
            result['memo'] = str(e)

        return result


def create_geocoding_service(provider: str, config: dict) -> GeocodingService:
    """创建地理编码服务实例"""
    from app.gpxutil_wrapper.local_geocoding import LocalGeocodingService

    services: dict[str, type[GeocodingService]] = {
        'nominatim': NominatimGeocoding,
        'gdf': LocalGeocodingService,
        'amap': AmapGeocoding,
        'baidu': BaiduGeocoding,
    }

    provider = provider.lower()
    if provider not in services:
        raise ValueError(f"Unsupported geocoding provider: {provider}")

    return services[provider](config)
