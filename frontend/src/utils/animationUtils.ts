// frontend/src/utils/animationUtils.ts

import type { TrackPoint } from '@/types/track'
import type { MarkerPosition } from '@/types/animation'

/**
 * 计算轨迹持续时间（毫秒）
 */
export function calculateDuration(points: TrackPoint[]): number {
  if (points.length === 0) return 0

  // 找到第一个和最后一个有效的时间点
  const firstPoint = points.find(p => p.time)
  const lastPoint = [...points].reverse().find(p => p.time)

  if (!firstPoint?.time || !lastPoint?.time) {
    // 如果没有时间数据，返回 0
    return 0
  }

  return new Date(lastPoint.time).getTime() - new Date(firstPoint.time).getTime()
}

/**
 * 根据当前时间查找对应的轨迹点索引和插值进度
 * @param time - 当前播放时间（毫秒）
 * @param points - 轨迹点数组
 * @param startTime - 轨迹开始时间（ISO 字符串）
 * @returns 索引和进度 { index: number, progress: number }
 */
export function findPointIndexByTime(
  time: number,
  points: TrackPoint[],
  startTime: string
): { index: number; progress: number } {
  if (points.length === 0) return { index: 0, progress: 0 }
  if (points.length === 1) return { index: 0, progress: 0 }

  const startTimeMs = new Date(startTime).getTime()
  const elapsed = time - startTimeMs

  // 找到第一个有效时间点
  const firstValidIndex = points.findIndex(p => p.time)
  if (firstValidIndex === -1) {
    // 没有时间数据，使用线性索引
    const totalPoints = points.length
    const rawIndex = (elapsed / 1000) * 10 // 假设每秒 10 个点
    return {
      index: Math.min(Math.floor(rawIndex), totalPoints - 1),
      progress: rawIndex % 1,
    }
  }

  // 二分查找
  let left = firstValidIndex
  let right = points.length - 1

  while (left < right) {
    const mid = Math.floor((left + right) / 2)
    const midPoint = points[mid]
    if (!midPoint?.time) {
      // 跳过无效时间点
      left = mid + 1
      continue
    }
    const midTime = new Date(midPoint.time).getTime() - startTimeMs
    if (midTime < elapsed) {
      left = mid + 1
    } else {
      right = mid
    }
  }

  const index = Math.max(0, left - 1)
  const point = points[index]
  const nextPoint = points[index + 1]

  if (!point?.time || !nextPoint?.time) {
    return { index, progress: 0 }
  }

  const pointTime = new Date(point.time).getTime() - startTimeMs
  const nextPointTime = new Date(nextPoint.time).getTime() - startTimeMs
  const segmentDuration = nextPointTime - pointTime

  if (segmentDuration <= 0) {
    return { index, progress: 0 }
  }

  const progress = Math.min(1, Math.max(0, (elapsed - pointTime) / segmentDuration))

  return { index, progress }
}

/**
 * 在两个轨迹点之间进行线性插值
 */
