/**
 * 坐标转换工具
 * 支持 WGS84、GCJ02、BD09 三种坐标系之间的转换
 */

// 定义常量
const pi = Math.PI
const a = 6378245.0 // 长半轴
const ee = 0.00669342162296594323 // 扁率

/**
 * 判断是否在国内，不在国内则不做偏移
 */
function outOfChina(lng: number, lat: number): boolean {
  if (lng < 72.004 || lng > 137.8347) return true
  if (lat < 0.8293 || lat > 55.8271) return true
  return false
}

/**
 * 坐标是否在中国境内（BD09/GCJ02 偏移加密的有效范围，粗判矩形）。
 * 百度海外底图按 WGS84 对齐，境外点显示时应直接使用 WGS84
 */
export function isInChina(lng: number, lat: number): boolean {
  return !outOfChina(lng, lat)
}

/**
 * 判断一组点是否属于中国境内（采样多数判定）。
 * 用于选择百度底图坐标口径：逐点判断会让跨界轨迹在边界处出现偏移量级的跳变，
 * 按轨迹整体口径处理（轨迹几乎总是整体位于一侧）
 */
export function isChinaRegionPoints(
  points: Array<{ latitude_wgs84?: number | null; longitude_wgs84?: number | null; latitude?: number; longitude?: number }>,
  sample = 20
): boolean {
  let checked = 0
  let inChina = 0
  const step = Math.max(1, Math.floor(points.length / sample))
  for (let i = 0; i < points.length; i += step) {
    const p = points[i]
    const lng = p.longitude_wgs84 ?? p.longitude
    const lat = p.latitude_wgs84 ?? p.latitude
    if (typeof lng === 'number' && typeof lat === 'number' && !isNaN(lng) && !isNaN(lat)) {
      checked++
      if (isInChina(lng, lat)) inChina++
    }
  }
  return checked > 0 && inChina * 2 >= checked
}

/**
 * 纬度转换
 */
function transformLat(lng: number, lat: number): number {
  let ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat +
    0.1 * lng * lat + 0.2 * Math.sqrt(Math.abs(lng))
  ret += (20.0 * Math.sin(6.0 * lng * pi) + 20.0 *
    Math.sin(2.0 * lng * pi)) * 2.0 / 3.0
  ret += (20.0 * Math.sin(lat * pi) + 40.0 *
    Math.sin(lat / 3.0 * pi)) * 2.0 / 3.0
  ret += (160.0 * Math.sin(lat / 12.0 * pi) + 320 *
    Math.sin(lat * pi / 30.0)) * 2.0 / 3.0
  return ret
}

/**
 * 经度转换
 */
function transformLng(lng: number, lat: number): number {
  let ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng +
    0.1 * lng * lat + 0.1 * Math.sqrt(Math.abs(lng))
  ret += (20.0 * Math.sin(6.0 * lng * pi) + 20.0 *
    Math.sin(2.0 * lng * pi)) * 2.0 / 3.0
  ret += (20.0 * Math.sin(lng * pi) + 40.0 *
    Math.sin(lng / 3.0 * pi)) * 2.0 / 3.0
  ret += (150.0 * Math.sin(lng / 12.0 * pi) + 300.0 *
    Math.sin(lng / 30.0 * pi)) * 2.0 / 3.0
  return ret
}

/**
 * WGS84 转 GCJ02 (火星坐标系)
 */
export function wgs84ToGcj02(lng: number, lat: number): [number, number] {
  if (outOfChina(lng, lat)) {
    return [lng, lat]
  }

  let dLat = transformLat(lng - 105.0, lat - 35.0)
  let dLng = transformLng(lng - 105.0, lat - 35.0)
  const radLat = lat / 180.0 * pi
  let magic = Math.sin(radLat)
  magic = 1 - ee * magic * magic
  const sqrtMagic = Math.sqrt(magic)
  dLat = (dLat * 180.0) / ((a * (1 - ee)) / (magic * sqrtMagic) * pi)
  dLng = (dLng * 180.0) / (a / sqrtMagic * Math.cos(radLat) * pi)
  const mgLat = lat + dLat
  const mgLng = lng + dLng
  return [mgLng, mgLat]
}

