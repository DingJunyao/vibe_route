"""
坐标转换模块
支持 WGS84、GCJ02、BD09 三种坐标系之间的转换
"""
import math
from typing import Tuple, Literal

CoordinateType = Literal['wgs84', 'gcj02', 'bd09']


# 定义常量
pi = 3.1415926535897932384626
a = 6378245.0  # 长半轴
ee = 0.00669342162296594323  # 扁率


def out_of_china(lng: float, lat: float) -> bool:
    """
    判断是否在国内，不在国内则不做偏移
    """
    if lng < 72.004 or lng > 137.8347:
        return True
    if lat < 0.8293 or lat > 55.8271:
        return True
    return False


def _transform_lat(lng: float, lat: float) -> float:
    """纬度转换"""
    ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + \
          0.1 * lng * lat + 0.2 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * pi) + 20.0 *
            math.sin(2.0 * lng * pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * pi) + 40.0 *
            math.sin(lat / 3.0 * pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * pi) + 320 *
            math.sin(lat * pi / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(lng: float, lat: float) -> float:
    """经度转换"""
    ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + \
          0.1 * lng * lat + 0.1 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * pi) + 20.0 *
            math.sin(2.0 * lng * pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lng * pi) + 40.0 *
            math.sin(lng / 3.0 * pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(lng / 12.0 * pi) + 300.0 *
            math.sin(lng / 30.0 * pi)) * 2.0 / 3.0
    return ret


def wgs84_to_gcj02(lng: float, lat: float) -> Tuple[float, float]:
    """
    WGS84 转 GCJ02 (火星坐标系)
    """
    if out_of_china(lng, lat):
        return lng, lat

    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * pi)
    dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * pi)
    mglat = lat + dlat
    mglng = lng + dlng
    return mglng, mglat


def gcj02_to_wgs84(lng: float, lat: float) -> Tuple[float, float]:
    """
    GCJ02 转 WGS84
    """
    if out_of_china(lng, lat):
        return lng, lat

    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * pi)
    dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * pi)
    mglat = lat + dlat
    mglng = lng + dlng
    return lng * 2 - mglng, lat * 2 - mglat


def gcj02_to_bd09(lng: float, lat: float) -> Tuple[float, float]:
    """
    GCJ02 转 BD09 (百度坐标系)
    """
    z = math.sqrt(lng * lng + lat * lat) + 0.00002 * math.sin(lat * pi * 3000.0 / 180.0)
    theta = math.atan2(lat, lng) + 0.000003 * math.cos(lng * pi * 3000.0 / 180.0)
    bd_lng = z * math.cos(theta) + 0.0065
    bd_lat = z * math.sin(theta) + 0.006
    return bd_lng, bd_lat


def bd09_to_gcj02(lng: float, lat: float) -> Tuple[float, float]:
    """
    BD09 转 GCJ02
    """
    x = lng - 0.0065
    y = lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * pi * 3000.0 / 180.0)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * pi * 3000.0 / 180.0)
    gcj_lng = z * math.cos(theta)
    gcj_lat = z * math.sin(theta)
    return gcj_lng, gcj_lat


def wgs84_to_bd09(lng: float, lat: float) -> Tuple[float, float]:
    """
    WGS84 转 BD09
    """
    gcj_lng, gcj_lat = wgs84_to_gcj02(lng, lat)
    return gcj02_to_bd09(gcj_lng, gcj_lat)


def bd09_to_wgs84(lng: float, lat: float) -> Tuple[float, float]:
    """
    BD09 转 WGS84
    """
    gcj_lng, gcj_lat = bd09_to_gcj02(lng, lat)
    return gcj02_to_wgs84(gcj_lng, gcj_lat)


def convert_point(
    lng: float,
    lat: float,
    from_crs: CoordinateType,
    to_crs: CoordinateType
) -> Tuple[float, float]:
    """
    坐标转换

    Args:
        lng: 经度
        lat: 纬度
        from_crs: 原始坐标系
        to_crs: 目标坐标系

    Returns:
        (经度, 纬度)
    """
    if from_crs == to_crs:
        return lng, lat

    # WGS84 -> GCJ02
    if from_crs == 'wgs84' and to_crs == 'gcj02':
        return wgs84_to_gcj02(lng, lat)

    # WGS84 -> BD09
    if from_crs == 'wgs84' and to_crs == 'bd09':
        return wgs84_to_bd09(lng, lat)

    # GCJ02 -> WGS84
    if from_crs == 'gcj02' and to_crs == 'wgs84':
        return gcj02_to_wgs84(lng, lat)

    # GCJ02 -> BD09
    if from_crs == 'gcj02' and to_crs == 'bd09':
        return gcj02_to_bd09(lng, lat)

    # BD09 -> WGS84
    if from_crs == 'bd09' and to_crs == 'wgs84':
        return bd09_to_wgs84(lng, lat)

    # BD09 -> GCJ02
    if from_crs == 'bd09' and to_crs == 'gcj02':
        return bd09_to_gcj02(lng, lat)

    raise ValueError(f"Unsupported coordinate conversion: {from_crs} -> {to_crs}")


def convert_point_to_all(
    lng: float,
    lat: float,
    original_crs: CoordinateType
) -> dict[CoordinateType, Tuple[float, float]]:
    """
    将一个点转换为所有坐标系

    Args:
        lng: 经度
        lat: 纬度
        original_crs: 原始坐标系

    Returns:
        包含所有坐标系的字典
    """
    result = {}

    if original_crs == 'wgs84':
        result['wgs84'] = (lng, lat)
        result['gcj02'] = wgs84_to_gcj02(lng, lat)
        result['bd09'] = wgs84_to_bd09(lng, lat)
    elif original_crs == 'gcj02':
        result['wgs84'] = gcj02_to_wgs84(lng, lat)
        result['gcj02'] = (lng, lat)
        result['bd09'] = gcj02_to_bd09(lng, lat)
    elif original_crs == 'bd09':
        result['wgs84'] = bd09_to_wgs84(lng, lat)
        result['gcj02'] = bd09_to_gcj02(lng, lat)
        result['bd09'] = (lng, lat)
    else:
        raise ValueError(f"Unsupported coordinate system: {original_crs}")

    return result
