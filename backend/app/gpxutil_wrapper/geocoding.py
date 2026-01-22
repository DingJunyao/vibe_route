"""
地理编码服务集成
支持 Nominatim、高德地图、百度地图
"""
import time
import asyncio
from typing import Optional, Literal, Any
import httpx

from app.gpxutil_wrapper.coord_transform import convert_point, CoordinateType

GeocodingProvider = Literal['nominatim', 'amap', 'baidu']


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
                    details_response = await client.get(f"{self.url}/details", params={'place_id': place_id}, headers=headers)
                    details = details_response.json()
                    if 'names' in details and 'ref' in details['names']:
                        result['road_num'] = ','.join(details['names']['ref'].split(';'))

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
            # 百度使用 BD09 坐标系，需要转换
            bd_lon, bd_lat = convert_point(lon, lat, 'wgs84', 'bd09')

            # 限流
            if self.freq > 0:
                await asyncio.sleep(1 / self.freq)

            async with httpx.AsyncClient(timeout=10.0) as client:
                # 中文请求
                params = {
                    'coordtype': 'bd09ll',
                    'output': 'json',
                    'ak': self.api_key,
                    'location': f'{bd_lat},{bd_lon}',
                    'extensions_poi': 0,
                    'language_code': 'zh-CN',
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

                    # 获取道路编号
                    if address.get('street_number'):
                        result['road_num'] = address['street_number']

                    # 如果启用了英文结果，再请求一次英文版本
                    if self.get_en_result:
                        params['language_code'] = 'en'
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
                else:
                    result['memo'] = resp.get('message', 'Unknown error')

        except Exception as e:
            result['memo'] = str(e)

        return result


def create_geocoding_service(provider: str, config: dict) -> GeocodingService:
    """创建地理编码服务实例"""
    services: dict[str, type[GeocodingService]] = {
        'nominatim': NominatimGeocoding,
        'amap': AmapGeocoding,
        'baidu': BaiduGeocoding,
    }

    provider = provider.lower()
    if provider not in services:
        raise ValueError(f"Unsupported geocoding provider: {provider}")

    return services[provider](config)