/**
 * GCJ02 转 WGS84
 */
export function gcj02ToWgs84(lng: number, lat: number): [number, number] {
  if (outOfChina(lng, lat)) {
    return [lng, lat]
  }

  let dLat = transformLat(lng - 105.0, lat - 35.0)
  let dLng = transformLng(lng - 105.0, lat - 35.0)
  const radLat = lat / 180.0 * pi
  let magic = Math.sin(radLat)
  magic = 1 - ee * magic * magic
  const sqrtMagic = Math.sqrt(magic)
  dLat = (dLat * 180.0) / ((a * (1 - ee)) / (magic * sqrtMagic) * pi)
  dLng = (dLng * 180.0) / (a / sqrtMagic * Math.cos(radLat) * pi)
  const mgLat = lat + dLat
  const mgLng = lng + dLng
  return [lng * 2 - mgLng, lat * 2 - mgLat]
}

/**
 * GCJ02 转 BD09 (百度坐标系)
 * 境外原样返回：BD09 偏移加密只在中国境内有意义，百度海外底图按 WGS84 对齐，
 * 对境外点套用偏移会带来约 1km 的显示偏移
 */
export function gcj02ToBd09(lng: number, lat: number): [number, number] {
  if (outOfChina(lng, lat)) return [lng, lat]
  const z = Math.sqrt(lng * lng + lat * lat) + 0.00002 * Math.sin(lat * pi * 3000.0 / 180.0)
  const theta = Math.atan2(lat, lng) + 0.000003 * Math.cos(lng * pi * 3000.0 / 180.0)
  const bdLng = z * Math.cos(theta) + 0.0065
  const bdLat = z * Math.sin(theta) + 0.006
  return [bdLng, bdLat]
}

/**
 * BD09 转 GCJ02
 * 境外原样返回（与 gcj02ToBd09 的守卫对称：境外不存在真正的 BD09 坐标）
 */
export function bd09ToGcj02(lng: number, lat: number): [number, number] {
  if (outOfChina(lng, lat)) return [lng, lat]
  const x = lng - 0.0065
  const y = lat - 0.006
  const z = Math.sqrt(x * x + y * y) - 0.00002 * Math.sin(y * pi * 3000.0 / 180.0)
  const theta = Math.atan2(y, x) - 0.000003 * Math.cos(x * pi * 3000.0 / 180.0)
  const gcjLng = z * Math.cos(theta)
  const gcjLat = z * Math.sin(theta)
  return [gcjLng, gcjLat]
}

/**
 * WGS84 转 BD09
 */
export function wgs84ToBd09(lng: number, lat: number): [number, number] {
  const [gcjLng, gcjLat] = wgs84ToGcj02(lng, lat)
  return gcj02ToBd09(gcjLng, gcjLat)
}

/**
 * BD09 转 WGS84
 */
export function bd09ToWgs84(lng: number, lat: number): [number, number] {
  const [gcjLng, gcjLat] = bd09ToGcj02(lng, lat)
  return gcj02ToWgs84(gcjLng, gcjLat)
}

export type CRSType = 'wgs84' | 'gcj02' | 'bd09'

/**
 * 坐标转换
 * @param lng 经度
 * @param lat 纬度
 * @param from 原始坐标系
 * @param to 目标坐标系
 * @returns [经度, 纬度]
 */
export function convertCoord(
  lng: number,
  lat: number,
  from: CRSType,
  to: CRSType
): [number, number] {
  if (from === to) return [lng, lat]

  switch (from) {
    case 'wgs84':
      switch (to) {
        case 'gcj02':
          return wgs84ToGcj02(lng, lat)
        case 'bd09':
          return wgs84ToBd09(lng, lat)
      }
      break
    case 'gcj02':
      switch (to) {
        case 'wgs84':
          return gcj02ToWgs84(lng, lat)
        case 'bd09':
          return gcj02ToBd09(lng, lat)
      }
      break
    case 'bd09':
      switch (to) {
        case 'wgs84':
          return bd09ToWgs84(lng, lat)
        case 'gcj02':
          return bd09ToGcj02(lng, lat)
      }
      break
  }
  return [lng, lat]
}
