// frontend/src/utils/animation/cameraSmoothing.ts
// 相机平滑与航向平滑（回放/导出相机专用）。
//
// 数学移植自 amap_remotion（TRACK-REPLAY-NOTES.md 第三节的实测结论）：
// - 相机位置：±1.5s 滑动平均（7 采样），抑制 GPS 停车抖动（不平滑镜头会画圈）；
//   画线仍用原始插值点，只有相机用平滑点。
// - 航向：窗口测向（±2.5/5/10/20s，位移不足逐级放宽）→ ±1s 圆周平滑
//   （circular mean，不能算术平均——359° 和 1° 的平均是 0° 不是 180°）；
//   窗口位移 < MIN_DISP_M 视为静止 → 保持航向，并向前找未来运动方向
//   （起步航向 = 即将行驶的方向），找不到再向后找。
//
// 仅相机与固定中心标记使用平滑结果；轨迹线、信息面板、移动端 HUD 均使用
// 原始插值位置。轨迹无有效时间数据时返回 null，调用方回退原始位置/方位角。

import type { TrackPoint } from '@/api/track'

/** 动画使用的坐标系（与 interpolatePosition 的 useGCJ02/useBD09 参数对应） */
export type AnimationCRS = 'gcj02' | 'bd09' | 'wgs84'

interface PreparedTrack {
  times: number[]   // 绝对时间戳（ms），严格递增
  lats: number[]
  lngs: number[]
}

const POSITION_HALF_MS = 1500  // 相机位置平滑半窗宽
const HEADING_SMOOTH_OFFSETS = [-1000, -500, 0, 500, 1000]  // 航向圆周平滑采样
const WINDOWS_MS = [2500, 5000, 10000, 20000]  // 测向窗口，位移不足逐级放宽
const MIN_DISP_M = 6           // 窗口内位移小于该值视为静止
const STATIC_SEARCH_MAX_MS = 240000  // 静止时向前/向后找运动方向的范围（4 分钟）
const STATIC_SEARCH_STEP_MS = 1000
const STATIC_PROBE_MS = 4000   // 静止方向探测的位移窗口

// (points 数组, CRS) → 预处理结果；null（无有效时间数据）也缓存避免反复重建
const preparedCache = new WeakMap<TrackPoint[], Map<string, PreparedTrack | null>>()

function pointCoords(p: TrackPoint, crs: AnimationCRS): [number, number] {
  if (crs === 'bd09' && p.latitude_bd09 != null && p.longitude_bd09 != null) {
    return [p.longitude_bd09, p.latitude_bd09]
  }
  if (crs === 'gcj02' && p.latitude_gcj02 != null && p.longitude_gcj02 != null) {
    return [p.longitude_gcj02, p.latitude_gcj02]
  }
  if (p.latitude_wgs84 != null && p.longitude_wgs84 != null) {
    return [p.longitude_wgs84, p.latitude_wgs84]
  }
  return [p.longitude, p.latitude]
}

function buildPrepared(points: TrackPoint[], crs: AnimationCRS): PreparedTrack | null {
  const times: number[] = []
  const lats: number[] = []
  const lngs: number[] = []
  for (const p of points) {
    if (!p.time) continue
    const t = Date.parse(p.time)
    if (!Number.isFinite(t)) continue
    // 重复/倒退的时间点直接丢弃，否则插值除零（amap_remotion 踩过的坑）
    if (times.length > 0 && t <= times[times.length - 1]) continue
    const [lng, lat] = pointCoords(p, crs)
    times.push(t)
    lats.push(lat)
    lngs.push(lng)
  }
  if (times.length < 2) return null
  return { times, lats, lngs }
}

function getPrepared(points: TrackPoint[], crs: AnimationCRS): PreparedTrack | null {
  let byCrs = preparedCache.get(points)
  if (!byCrs) {
    byCrs = new Map()
    preparedCache.set(points, byCrs)
  }
  const key = crs
  if (!byCrs.has(key)) {
    byCrs.set(key, buildPrepared(points, crs))
  }
  return byCrs.get(key) ?? null
}

/** 时间插值出的原始位置（超出范围取端点） */
function positionAt(prepared: PreparedTrack, tMs: number): { lat: number; lng: number } {
  const { times, lats, lngs } = prepared
  const n = times.length
  if (tMs <= times[0]) return { lat: lats[0], lng: lngs[0] }
  if (tMs >= times[n - 1]) return { lat: lats[n - 1], lng: lngs[n - 1] }
  let lo = 0
  let hi = n - 1
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1
    if (times[mid] <= tMs) lo = mid
    else hi = mid
  }
  const f = (tMs - times[lo]) / (times[hi] - times[lo])
  return { lat: lats[lo] + (lats[hi] - lats[lo]) * f, lng: lngs[lo] + (lngs[hi] - lngs[lo]) * f }
}