export function interpolatePosition(
  point1: TrackPoint,
  point2: TrackPoint,
  progress: number,
  useGCJ02 = false,
  useBD09 = false
): MarkerPosition {
  // 根据地图提供商选择正确的坐标系
  const lat1 = useGCJ02 ? (point1.latitude_gcj02 ?? point1.latitude_wgs84 ?? point1.latitude)
    : useBD09 ? (point1.latitude_bd09 ?? point1.latitude_wgs84 ?? point1.latitude)
    : (point1.latitude_wgs84 ?? point1.latitude)

  const lng1 = useGCJ02 ? (point1.longitude_gcj02 ?? point1.longitude_wgs84 ?? point1.longitude)
    : useBD09 ? (point1.longitude_bd09 ?? point1.longitude_wgs84 ?? point1.longitude)
    : (point1.longitude_wgs84 ?? point1.longitude)

  const lat2 = useGCJ02 ? (point2.latitude_gcj02 ?? point2.latitude_wgs84 ?? point2.latitude)
    : useBD09 ? (point2.latitude_bd09 ?? point2.latitude_wgs84 ?? point2.latitude)
    : (point2.latitude_wgs84 ?? point2.latitude)

  const lng2 = useGCJ02 ? (point2.longitude_gcj02 ?? point2.longitude_wgs84 ?? point2.longitude)
    : useBD09 ? (point2.longitude_bd09 ?? point2.longitude_wgs84 ?? point2.longitude)
    : (point2.longitude_wgs84 ?? point2.longitude)

  const lat = lat1 + (lat2 - lat1) * progress
  const lng = lng1 + (lng2 - lng1) * progress

  // 方位角插值（处理 350° -> 10° 的情况）
  const bearing1 = point1.bearing ?? 0
  const bearing2 = point2.bearing ?? bearing1
  let bearing = bearing1 + (bearing2 - bearing1) * progress

  // 归一化到 [0, 360)
  if (bearing < 0) bearing += 360
  if (bearing >= 360) bearing -= 360

  // 速度插值
  const speed1 = point1.speed ?? 0
  const speed2 = point2.speed ?? 0
  const speed = speed1 + (speed2 - speed1) * progress

  // 海拔插值
  const elevation1 = point1.elevation ?? 0
  const elevation2 = point2.elevation ?? 0
  const elevation = elevation1 + (elevation2 - elevation1) * progress

  // 时间插值
  let time: string | null = null
  if (point1.time && point2.time) {
    const t1 = new Date(point1.time).getTime()
    const t2 = new Date(point2.time).getTime()
    const t = t1 + (t2 - t1) * progress
    time = new Date(t).toISOString()
  }

  return { lat, lng, bearing, speed, elevation, time }
}

/**
 * 计算最短旋转路径的角度差（处理 350° -> 10° 的情况）
 * @param from - 起始角度
 * @param to - 目标角度
 * @returns 角度差，范围 (-180, 180]
 */
export function calculateShortestRotation(from: number, to: number): number {
  let delta = to - from
  while (delta > 180) delta -= 360
  while (delta < -180) delta += 360
  return delta
}

/**
 * 归一化角度到 [0, 360)
 */
export function normalizeAngle(angle: number): number {
  let normalized = angle % 360
  if (normalized < 0) normalized += 360
  return normalized
}

/**
 * 格式化时间显示（毫秒转 HH:MM:SS）
 */
export function formatAnimationTime(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60

  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`
}

/**
 * 根据点数量和倍速计算采样步长
 */
export function getSampleStep(pointCount: number, speed: number): number {
  if (pointCount < 500) return 1
  if (speed >= 8) return 4
  if (speed >= 4) return 2
  if (pointCount < 2000) return 1
  return 2
}

/**
 * 检查轨迹是否有足够的数据用于动画播放
 */
export function canPlayAnimation(points: TrackPoint[]): { canPlay: boolean; reason?: string } {
  if (points.length === 0) {
    return { canPlay: false, reason: '无轨迹数据' }
  }
  if (points.length === 1) {
    return { canPlay: false, reason: '轨迹点不足' }
  }
  return { canPlay: true }
}

/**
 * 计算两个点之间的距离（米，使用 Haversine 公式）
 */
export function calculateDistance(
  lat1: number,
  lng1: number,
  lat2: number,
  lng2: number
): number {
  const R = 6371000 // 地球半径（米）
  const φ1 = (lat1 * Math.PI) / 180
  const φ2 = (lat2 * Math.PI) / 180
  const Δφ = ((lat2 - lat1) * Math.PI) / 180
  const Δλ = ((lng2 - lng1) * Math.PI) / 180

  const a =
    Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
    Math.cos(φ1) * Math.cos(φ2) * Math.sin(Δλ / 2) * Math.sin(Δλ / 2)
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))

  return R * c
}
