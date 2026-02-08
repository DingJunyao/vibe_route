/**
 * 三次贝塞尔曲线工具类
 * 用于前端轨迹插值预览
 */

/**
 * 坐标点
 */
export interface Point {
  lng: number
  lat: number
}

/**
 * 带手柄的贝塞尔控制点
 */
export interface BezierControlPoint extends Point {
  inHandle: Point
  outHandle: Point
  handlesLocked: boolean
}

/**
 * 计算两点间的球面距离（米）
 * 使用 Haversine 公式
 */
function calculateDistance(p1: Point, p2: Point): number {
  const R = 6371000  // 地球半径（米）
  const φ1 = (p1.lat * Math.PI) / 180
  const φ2 = (p2.lat * Math.PI) / 180
  const Δφ = ((p2.lat - p1.lat) * Math.PI) / 180
  const Δλ = ((p2.lng - p1.lng) * Math.PI) / 180

  const a = Math.sin(Δφ / 2) ** 2 +
            Math.cos(φ1) * Math.cos(φ2) *
            Math.sin(Δλ / 2) ** 2

  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))

  return R * c
}

/**
 * 线性插值
 */
function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t
}

/**
 * 单段三次贝塞尔曲线
 */
class CubicBezierSegment {
  constructor(
    private p0: Point,
    private p1: Point,
    private p2: Point,
    private p3: Point
  ) {}

  /**
   * 计算贝塞尔曲线在参数 t 处的点
   * B(t) = (1-t)³P₀ + 3(1-t)²tP₁ + 3(1-t)t²P₂ + t³P₃
   */
  evaluate(t: number): Point {
    const mt = 1 - t
    const mt2 = mt * mt
    const mt3 = mt2 * mt
    const t2 = t * t
    const t3 = t2 * t

    return {
      lng: mt3 * this.p0.lng + 3 * mt2 * t * this.p1.lng + 3 * mt * t2 * this.p2.lng + t3 * this.p3.lng,
      lat: mt3 * this.p0.lat + 3 * mt2 * t * this.p1.lat + 3 * mt * t2 * this.p2.lat + t3 * this.p3.lat
    }
  }

  /**
   * 计算曲线长度（数值积分）
   */
  calculateLength(steps: number = 20): number {
    let length = 0
    let prev = this.evaluate(0)

    for (let i = 1; i <= steps; i++) {
      const curr = this.evaluate(i / steps)
      length += calculateDistance(prev, curr)
      prev = curr
    }

    return length
  }

  /**
   * 根据弧长获取点（弧长参数化）
   */
  getPointAtLength(targetLength: number, steps: number = 100): Point {
    const totalLength = this.calculateLength(steps)

    if (targetLength <= 0) return this.p0
    if (targetLength >= totalLength) return this.p3

    let accumulated = 0
    let prev = this.evaluate(0)

    for (let i = 1; i <= steps; i++) {
      const t = i / steps
      const curr = this.evaluate(t)
      const segmentLength = calculateDistance(prev, curr)

      if (accumulated + segmentLength >= targetLength) {
        const remaining = targetLength - accumulated
        const localT = segmentLength > 0 ? remaining / segmentLength : 0
        const localTParam = (i - 1 + localT) / steps
        return this.evaluate(localTParam)
      }

      accumulated += segmentLength
      prev = curr
    }

    return this.p3
  }
}

/**
 * 多段三次贝塞尔曲线
 */
export class CubicBezierCurve {
  private segments: CubicBezierSegment[] = []
  private segmentLengths: number[] = []
  private totalLength = 0

  constructor(points: Array<Point | BezierControlPoint>) {
    this._buildSegments(points)
  }

  /**
   * 构建曲线段
   */
  private _buildSegments(points: Array<Point | BezierControlPoint>) {
    this.segments = []
    this.segmentLengths = []
    this.totalLength = 0

    for (let i = 0; i < points.length - 1; i++) {
      const p0 = points[i]
      const p3 = points[i + 1]

      // 获取控制点手柄
      let p1: Point, p2: Point

      if ('outHandle' in p0) {
        const cp = p0 as BezierControlPoint
        // outHandle 是相对偏移，需要加到点位置上
        p1 = {
          lng: p0.lng + cp.outHandle.lng,
          lat: p0.lat + cp.outHandle.lat
        }
      } else {
        // 端点没有手柄，使用自身位置
        p1 = { lng: p0.lng, lat: p0.lat }
      }

      if ('inHandle' in p3) {
        const cp = p3 as BezierControlPoint
        // inHandle 是相对偏移，需要加到点位置上
        p2 = {
          lng: p3.lng + cp.inHandle.lng,
          lat: p3.lat + cp.inHandle.lat
        }
      } else {
        p2 = { lng: p3.lng, lat: p3.lat }
      }

      const segment = new CubicBezierSegment(
        { lng: p0.lng, lat: p0.lat },
        p1,
        p2,
        { lng: p3.lng, lat: p3.lat }
      )

      const length = segment.calculateLength()
      this.segments.push(segment)
      this.segmentLengths.push(length)
      this.totalLength += length
    }
  }

  /**
   * 重新构建曲线（用于控制点更新后）
   */
  rebuild(points: Array<Point | BezierControlPoint>) {
    this._buildSegments(points)
  }

  /**
   * 获取曲线总长度
   */
  getTotalLength(): number {
    return this.totalLength
  }

  /**
   * 根据弧长获取点
   */
  getPointAtLength(targetLength: number): Point {
    if (targetLength <= 0) {
      return this.segments[0]?.evaluate(0) || { lng: 0, lat: 0 }
    }
    if (targetLength >= this.totalLength) {
      const lastSegment = this.segments[this.segments.length - 1]
      return lastSegment ? lastSegment.evaluate(1) : { lng: 0, lat: 0 }
    }

    let accumulated = 0
    for (let i = 0; i < this.segments.length; i++) {
      const segLength = this.segmentLengths[i]
      if (accumulated + segLength >= targetLength) {
        return this.segments[i].getPointAtLength(targetLength - accumulated)
      }
      accumulated += segLength
    }

    return { lng: 0, lat: 0 }
  }

  /**
   * 生成均匀分布的点
   */
  generatePoints(count: number): Point[] {
    if (count <= 0) return []
    if (count === 1) return [this.getPointAtLength(0)]

    const points: Point[] = []
    const step = this.totalLength / (count - 1)

    for (let i = 0; i < count; i++) {
      points.push(this.getPointAtLength(i * step))
    }

    return points
  }
}