/** 两点间的平面近似位移（米，东向/北向分量；窗口内位移小，近似足够） */
function metersDelta(a: { lat: number; lng: number }, b: { lat: number; lng: number }): [number, number] {
  const midLatRad = (((a.lat + b.lat) / 2) * Math.PI) / 180
  const dNorth = (b.lat - a.lat) * 111320
  const dEast = (b.lng - a.lng) * 111320 * Math.cos(midLatRad)
  return [dEast, dNorth]
}

function bearingDeg(dEast: number, dNorth: number): number {
  const deg = (Math.atan2(dEast, dNorth) * 180) / Math.PI  // 0=北，顺时针
  return (deg + 360) % 360
}

function windowBearing(prepared: PreparedTrack, tMs: number, windowMs: number): number | null {
  const a = positionAt(prepared, tMs - windowMs)
  const b = positionAt(prepared, tMs + windowMs)
  const [dEast, dNorth] = metersDelta(a, b)
  if (Math.hypot(dEast, dNorth) < MIN_DISP_M) return null
  return bearingDeg(dEast, dNorth)
}

function headingRaw(prepared: PreparedTrack, tMs: number): number | null {
  for (const w of WINDOWS_MS) {
    const h = windowBearing(prepared, tMs, w)
    if (h !== null) return h
  }
  return null
}

function circularMean(degs: number[]): number {
  let sx = 0
  let sy = 0
  for (const d of degs) {
    const r = (d * Math.PI) / 180
    sx += Math.cos(r)
    sy += Math.sin(r)
  }
  return (((Math.atan2(sy, sx) * 180) / Math.PI) + 360) % 360
}

/**
 * 相机位置：原始插值位置的 ±1.5s 滑动平均（7 采样）。
 * 无有效时间数据时返回 null。
 */
export function smoothedCameraAt(
  tMs: number,
  points: TrackPoint[],
  crs: AnimationCRS
): { lat: number; lng: number } | null {
  const prepared = getPrepared(points, crs)
  if (!prepared) return null
  let sx = 0
  let sy = 0
  for (let i = -3; i <= 3; i++) {
    const p = positionAt(prepared, tMs + (i / 3) * POSITION_HALF_MS)
    sx += p.lng
    sy += p.lat
  }
  return { lat: sy / 7, lng: sx / 7 }
}

/**
 * 行进方向（度，0=正北，顺时针）：窗口测向 + 圆周平滑；
 * 静止时向前（最多 4 分钟）找即将出发的方向，找不到再向后找；
 * 前后 4 分钟均静止时返回 null（调用方保持上次航向）。
 * 航向只依赖几何方向，坐标系换算（GCJ02/BD09）局部线性不影响角度，统一按 WGS84 缓存。
 * 无有效时间数据时返回 null。
 */
export function cameraHeadingAt(tMs: number, points: TrackPoint[]): number | null {
  const prepared = getPrepared(points, 'wgs84')
  if (!prepared) return null
  const h = headingRaw(prepared, tMs)
  if (h !== null) {
    const samples: number[] = []
    for (const dt of HEADING_SMOOTH_OFFSETS) {
      samples.push(headingRaw(prepared, tMs + dt) ?? h)
    }
    return circularMean(samples)
  }
  // 静止：向前找即将出发的方向（起步航向 = 即将行驶的方向），否则向后
  for (let dt = STATIC_SEARCH_STEP_MS; dt <= STATIC_SEARCH_MAX_MS; dt += STATIC_SEARCH_STEP_MS) {
    const a = positionAt(prepared, tMs + dt)
    const b = positionAt(prepared, tMs + dt + STATIC_PROBE_MS)
    const [dEast, dNorth] = metersDelta(a, b)
    if (Math.hypot(dEast, dNorth) >= MIN_DISP_M) {
      return bearingDeg(dEast, dNorth)
    }
  }
  for (let dt = STATIC_SEARCH_STEP_MS; dt <= STATIC_SEARCH_MAX_MS; dt += STATIC_SEARCH_STEP_MS) {
    const a = positionAt(prepared, tMs - dt - STATIC_PROBE_MS)
    const b = positionAt(prepared, tMs - dt)
    const [dEast, dNorth] = metersDelta(a, b)
    if (Math.hypot(dEast, dNorth) >= MIN_DISP_M) {
      return bearingDeg(dEast, dNorth)
    }
  }
  return null
}
