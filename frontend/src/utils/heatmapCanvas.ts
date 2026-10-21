/**
 * Canvas 热力渲染
 *
 * 所有 SDK 引擎（高德/百度/腾讯/Google）共用同一套渲染与归一化，保证：
 * - 任意缩放级别都能展开完整色带（不是一片饱和色）
 * - 不同引擎观感一致
 *
 * 做法：把屏幕坐标点按 radius/2 的网格聚合，用聚合值的 98 分位作为归一化上限，
 * 每格只画一个热力圆（权重和决定透明度）。
 */

interface HeatPoint {
  x: number
  y: number
  weight: number
}

export interface HeatCanvasOptions {
  radius?: number
  blur?: number
  /** 手动指定归一化上限；缺省用聚合值的 98 分位 */
  max?: number
  minOpacity?: number
  /** 整体不透明度 0-1（在算出颜色后统一乘到 alpha 上） */
  opacity?: number
  gradient?: Record<string, string>
}

const DEFAULT_GRADIENT: Record<string, string> = {
  0.2: '#8fc0dd',
  0.4: '#7cc6b8',
  0.6: '#c3d78f',
  0.75: '#ecd393',
  0.9: '#e9ab84',
  1.0: '#cd8f8f',
}

// 归一化上限 = 98 分位 × 该系数。
// 1.0 时热区顶到色带末端（与 leaflet.heat 观感接近）；系数过大整体会发灰。
const SATURATION_FACTOR = 1.2

// 圆点模板缓存（按 radius/blur 复用，避免每次重绘重建阴影圆）
const circleCache = new Map<string, HTMLCanvasElement>()

function getCircle(radius: number, blur: number): HTMLCanvasElement {
  const key = `${radius}:${blur}`
  const cached = circleCache.get(key)
  if (cached) return cached

  const r = radius + blur
  const circle = document.createElement('canvas')
  circle.width = circle.height = r * 2
  const ctx = circle.getContext('2d')!
  ctx.shadowOffsetX = ctx.shadowOffsetY = 2000
  ctx.shadowBlur = blur
  ctx.shadowColor = 'black'
  ctx.beginPath()
  ctx.arc(r - 2000, r - 2000, radius, 0, Math.PI * 2, true)
  ctx.closePath()
  ctx.fill()

  circleCache.set(key, circle)
  return circle
}

// 渐变查找表（256 级）
function buildGradientLut(gradient: Record<string, string>): Uint8ClampedArray {
  const canvas = document.createElement('canvas')
  canvas.width = 1
  canvas.height = 256
  const ctx = canvas.getContext('2d')!
  const grad = ctx.createLinearGradient(0, 0, 0, 256)
  for (const [stop, color] of Object.entries(gradient)) {
    grad.addColorStop(parseFloat(stop), color)
  }
  ctx.fillStyle = grad
  ctx.fillRect(0, 0, 1, 256)
  return ctx.getImageData(0, 0, 1, 256).data
}

function percentile(sorted: number[], p: number): number {
  if (sorted.length === 0) return 1
  return sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * p))] || 1
}

/**
 * 在 canvas 上绘制热力点（坐标单位为 canvas 像素）
 */
export function renderHeatCanvas(
  canvas: HTMLCanvasElement,
  points: HeatPoint[],
  options: HeatCanvasOptions = {},
): void {
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const radius = options.radius ?? 22
  const blur = options.blur ?? 16
  const minOpacity = options.minOpacity ?? 0.08
  const opacity = options.opacity ?? 1
  const gradient = options.gradient ?? DEFAULT_GRADIENT

  const { width, height } = canvas
  if (width === 0 || height === 0) return

  ctx.clearRect(0, 0, width, height)
  if (points.length === 0) return

  // 1) 屏幕网格聚合：cell = radius/2，记录权重和与加权中心
  const cell = Math.max(2, Math.round(radius / 2))
  const cells = new Map<string, { x: number; y: number; w: number }>()
  for (const p of points) {
    if (p.x < -cell || p.x > width + cell || p.y < -cell || p.y > height + cell) continue
    const key = `${Math.floor(p.x / cell)}:${Math.floor(p.y / cell)}`
    const c = cells.get(key)
    if (c) {
      c.x += p.x * p.weight
      c.y += p.y * p.weight
      c.w += p.weight
    } else {
      cells.set(key, { x: p.x * p.weight, y: p.y * p.weight, w: p.weight })
    }
  }
  if (cells.size === 0) return

  const aggregated: Array<{ x: number; y: number; w: number }> = []
  const sums: number[] = []
  for (const c of cells.values()) {
    aggregated.push({ x: c.x / c.w, y: c.y / c.w, w: c.w })
    sums.push(c.w)
  }
  sums.sort((a, b) => a - b)

  // 2) 归一化上限：默认取 98 分位（保证绝大多数格子处于色带中低段）
  const max = Math.max(1, options.max ?? percentile(sums, 0.98) * SATURATION_FACTOR)

  // 3) 每格一个热力圆，透明度按聚合权重
  const circle = getCircle(radius, blur)
  const r = radius + blur
  for (const c of aggregated) {
    ctx.globalAlpha = Math.max(c.w / max, minOpacity)
    ctx.drawImage(circle, c.x - r, c.y - r)
  }
  ctx.globalAlpha = 1

  // 4) 灰度强度 → 色带，并乘整体不透明度
  const lut = buildGradientLut(gradient)
  const image = ctx.getImageData(0, 0, width, height)
  const data = image.data
  for (let i = 3; i < data.length; i += 4) {
    const intensity = data[i]
    if (intensity === 0) continue
    const idx = intensity * 4
    data[i - 3] = lut[idx]
    data[i - 2] = lut[idx + 1]
    data[i - 1] = lut[idx + 2]
    if (opacity < 1) {
      data[i] = Math.round(intensity * opacity)
    }
  }
  ctx.putImageData(image, 0, 0)
}

/**
 * 拖动跟随：热力画布按屏幕坐标绘制，地图平移时用 CSS translate 跟随，
 * 避免每帧重投影全部点（4 万点在低端设备上会明显掉帧）。
 * 松手（moveend）后由调用方重绘并清除 transform 校准。
 */
export interface HeatFollowState {
  lng: number
  lat: number
  startX: number
  startY: number
  dx: number
  dy: number
}

export function createHeatFollow(lng: number, lat: number, x: number, y: number): HeatFollowState {
  return { lng, lat, startX: x, startY: y, dx: 0, dy: 0 }
}

/** 按锚点当前像素位置平移画布（无变化时不写样式） */
export function applyHeatFollow(
  state: HeatFollowState,
  canvas: HTMLCanvasElement,
  x: number,
  y: number,
): void {
  const dx = Math.round(x - state.startX)
  const dy = Math.round(y - state.startY)
  if (dx === state.dx && dy === state.dy) return
  state.dx = dx
  state.dy = dy
  canvas.style.transform = dx === 0 && dy === 0 ? '' : `translate(${dx}px, ${dy}px)`
}

/** 清除跟随位移（重绘前调用） */
export function clearHeatTransform(canvas: HTMLCanvasElement | null): void {
  if (canvas) canvas.style.transform = ''
}
