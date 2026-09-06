<template>
  <div class="google-map-container">
    <div ref="mapContainer" class="google-map"></div>
    <div ref="customTooltip" class="custom-tooltip"></div>
  </div>
</template>

<script lang="ts">
// 动画 DOM Overlay 类（使用 CSS transform 旋转，避免 Canvas 变形）
// Google 地图为光栅瓦片渲染（无 canvas），直接挂载到地图容器 div
class AnimationDOMOverlay {
  private map: any
  private mapContainer: HTMLElement | null = null
  private position: { lat: number; lng: number } | null = null
  private style: 'arrow' | 'car' | 'person' = 'arrow'
  private bearing: number = 0
  private element: HTMLElement
  private innerElement: HTMLElement
  private onBoundsChangedHandler: (() => void) | null = null
  private projectionHelper: any

  constructor(map: any, projectionHelper: any) {
    this.map = map
    this.projectionHelper = projectionHelper

    // 创建外部容器（绝对定位）
    // z-index: 500 确保在地图控件之下但在地图内容之上
    this.element = document.createElement('div')
    this.element.style.cssText = 'position: absolute; top: 0; left: 0; pointer-events: none; z-index: 500;'

    // 创建内部元素（用于旋转）
    this.innerElement = document.createElement('div')
    this.innerElement.style.cssText = 'position: relative; transform-origin: center center;'

    this.element.appendChild(this.innerElement)

    this.addToMap()
    this.updateContent()
  }

  private addToMap() {
    // Google 地图容器：getDiv() 返回初始化时传入的容器（position: relative）
    const mapDiv = this.map?.getDiv?.()
    if (mapDiv) {
      this.mapContainer = mapDiv
      this.mapContainer.appendChild(this.element)

      // 监听地图移动/缩放事件（bounds_changed 涵盖两者），更新标记位置
      this.onBoundsChangedHandler = () => this.updatePosition()
      this.map.addListener('bounds_changed', this.onBoundsChangedHandler)
    }
  }

  private removeFromMap() {
    if (this.mapContainer && this.element.parentNode === this.mapContainer) {
      this.mapContainer.removeChild(this.element)
    }
    // Google 地图没有统一的 off 方法，移除时通过 listener 引用
    if (this.onBoundsChangedHandler) {
      // addListener 返回的 listener 有 remove 方法，这里保底用 google.maps.event
      const google = (window as any).google
      if (google?.maps?.event) {
        google.maps.event.removeListener(this.onBoundsChangedHandler)
      }
      this.onBoundsChangedHandler = null
    }
  }

  setPosition(lat: number, lng: number) {
    this.position = { lat, lng }
    this.updatePosition()
  }

  setStyle(style: 'arrow' | 'car' | 'person') {
    this.style = style
    this.updateContent()
    this.updatePosition() // 样式可能改变尺寸
  }

  setBearing(bearing: number) {
    this.bearing = bearing
    this.innerElement.style.transform = `rotate(${bearing}deg)`
  }

  destroy() {
    this.removeFromMap()
  }

  setMap(map: any | null) {
    if (map) {
      this.map = map
      if (!this.mapContainer) {
        this.addToMap()
      }
      this.updatePosition()
    } else {
      this.removeFromMap()
    }
  }

  private updatePosition() {
    if (!this.position || !this.map || !this.projectionHelper) return

    const pointPixel = this.projectionHelper.toContainerPixel(this.position)
    if (!pointPixel) return

    // 获取 DOM 元素的尺寸
    const width = this.style === 'car' ? 60 : 36
    const height = this.style === 'car' ? 40 : 36

    // 计算新的像素位置
    const newLeft = pointPixel.x - width / 2
    const newTop = pointPixel.y - height / 2

    this.element.style.transform = `translate3d(${newLeft}px, ${newTop}px, 0)`
  }

  private updateContent() {
    // car: 60×40，arrow/person: 36×36
    const width = this.style === 'car' ? 60 : 36
    const height = this.style === 'car' ? 40 : 36

    this.innerElement.style.width = `${width}px`
    this.innerElement.style.height = `${height}px`
    this.innerElement.style.display = 'flex'
    this.innerElement.style.alignItems = 'center'
    this.innerElement.style.justifyContent = 'center'

    if (this.style === 'car') {
      this.innerElement.className = 'animation-marker-car'
      this.innerElement.innerHTML = `
        <img src="/vehicle.svg" style="display: block; width: ${width}px; height: ${height}px;" />
      `
    } else if (this.style === 'person') {
      this.innerElement.className = 'animation-marker-person'
      this.innerElement.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="${width}" height="${height}">
          <circle cx="12" cy="8" r="4" fill="#409eff" />
          <path d="M12 13 L12 22" stroke="#409eff" stroke-width="3" stroke-linecap="round" />
          <path d="M8 16 L16 16" stroke="#409eff" stroke-width="3" stroke-linecap="round" />
        </svg>
      `
    } else {
      this.innerElement.className = 'animation-marker-arrow'
      this.innerElement.innerHTML = `
        <img src="/location.svg" style="display: block; width: ${width}px; height: ${height}px;" />
      `
    }
  }
}
</script>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useConfigStore } from '@/stores/config'
import { roadSignApi } from '@/api/roadSign'
import { parseRoadNumber, type ParsedRoadNumber } from '@/utils/roadSignParser'
import { formatDistance, formatDuration } from '@/utils/format'
import { useAnimationMap, type AnimationMapAdapter } from '@/composables/animation/useAnimationMap'
import type { MarkerPosition, MarkerStyle } from '@/types/animation'

// 类型定义
interface Point {
  latitude?: number
  longitude?: number
  latitude_wgs84?: number
  longitude_wgs84?: number
  latitude_gcj02?: number | null
  longitude_gcj02?: number | null
  latitude_bd09?: number | null
  longitude_bd09?: number | null
  elevation?: number | null
  time?: string | null
  speed?: number | null
  province?: string | null
  city?: string | null
  district?: string | null
  road_name?: string | null
  road_number?: string | null
}

// 格式化地理信息显示
function formatLocationInfo(point: Point): { html: string; needLoad: ParsedRoadNumber[] } {
  const parts: string[] = []
  const needLoad: ParsedRoadNumber[] = []

  // 行政区划
  if (point.province) parts.push(point.province)
  if (point.city && point.city !== point.province) parts.push(point.city)
  if (point.district) parts.push(point.district)

  // 道路信息
  const roadParts: string[] = []
  if (point.road_number) {
    const roadNumbers = point.road_number.split(',').map(s => s.trim())
    const signContents: string[] = []

    for (const num of roadNumbers) {
      const parsed = parseRoadNumber(num)
      if (parsed) {
        const cacheKey = parsed.province ? `${parsed.sign_type}:${parsed.code}:${parsed.province}` : `${parsed.sign_type}:${parsed.code}`
        const svg = roadSignSvgCache.get(cacheKey)

        if (svg) {
          signContents.push(`<span class="road-sign-inline">${svg}</span>`)
        } else {
          signContents.push(num)
          needLoad.push(parsed)
        }
      } else {
        signContents.push(num)
      }
    }

    if (signContents.length > 0) {
      roadParts.push(signContents.join(' '))
    }
  }
  if (point.road_name) {
    roadParts.push(point.road_name)
  }

  if (roadParts.length > 0) {
    parts.push(roadParts.join(' '))
  }

  return { html: parts.join(' '), needLoad }
}

// 异步获取道路标志 SVG
async function getRoadSignSvg(code: string, signType: 'way' | 'expwy', province?: string): Promise<string | null> {
  const cacheKey = province ? `${signType}:${code}:${province}` : `${signType}:${code}`
  const cached = roadSignSvgCache.get(cacheKey)
  if (cached) return cached

  try {
    const response = await roadSignApi.generate({
      sign_type: signType,
      code: code,
      ...(province && { province }),
    })
    const svg = response.svg
    roadSignSvgCache.set(cacheKey, svg)
    return svg
  } catch {
    return null
  }
}

// 异步加载道路编号的 SVG
async function loadRoadSignsForTooltip(parsedList: ParsedRoadNumber[]): Promise<boolean> {
  const config = configStore.config
  const showSigns = config?.show_road_sign_in_region_tree ?? true
  if (!showSigns || parsedList.length === 0) return false

  let loaded = false
  for (const parsed of parsedList) {
    const key = parsed.province ? `${parsed.sign_type}:${parsed.code}:${parsed.province}` : `${parsed.sign_type}:${parsed.code}`
    if (loadingSigns.has(key)) continue

    loadingSigns.add(key)
    try {
      const svg = await getRoadSignSvg(parsed.code, parsed.sign_type, parsed.province)
      if (svg) {
        loaded = true
      }
    } finally {
      loadingSigns.delete(key)
    }
  }

  return loaded
}

// 定义 emit 事件
const emit = defineEmits<{
  (e: 'point-hover', point: Point | null, pointIndex: number): void
  (e: 'track-hover', trackId: number | null): void
  (e: 'track-click', trackId: number): void
  (e: 'map-click', lng: number, lat: number): void  // 地图点击事件（WGS84 坐标）
}>()

interface Track {
  id: number | string
  points: Point[]
  name?: string
  start_time?: string | null
  end_time?: string | null
  distance?: number
  duration?: number
  opacity?: number  // 轨迹透明度
  color?: string  // 轨迹颜色
}

// 自定义覆盖层类型（用于绘制路径模式的控制点和曲线）
interface CustomOverlay {
  type: 'marker' | 'polyline'
  position?: [number, number]  // [lat, lng] for marker（WGS84）
  positions?: [number, number][]  // [[lat, lng], ...] for polyline（WGS84）
  icon?: {
    type: 'circle'
    radius: number
    fillColor: string
    fillOpacity: number
    strokeColor: string
    strokeWidth: number
  }
  label?: string  // marker label
  color?: string  // polyline color
  weight?: number  // polyline weight
  opacity?: number  // polyline opacity
  dashArray?: string  // polyline dashArray
}

interface Props {
  tracks?: Track[]
  highlightTrackId?: number
  highlightSegment?: { start: number; end: number } | null
  coloredSegments?: Array<{ start: number; end: number; color: string }> | null  // 多段彩色高亮
  availableSegments?: Array<{ start: number; end: number; key: string }> | null  // 可用区段列表
  highlightPointIndex?: number
  latestPointIndex?: number | null  // 实时轨迹最新点索引（显示绿色标记）
  defaultLayerId?: string
  mode?: 'home' | 'detail'
  mapScale?: number  // 地图缩放百分比（100-200），用于海报生成时调整视野
  trackOrientation?: 'horizontal' | 'vertical'  // 轨迹方向
  disablePointHover?: boolean  // 禁用轨迹点悬停显示（用于绘制路径模式）
  customOverlays?: CustomOverlay[]  // 自定义覆盖层（用于绘制路径模式的控制点和曲线）
}

const props = withDefaults(defineProps<Props>(), {
  tracks: () => [],
  highlightTrackId: undefined,
  highlightSegment: null,
  coloredSegments: null,
  availableSegments: null,
  highlightPointIndex: undefined,
  latestPointIndex: null,
  defaultLayerId: undefined,
  mode: 'detail',
  mapScale: 100,
  trackOrientation: 'horizontal',
  disablePointHover: false,
  customOverlays: () => [],
})

const configStore = useConfigStore()

// Google 地图实例
const mapContainer = ref<HTMLElement>()
const customTooltip = ref<HTMLElement>()
let googleMapInstance: any = null
let projectionHelper: any = null  // OverlayView 投影助手（坐标↔像素转换）
let polylineLayers: any[] = []  // 轨迹折线图层（每条轨迹一个 Polyline）
let coloredPolylineLayers: any[] = []  // 多段彩色高亮图层
let highlightPolylineLayer: any = null  // 路径段高亮图层
let customOverlayMarkers: any[] = []  // 自定义覆盖层标记
let customOverlayPolylines: any[] = []  // 自定义覆盖层折线
let mouseMarker: any = null  // Google 地图 Marker 实例（蓝色悬停点）
let lastTooltipPosition: { lat: number; lng: number } | null = null  // 上次 tooltip 显示的位置
let latestPointMarker: any = null  // 实时轨迹最新点标记（绿色）

// 存储轨迹点数据用于查询
let trackPoints: Point[] = []
let trackPath: { lat: number; lng: number }[] = []  // WGS84 坐标路径
// home 模式：按轨迹分开存储
const tracksData = new Map<number, { points: Point[]; path: { lat: number; lng: number }[]; track: Track }>()

// 节流和缓存
let lastHoverIndex = -1  // 上次悬停的点索引
let mouseDownPos: { x: number; y: number } | null = null  // 记录鼠标按下位置，用于区分点击和拖动
let isClickProcessing = false  // 防止移动端 touchend 和 click 重复触发

// 道路标志 SVG 缓存
const roadSignSvgCache = new Map<string, string>()
const loadingSigns = new Set<string>()
let currentTooltipPoint: Point | null = null  // 当前 tooltip 显示的点（用于异步更新）

// 动画相关状态
let animationPassedPolyline: any = null
let animationRemainingPolyline: any = null
let fullTrackPolyline: any = null  // 播放时的完整轨迹
let animationMarker: AnimationDOMOverlay | null = null
let currentMapRotation = 0
let isAnimationPlaying = false  // 跟踪动画播放状态，避免双色轨迹闪烁

// 地图事件监听器（用于清理）
const mapListeners: any[] = []

// 动画地图适配器实现
const animationAdapter: AnimationMapAdapter = {
  setPassedSegment(start, end) {
    // 播放状态下不更新轨迹，避免闪烁
    if (isAnimationPlaying) return

    if (!googleMapInstance || !props.tracks[0]?.points) return

    const points = props.tracks[0].points
    const toLatLng = (p: any) => ({
      lat: p.latitude_wgs84 ?? p.latitude,
      lng: p.longitude_wgs84 ?? p.longitude,
    })

    // 移除旧的轨迹
    if (animationPassedPolyline) {
      animationPassedPolyline.setMap(null)
      animationPassedPolyline = null
    }
    if (animationRemainingPolyline) {
      animationRemainingPolyline.setMap(null)
      animationRemainingPolyline = null
    }

    const google = (window as any).google

    // 非播放状态：使用双色轨迹显示进度
    const passedPoints = points.slice(0, end + 1)
    const remainingPoints = points.slice(end)

    if (passedPoints.length > 1) {
      animationPassedPolyline = new google.maps.Polyline({
        path: passedPoints.map(toLatLng),
        strokeColor: '#409eff',
        strokeOpacity: 1,
        strokeWeight: 5,
        map: googleMapInstance,
      })
    }

    if (remainingPoints.length > 1) {
      animationRemainingPolyline = new google.maps.Polyline({
        path: remainingPoints.map(toLatLng),
        strokeColor: '#c0c4cc',
        strokeOpacity: 1,
        strokeWeight: 5,
        map: googleMapInstance,
      })
    }
  },

  setMarkerPosition(position, style = 'arrow') {
    if (!googleMapInstance) return

    if (!animationMarker) {
      // 地图可能还未初始化，延迟创建标记
      setTimeout(() => {
        if (!animationMarker && googleMapInstance) {
          animationMarker = new AnimationDOMOverlay(googleMapInstance, projectionHelper)
          animationMarker.setPosition(position.lat, position.lng)
          animationMarker.setStyle(style)
          animationMarker.setBearing(position.bearing)
        }
      }, 0)
    } else {
      // 更新位置、样式和旋转
      animationMarker.setPosition(position.lat, position.lng)
      animationMarker.setStyle(style)
      animationMarker.setBearing(position.bearing)
    }
  },

  setCameraToMarker(position) {
    if (!googleMapInstance) return
    googleMapInstance.setCenter({ lat: position.lat, lng: position.lng })
  },

  setMapRotation(bearing) {
    if (!googleMapInstance) return
    // 光栅地图不支持 heading，仅在矢量地图（mapId）下生效
    try {
      googleMapInstance.setHeading(bearing)
    } catch {
      // 忽略不支持的情况
    }
    currentMapRotation = bearing
  },

  getMapRotation() {
    return currentMapRotation
  },

  // 设置动画播放状态（避免双色轨迹闪烁）
  setAnimationPlaying(playing) {
    isAnimationPlaying = playing

    if (!googleMapInstance || !props.tracks[0]?.points) return

    const points = props.tracks[0].points
    const google = (window as any).google
    const toLatLng = (p: any) => ({
      lat: p.latitude_wgs84 ?? p.latitude,
      lng: p.longitude_wgs84 ?? p.longitude,
    })

    if (playing) {
      // 播放开始：清除双色轨迹，绘制完整灰色轨迹
      if (animationPassedPolyline) {
        animationPassedPolyline.setMap(null)
        animationPassedPolyline = null
      }
      if (animationRemainingPolyline) {
        animationRemainingPolyline.setMap(null)
        animationRemainingPolyline = null
      }

      // 强制重新绘制完整灰色轨迹（用于相机模式切换时刷新）
      if (fullTrackPolyline) {
        fullTrackPolyline.setMap(null)
        fullTrackPolyline = null
      }

      if (points.length > 1) {
        fullTrackPolyline = new google.maps.Polyline({
          path: points.map(toLatLng),
          strokeColor: '#c0c4cc',
          strokeOpacity: 1,
          strokeWeight: 5,
          map: googleMapInstance,
        })
      }
    } else {
      // 播放停止：清除完整灰色轨迹
      if (fullTrackPolyline) {
        fullTrackPolyline.setMap(null)
        fullTrackPolyline = null
      }
      // 恢复双色轨迹（由 setPassedSegment 重新绘制）
    }
  },

  // 调整地图视野以适应轨迹（添加底部 padding）
  // 注意：bottomPaddingPx 可以是像素值或百分比（<=100）
  fitTrackWithPadding(bottomPaddingPx) {
    if (!googleMapInstance) return

    let paddingPercent: number

    // 判断是像素值还是百分比
    // TrackAnimationPlayer 传递的 5 表示 5%（而不是 5px）
    if (bottomPaddingPx <= 100) {
      // 小于等于 100，视为百分比
      paddingPercent = bottomPaddingPx
    } else {
      // 大于 100，视为像素值，转换为百分比
      const containerHeight = mapContainer.value?.offsetHeight || 600
      paddingPercent = (bottomPaddingPx / containerHeight) * 100
    }

    // 调用现有的 fitBounds 方法
    fitBounds(paddingPercent)
  },
}

// 计算两点距离
function distance(p1: [number, number], p2: [number, number]): number {
  const dx = p1[0] - p2[0]
  const dy = p1[1] - p2[1]
  return Math.sqrt(dx * dx + dy * dy)
}

// 计算点到线段的最近点
function closestPointOnSegment(p: [number, number], v: [number, number], w: [number, number]): [number, number] {
  const [px, py] = p
  const [vx, vy] = v
  const [wx, wy] = w

  const l2 = (wx - vx) ** 2 + (wy - vy) ** 2
  if (l2 === 0) return v

  let t = ((px - vx) * (wx - vx) + (py - vy) * (wy - vy)) / l2
  t = Math.max(0, Math.min(1, t))

  return [vx + t * (wx - vx), vy + t * (wy - vy)]
}

// 创建鼠标位置标记（使用 Google 地图 Marker，Canvas 绘制蓝色圆点）
function createMouseMarker() {
  const google = (window as any).google
  if (!google || !googleMapInstance) return

  // 使用 Canvas 绘制蓝色圆点
  const canvas = document.createElement('canvas')
  canvas.width = 16
  canvas.height = 16
  const ctx = canvas.getContext('2d')!

  // 绘制白色边框
  ctx.fillStyle = '#ffffff'
  ctx.beginPath()
  ctx.arc(8, 8, 7, 0, Math.PI * 2)
  ctx.fill()

  // 绘制蓝色圆点
  ctx.fillStyle = '#409eff'
  ctx.beginPath()
  ctx.arc(8, 8, 5, 0, Math.PI * 2)
  ctx.fill()

  // 转换为 data URL
  const dataUrl = canvas.toDataURL()

  mouseMarker = new google.maps.Marker({
    map: null,  // 初始不添加到地图
    icon: {
      url: dataUrl,
      size: new google.maps.Size(16, 16),
      anchor: new google.maps.Point(8, 8),
    },
    position: { lat: 0, lng: 0 },
  })
}

// 创建最新点标记（绿色）
function createLatestPointMarker() {
  const google = (window as any).google
  if (!google || !googleMapInstance) return

  // 使用 Canvas 绘制绿色圆点
  const canvas = document.createElement('canvas')
  canvas.width = 16
  canvas.height = 16
  const ctx = canvas.getContext('2d')!

  // 绘制白色边框
  ctx.fillStyle = '#ffffff'
  ctx.beginPath()
  ctx.arc(8, 8, 7, 0, Math.PI * 2)
  ctx.fill()

  // 绘制绿色圆点
  ctx.fillStyle = '#67c23a'
  ctx.beginPath()
  ctx.arc(8, 8, 5, 0, Math.PI * 2)
  ctx.fill()

  const dataUrl = canvas.toDataURL()

  latestPointMarker = new google.maps.Marker({
    map: null,
    icon: {
      url: dataUrl,
      size: new google.maps.Size(16, 16),
      anchor: new google.maps.Point(8, 8),
    },
    position: { lat: 0, lng: 0 },
  })
}

// 更新标记位置
function updateMarkerPosition(position: { lat: number; lng: number }) {
  if (!googleMapInstance || !mouseMarker) return

  mouseMarker.setPosition(position)
  mouseMarker.setMap(googleMapInstance)
}

// 更新自定义 tooltip 的位置
function updateCustomTooltipPosition(position: { lat: number; lng: number }, offsetX = 0, offsetY = -20, align: 'center' | 'left' | 'right' = 'center') {
  if (!googleMapInstance || !customTooltip.value || !projectionHelper) return

  // 将地理坐标转换为容器像素坐标
  const pointPixel = projectionHelper.toContainerPixel(position)
  if (!pointPixel) return

  const containerWidth = mapContainer.value?.clientWidth || 0
  const containerHeight = mapContainer.value?.clientHeight || 0

  // 先设置内容以获取实际尺寸
  customTooltip.value.style.visibility = 'hidden'
  customTooltip.value.style.display = 'block'

  // 获取实际尺寸
  const tooltipWidth = customTooltip.value.offsetWidth
  const tooltipHeight = customTooltip.value.offsetHeight

  // 根据 align 方式计算 x 坐标
  let x: number
  if (align === 'left') {
    // tooltip 左对齐到点（tooltip 在点右侧）
    x = pointPixel.x + 10
  } else if (align === 'right') {
    // tooltip 右对齐到点（tooltip 在点左侧）
    x = pointPixel.x - tooltipWidth - 10
  } else {
    // 居中
    x = pointPixel.x - tooltipWidth / 2 + offsetX
  }

  // 计算 y 坐标
  let y: number
  if (offsetY < 0) {
    // tooltip 在点上方
    y = pointPixel.y - tooltipHeight - 10
  } else {
    // tooltip 在点下方
    y = pointPixel.y + 10
  }

  // 边界检测：确保 tooltip 不超出容器
  const padding = 10
  if (x < padding) x = padding
  if (x + tooltipWidth > containerWidth - padding) x = containerWidth - tooltipWidth - padding
  if (y < padding) y = padding
  if (y + tooltipHeight > containerHeight - padding) y = containerHeight - tooltipHeight - padding

  customTooltip.value.style.visibility = ''
  customTooltip.value.style.left = `${x}px`
  customTooltip.value.style.top = `${y}px`
}

// 计算智能偏移量，避免 tooltip 超出地图边界
function calculateGoogleOffset(position: { lat: number; lng: number }): { x: number; y: number; align: 'center' | 'left' | 'right' } {
  if (!googleMapInstance || !mapContainer.value || !projectionHelper) {
    return { x: 0, y: -20, align: 'center' }
  }

  // 将地图坐标转换为容器像素坐标
  const pointPixel = projectionHelper.toContainerPixel(position)
  if (!pointPixel) {
    return { x: 0, y: -20, align: 'center' }
  }

  const containerWidth = mapContainer.value.clientWidth
  const containerHeight = mapContainer.value.clientHeight

  // Tooltip 的估计尺寸
  const tooltipWidth = 200
  const tooltipHeight = 100
  const padding = 10

  const pixelX = pointPixel.x
  const pixelY = pointPixel.y

  // 计算水平偏移和对齐方式
  let offsetX = 0
  let align: 'center' | 'left' | 'right' = 'center'

  // 检查是否靠近左右边界
  const tooltipLeft = pixelX - tooltipWidth / 2
  const tooltipRight = pixelX + tooltipWidth / 2

  if (tooltipRight > containerWidth - padding) {
    // 靠右边界
    if (pixelY < 180) {
      // 顶部区域：保持居中（tooltip 在点下方，不会遮挡）
      align = 'center'
      offsetX = (containerWidth - padding) - tooltipRight
    } else {
      // 非顶部区域：tooltip 放在点左侧，避免遮挡轨迹点
      align = 'right'
      offsetX = -10
    }
  } else if (tooltipLeft < padding) {
    // 靠左边界：tooltip 放在点右侧
    align = 'left'
    offsetX = 10
  }

  // 顶部区域：tooltip 显示在点下方，避免被遮住
  let offsetY = -20
  if (pixelY < 180) {
    offsetY = 15
  }

  return { x: offsetX, y: offsetY, align }
}

// 更新标记和提示框
function updateMarker(nearest: { point: Point; index: number; position: { lat: number; lng: number } }) {
  if (!googleMapInstance) return

  // 始终更新标记位置
  updateMarkerPosition(nearest.position)

  // 如果是同一个点，只更新位置（用于地图移动/缩放）
  if (nearest.index === lastHoverIndex) {
    if (lastTooltipPosition && customTooltip.value) {
      const offset = calculateGoogleOffset(nearest.position)
      updateCustomTooltipPosition(nearest.position, offset.x, offset.y, offset.align)
    }
    return
  }

  // 新的点，完整更新
  lastHoverIndex = nearest.index
  currentTooltipPoint = nearest.point
  lastTooltipPosition = nearest.position

  const { point, index } = nearest

  if (customTooltip.value) {
    customTooltip.value.innerHTML = buildPointTooltipHtml(point, index)
    customTooltip.value.style.display = 'block'

    const offset = calculateGoogleOffset(nearest.position)
    updateCustomTooltipPosition(nearest.position, offset.x, offset.y, offset.align)
  }

  // 异步加载道路标志 SVG
  loadRoadSignsAsync(point, index)

  // 发射事件
  emit('point-hover', point, index)
}

// 构建轨迹点 tooltip HTML
function buildPointTooltipHtml(point: Point, index: number): string {
  const timeStr = point.time ? new Date(point.time).toLocaleTimeString('zh-CN') : '-'
  const elevation = point.elevation != null ? `${point.elevation.toFixed(1)} m` : '-'
  const speed = point.speed != null ? `${(point.speed * 3.6).toFixed(1)} km/h` : '-'
  const locationResult = formatLocationInfo(point)

  return `
    <div class="tooltip-content" style="padding: 8px 12px; margin: 0; background: #fff; border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-size: 12px; line-height: 1.6;">
      <div style="font-weight: bold; color: #333; margin-bottom: 4px;">点 #${index}</div>
      ${locationResult.html ? `<div style="color: #666;">${locationResult.html}</div>` : ''}
      <div style="color: #666;">时间: ${timeStr}</div>
      <div style="color: #666;">速度: ${speed}</div>
      <div style="color: #666;">海拔: ${elevation}</div>
    </div>
  `
}

// 异步加载道路标志 SVG 并刷新 tooltip
function loadRoadSignsAsync(point: Point, index: number) {
  const locationResult = formatLocationInfo(point)
  if (locationResult.needLoad.length === 0) return

  const savedIndex = index
  const savedPoint = point
  nextTick(async () => {
    const loaded = await loadRoadSignsForTooltip(locationResult.needLoad)
    if (loaded && currentTooltipPoint === savedPoint && customTooltip.value) {
      customTooltip.value.innerHTML = buildPointTooltipHtml(savedPoint, savedIndex)
    }
  })
}

// 隐藏标记和提示框
function hideMarker() {
  if (lastHoverIndex === -1) return  // 已经隐藏了

  lastHoverIndex = -1
  currentTooltipPoint = null
  lastTooltipPosition = null

  if (mouseMarker) {
    mouseMarker.setMap(null)
  }

  if (customTooltip.value) {
    customTooltip.value.style.display = 'none'
  }

  if (props.mode === 'home') {
    emit('track-hover', null)
  } else {
    emit('point-hover', null, -1)
  }
}

// 从外部高亮指定点（由图表触发）
function highlightPoint(index: number) {
  if (index < 0 || index >= trackPoints.length) {
    hideMarker()
    return
  }

  if (index === lastHoverIndex) return

  lastHoverIndex = index

  const point = trackPoints[index]
  const position = trackPath[index]

  if (!googleMapInstance || !point || !position) return

  // 移动地图到指定点（如果点在视野外）
  const bounds = googleMapInstance.getBounds()
  if (bounds && !bounds.contains(position)) {
    googleMapInstance.panTo(position)
  }

  // 更新标记位置
  updateMarkerPosition(position)

  // 保存当前显示的点（用于异步更新）
  currentTooltipPoint = point
  lastTooltipPosition = position

  if (customTooltip.value) {
    customTooltip.value.innerHTML = buildPointTooltipHtml(point, index)
    customTooltip.value.style.display = 'block'

    const offset = calculateGoogleOffset(position)
    updateCustomTooltipPosition(position, offset.x, offset.y, offset.align)
  }

  // 异步加载道路标志 SVG
  loadRoadSignsAsync(point, index)
}

// 初始化
async function init() {
  // 等待配置加载
  if (!configStore.config) {
    await configStore.fetchConfig()
  }

  await initMap()
}

// 加载 Google Maps JavaScript API
async function loadGoogleMapScript(): Promise<void> {
  return new Promise((resolve, reject) => {
    if ((window as any).google?.maps) {
      resolve()
      return
    }

    // SDK 配置复用 google 图层（api_key / api_base_url）
    const layerConfig = configStore.getMapLayerById('google')
    const apiKey = layerConfig?.api_key || ''
    const apiBaseUrl = layerConfig?.api_base_url || 'https://maps.googleapis.com'

    if (!apiKey) {
      reject(new Error('Google Map API Key is required'))
      return
    }

    // 设置全局回调函数（loading=async 模式必须使用 callback）
    const callbackName = 'googleMapInitCallback'
    ;(window as any)[callbackName] = () => {
      resolve()
      delete (window as any)[callbackName]
    }

    const script = document.createElement('script')
    script.type = 'text/javascript'
    script.src = `${apiBaseUrl}/maps/api/js?key=${apiKey}&v=weekly&language=zh-CN&loading=async&callback=${callbackName}`
    script.async = true
    script.onerror = () => {
      reject(new Error('Failed to load Google Maps API'))
      delete (window as any)[callbackName]
    }
    document.head.appendChild(script)
  })
}

// 初始化地图
async function initMap() {
  if (!mapContainer.value) return

  try {
    await loadGoogleMapScript()

    const google = (window as any).google

    // 创建地图实例
    googleMapInstance = new google.maps.Map(mapContainer.value, {
      center: { lat: 39.984104, lng: 116.307428 },
      zoom: 12,
      minZoom: 3,
      maxZoom: 20,
      // 控件配置：隐藏默认 UI，保留缩放和比例尺
      disableDefaultUI: true,
      zoomControl: true,
      scaleControl: true,
      // POI 不可点击，避免干扰轨迹交互
      clickableIcons: false,
      // 移动端单指即可拖动地图
      gestureHandling: 'greedy',
    })

    // 创建投影助手（OverlayView，用于坐标↔像素转换）
    // 必须在地图 projection 就绪后使用（idle 事件后）
    projectionHelper = new (class extends google.maps.OverlayView {
      onAdd() { /* 无需额外处理 */ }
      onRemove() { /* 无需额外处理 */ }
      draw() { /* 无需额外处理 */ }

      toContainerPixel(latLng: { lat: number; lng: number }) {
        return this.getProjection()?.fromLatLngToContainerPixel(latLng) || null
      }

      toLatLng(pixel: { x: number; y: number }) {
        return this.getProjection()?.fromContainerPixelToLatLng(pixel) || null
      }
    })()
    projectionHelper.setMap(googleMapInstance)

    // 创建标记
    createMouseMarker()
    createLatestPointMarker()

    // 统一的鼠标处理函数
    const handleMouseMove = (lat: number, lng: number) => {
      // 绘制路径模式：禁用 tooltip
      if (props.disablePointHover) {
        hideMarker()
        return
      }

      if (props.mode === 'home') {
        handleHomeModeMouseMove(lat, lng)
      } else {
        handleDetailModeMouseMove(lat, lng)
      }
    }

    // detail 模式：显示最近的点信息
    const handleDetailModeMouseMove = (lat: number, lng: number) => {
      if (trackPath.length < 2) return

      const zoom = googleMapInstance.getZoom()
      const dynamicDistance = Math.pow(2, 12 - zoom) * 0.008

      let minDistance = Infinity
      let nearestIndex = -1
      let nearestPosition: { lat: number; lng: number } | null = null

      // 快速查找最近的点
      for (let i = 0; i < trackPath.length - 1; i++) {
        const p1 = [trackPath[i].lng, trackPath[i].lat] as [number, number]
        const p2 = [trackPath[i + 1].lng, trackPath[i + 1].lat] as [number, number]
        const closest = closestPointOnSegment([lng, lat], p1, p2)
        const dist = distance([lng, lat], closest)

        if (dist < minDistance) {
          minDistance = dist
          nearestPosition = { lat: closest[1], lng: closest[0] }
          const distToP1 = distance(closest, p1)
          const distToP2 = distance(closest, p2)
          nearestIndex = distToP1 < distToP2 ? i : i + 1
        }
      }

      const triggered = minDistance < dynamicDistance

      // 更新或隐藏标记
      if (triggered && nearestIndex >= 0 && nearestIndex < trackPoints.length) {
        const point = trackPoints[nearestIndex]
        if (nearestIndex !== lastHoverIndex) {
          updateMarker({ point, index: nearestIndex, position: nearestPosition! })
        }
      } else {
        hideMarker()
      }
    }

    // home 模式：显示最近的轨迹信息
    const handleHomeModeMouseMove = (lat: number, lng: number) => {
      const zoom = googleMapInstance.getZoom()
      const dynamicDistance = Math.pow(2, 12 - zoom) * 0.008

      let minDistance = Infinity
      let nearestTrackId: number | null = null
      let nearestPosition: { lat: number; lng: number } | null = null

      // 遍历所有轨迹，找到最近的轨迹
      for (const [trackId, data] of tracksData) {
        if (data.path.length < 2) continue

        for (let i = 0; i < data.path.length - 1; i++) {
          const p1 = [data.path[i].lng, data.path[i].lat] as [number, number]
          const p2 = [data.path[i + 1].lng, data.path[i + 1].lat] as [number, number]
          const closest = closestPointOnSegment([lng, lat], p1, p2)
          const dist = distance([lng, lat], closest)

          if (dist < minDistance) {
            minDistance = dist
            nearestPosition = { lat: closest[1], lng: closest[0] }
            nearestTrackId = trackId
          }
        }
      }

      const triggered = minDistance < dynamicDistance

      if (triggered && nearestTrackId !== null) {
        const trackData = tracksData.get(nearestTrackId)
        if (!trackData) return

        const track = trackData.track

        // 如果是同一条轨迹，跳过更新
        if (nearestTrackId === lastHoverIndex) return

        lastHoverIndex = nearestTrackId
        lastTooltipPosition = nearestPosition

        // 更新标记位置并显示
        if (mouseMarker && nearestPosition) {
          updateMarkerPosition(nearestPosition)
        }

        const isMobile = window.innerWidth <= 1366

        if (customTooltip.value && nearestPosition) {
          customTooltip.value.innerHTML = buildTrackTooltipHtml(track, isMobile)
          customTooltip.value.style.display = 'block'

          const offset = calculateGoogleOffset(nearestPosition)
          updateCustomTooltipPosition(nearestPosition, offset.x, offset.y, offset.align)
        }

        // 发射事件
        emit('track-hover', nearestTrackId)
      } else {
        hideMarker()
      }
    }

    // 桌面端：鼠标移动监听（Google 地图实例）
    mapListeners.push(
      googleMapInstance.addListener('mousemove', (evt: any) => {
        const lat = evt.latLng?.lat()
        const lng = evt.latLng?.lng()
        if (lat !== undefined && lng !== undefined) {
          handleMouseMove(lat, lng)
        }
      })
    )

    // 鼠标离开地图时隐藏标记（仅桌面端）
    const isMobile = window.innerWidth <= 1366
    if (!isMobile) {
      mapListeners.push(
        googleMapInstance.addListener('mouseout', () => {
          hideMarker()
        })
      )
    }

    // 监听地图移动/缩放事件，更新 tooltip 位置（bounds_changed 涵盖两者）
    mapListeners.push(
      googleMapInstance.addListener('bounds_changed', () => {
        if (lastTooltipPosition && customTooltip.value && customTooltip.value.style.display !== 'none') {
          const offset = calculateGoogleOffset(lastTooltipPosition)
          updateCustomTooltipPosition(lastTooltipPosition, offset.x, offset.y, offset.align)
        }
      })
    )

    // 点击地图显示轨迹信息（同时支持桌面端和移动端）
    if (mapContainer.value) {
      // 监听鼠标按下事件（记录位置，用于区分点击和拖动）
      mapContainer.value.addEventListener('mousedown', mouseDownHandler, true)

      // 监听点击事件（桌面端）- 使用冒泡阶段，让 HUD 元素先响应
      mapContainer.value.addEventListener('click', containerClickHandler, false)

      // 同时监听触摸事件（移动端）- 使用冒泡阶段，让 HUD 元素先响应
      mapContainer.value.addEventListener('touchend', containerTouchEndHandler, false)
    }

    // 更新轨迹（包括自定义覆盖层）
    updateTracks()
  } catch (error) {
    console.error('[GoogleMap] 初始化失败:', error)
  }
}

// 鼠标按下处理（记录位置，用于区分点击和拖动）
function mouseDownHandler(e: MouseEvent) {
  mouseDownPos = { x: e.clientX, y: e.clientY }
}

// 容器点击处理（桌面端）
function containerClickHandler(e: Event) {
  // 移动端：如果刚处理完 touchend，跳过 click 事件
  if (isClickProcessing) return

  // 检查是否是拖动操作（鼠标按下和抬起位置超过 5px 视为拖动）
  if (mouseDownPos && e instanceof MouseEvent) {
    const deltaX = Math.abs(e.clientX - mouseDownPos.x)
    const deltaY = Math.abs(e.clientY - mouseDownPos.y)
    if (deltaX > 5 || deltaY > 5) {
      // 这是拖动操作，不处理点击
      mouseDownPos = null
      return
    }
  }
  mouseDownPos = null

  // 复用 initMap 中定义的点击逻辑
  handleMapClick(e)
}

// 容器触摸结束处理（移动端）
function containerTouchEndHandler(e: Event) {
  // 防止 touchend 后立即触发 click 导致重复处理
  e.preventDefault()
  isClickProcessing = true
  handleMapClick(e)
  // 300ms 后清除标志（防止影响后续点击）
  setTimeout(() => {
    isClickProcessing = false
  }, 300)
}

// 构建轨迹 tooltip HTML（home 模式）
function buildTrackTooltipHtml(track: Track, showHint: boolean): string {
  const formatTime = (time: string | null | undefined, endDate: boolean = false) => {
    if (!time) return '-'
    const date = new Date(time)
    if (endDate) {
      return date.toLocaleString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit',
      })
    }
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const isSameDay = (start: string | null | undefined, end: string | null | undefined) => {
    if (!start || !end) return false
    const startDate = new Date(start)
    const endDate = new Date(end)
    return startDate.getFullYear() === endDate.getFullYear() &&
           startDate.getMonth() === endDate.getMonth() &&
           startDate.getDate() === endDate.getDate()
  }

  const formatTimeRange = () => {
    const startTime = formatTime(track.start_time, false)
    const endTime = isSameDay(track.start_time, track.end_time)
      ? formatTime(track.end_time, true)
      : formatTime(track.end_time, false)
    return `${startTime} ~ ${endTime}`
  }

  return `
    <div class="track-tooltip" data-track-id="${track.id}" style="padding: 8px 12px; background: rgba(255, 255, 255, 0.95); border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-size: 12px; line-height: 1.6; cursor: pointer;">
      <div style="font-weight: bold; color: #333; margin-bottom: 4px;">${track.name || '未命名轨迹'}</div>
      <div style="color: #666;">时间: ${formatTimeRange()}</div>
      <div style="color: #666;">里程: ${formatDistance(track.distance)}</div>
      <div style="color: #666;">历时: ${formatDuration(track.duration)}</div>
      ${showHint ? '<div style="font-size: 10px; color: #409eff; margin-top: 4px;">点击查看详情</div>' : ''}
    </div>
  `
}

// 地图点击统一处理（从容器 DOM 事件提取坐标）
function handleMapClick(e: Event) {
  if (!googleMapInstance) return

  const target = e.target as HTMLElement

  // 检查点击的是否是回放控制浮窗的元素
  const hudEl = target?.closest('.track-animation-player, .animation-hud, .hud-content') as HTMLElement
  if (hudEl) return

  // 检查点击的是否是 tooltip 中的轨迹卡片
  const tooltipEl = target?.closest('.track-tooltip') as HTMLElement
  if (tooltipEl) {
    const trackId = tooltipEl.getAttribute('data-track-id')
    if (trackId) {
      emit('track-click', parseInt(trackId))
    }
    return
  }

  // 获取点击位置
  let clientX: number, clientY: number
  if (e instanceof MouseEvent) {
    clientX = e.clientX
    clientY = e.clientY
  } else if ((e as any).changedTouches && (e as any).changedTouches.length > 0) {
    clientX = (e as any).changedTouches[0].clientX
    clientY = (e as any).changedTouches[0].clientY
  } else {
    return
  }

  // 获取容器的位置信息，转换为容器像素坐标
  const rect = mapContainer.value?.getBoundingClientRect()
  if (!rect) return
  const x = clientX - rect.left
  const y = clientY - rect.top

  // 通过投影助手将容器像素转换为经纬度（WGS84）
  if (!projectionHelper) return
  const latLng = projectionHelper.toLatLng({ x, y })?.toJSON?.()
  if (!latLng) return
  const { lat, lng } = latLng

  // 绘制路径模式：直接发射点击事件（Google 地图使用 WGS84，无需转换）
  if (props.disablePointHover) {
    emit('map-click', lng, lat)
    return
  }

  const zoom = googleMapInstance.getZoom()
  const dynamicDistance = Math.pow(2, 12 - zoom) * 0.008

  if (props.mode === 'home') {
    // home 模式：显示轨迹信息
    if (tracksData.size === 0) {
      hideMarker()
      return
    }

    let minDistance = Infinity
    let nearestTrackId: number | null = null
    let nearestPosition: { lat: number; lng: number } | null = null

    for (const [trackId, data] of tracksData) {
      if (data.path.length < 2) continue

      for (let i = 0; i < data.path.length - 1; i++) {
        const p1 = [data.path[i].lng, data.path[i].lat] as [number, number]
        const p2 = [data.path[i + 1].lng, data.path[i + 1].lat] as [number, number]
        const closest = closestPointOnSegment([lng, lat], p1, p2)
        const dist = distance([lng, lat], closest)

        if (dist < minDistance) {
          minDistance = dist
          nearestPosition = { lat: closest[1], lng: closest[0] }
          nearestTrackId = trackId
        }
      }
    }

    const triggered = minDistance < dynamicDistance

    if (triggered && nearestTrackId !== null) {
      // 桌面端：直接跳转
      const isMobile = window.innerWidth <= 1366
      if (!isMobile) {
        emit('track-click', nearestTrackId)
        return
      }

      // 移动端：显示自定义 tooltip
      const trackData = tracksData.get(nearestTrackId)
      if (!trackData) return

      const track = trackData.track
      lastHoverIndex = nearestTrackId
      lastTooltipPosition = nearestPosition

      if (mouseMarker && nearestPosition) {
        updateMarkerPosition(nearestPosition)
      }

      if (customTooltip.value && nearestPosition) {
        customTooltip.value.innerHTML = buildTrackTooltipHtml(track, true)
        customTooltip.value.style.display = 'block'

        const offset = calculateGoogleOffset(nearestPosition)
        updateCustomTooltipPosition(nearestPosition, offset.x, offset.y, offset.align)
      }

      emit('track-hover', nearestTrackId)
    } else {
      hideMarker()
    }
  } else {
    // detail 模式：显示点信息
    if (trackPath.length < 2) {
      hideMarker()
      return
    }

    let minDistance = Infinity
    let nearestIndex = -1
    let nearestPosition: { lat: number; lng: number } | null = null

    for (let i = 0; i < trackPath.length - 1; i++) {
      const p1 = [trackPath[i].lng, trackPath[i].lat] as [number, number]
      const p2 = [trackPath[i + 1].lng, trackPath[i + 1].lat] as [number, number]
      const closest = closestPointOnSegment([lng, lat], p1, p2)
      const dist = distance([lng, lat], closest)

      if (dist < minDistance) {
        minDistance = dist
        nearestPosition = { lat: closest[1], lng: closest[0] }
        const distToP1 = distance(closest, p1)
        const distToP2 = distance(closest, p2)
        nearestIndex = distToP1 < distToP2 ? i : i + 1
      }
    }

    const triggered = minDistance < dynamicDistance

    if (triggered && nearestIndex >= 0 && nearestIndex < trackPoints.length) {
      const point = trackPoints[nearestIndex]
      updateMarker({ point, index: nearestIndex, position: nearestPosition! })
    } else {
      hideMarker()
    }
  }
}

// 根据坐标系获取经纬度（Google 地图使用 WGS84）
function getWGS84Coords(point: Point): { lat: number; lng: number } | null {
  const lat = point.latitude_wgs84 ?? point.latitude
  const lng = point.longitude_wgs84 ?? point.longitude
  if (lat !== undefined && lng !== undefined && !isNaN(lat) && !isNaN(lng)) {
    return { lat, lng }
  }
  return null
}

// 绘制轨迹
function drawTracks() {
  if (!googleMapInstance || !props.tracks || props.tracks.length === 0) return

  const google = (window as any).google

  // 清除现有轨迹图层
  polylineLayers.forEach(layer => {
    try { layer.setMap(null) } catch { /* ignore */ }
  })
  polylineLayers = []

  // 清除路径段高亮图层
  if (highlightPolylineLayer) {
    highlightPolylineLayer.setMap(null)
    highlightPolylineLayer = null
  }

  // 清除多段彩色高亮图层
  coloredPolylineLayers.forEach(layer => {
    try { layer.setMap(null) } catch { /* ignore */ }
  })
  coloredPolylineLayers = []

  // 清除动画相关元素（只在非播放状态时清除）
  if (animationMarker && !isAnimationPlaying) {
    try {
      animationMarker.destroy()
    } catch { /* ignore */ }
    animationMarker = null
  }
  if (animationPassedPolyline) {
    try { animationPassedPolyline.setMap(null) } catch { /* ignore */ }
    animationPassedPolyline = null
  }
  if (animationRemainingPolyline) {
    try { animationRemainingPolyline.setMap(null) } catch { /* ignore */ }
    animationRemainingPolyline = null
  }
  if (fullTrackPolyline) {
    try { fullTrackPolyline.setMap(null) } catch { /* ignore */ }
    fullTrackPolyline = null
  }

  // 重置轨迹点数据
  trackPoints = []
  trackPath = []
  tracksData.clear()

  // 准备轨迹数据
  const bounds: { lat: number; lng: number }[] = []

  for (const track of props.tracks) {
    if (!track.points || track.points.length === 0) continue

    const paths: { lat: number; lng: number }[] = []
    const trackPathData: { lat: number; lng: number }[] = []
    const trackPointsData: Point[] = []

    for (const point of track.points) {
      const coords = getWGS84Coords(point)
      if (!coords) continue

      const { lat, lng } = coords
      paths.push({ lat, lng })
      bounds.push({ lat, lng })

      // detail 模式：合并所有轨迹
      trackPoints.push(point)
      trackPath.push({ lat, lng })

      // home 模式：按轨迹分开存储
      trackPointsData.push(point)
      trackPathData.push({ lat, lng })
    }

    if (paths.length === 0) continue

    // 保存轨迹数据用于 home 模式
    tracksData.set(track.id, {
      points: trackPointsData,
      path: trackPathData,
      track,
    })

    const isHighlighted = track.id === props.highlightTrackId

    // 根据 track.opacity 和 track.color 计算 RGBA 颜色
    const opacity = track.opacity !== undefined ? track.opacity : 0.8
    const baseColor = track.color || '#FF0000'
    // 解析 hex 颜色转为 RGB
    const r = parseInt(baseColor.slice(1, 3), 16)
    const g = parseInt(baseColor.slice(3, 5), 16)
    const b = parseInt(baseColor.slice(5, 7), 16)

    const layer = new google.maps.Polyline({
      path: paths,
      strokeColor: baseColor,
      strokeOpacity: opacity,
      strokeWeight: isHighlighted ? 6 : 4,
      map: googleMapInstance,
    })
    polylineLayers.push(layer)
  }

  if (polylineLayers.length === 0) return

  // 绘制多段彩色高亮（插值页面）
  if (props.mode === 'detail' && props.coloredSegments && trackPath.length > 0) {
    props.coloredSegments.forEach((seg) => {
      const { start, end, color } = seg
      if (start >= 0 && end < trackPath.length && start <= end) {
        const segmentPath = trackPath.slice(start, end + 1)
        if (segmentPath.length > 0) {
          const coloredLayer = new google.maps.Polyline({
            path: segmentPath,
            strokeColor: color,
            strokeOpacity: 1,
            strokeWeight: 8,
            zIndex: 10,
            map: googleMapInstance,
          })
          coloredPolylineLayers.push(coloredLayer)
        }
      }
    })
  }
  // 绘制路径段高亮（detail 模式，兼容旧逻辑）
  else if (props.mode === 'detail' && props.highlightSegment && trackPath.length > 0) {
    const { start, end } = props.highlightSegment
    // 确保索引在有效范围内
    if (start >= 0 && end < trackPath.length && start <= end) {
      const segmentPath = trackPath.slice(start, end + 1)
      if (segmentPath.length > 0) {
        highlightPolylineLayer = new google.maps.Polyline({
          path: segmentPath,
          strokeColor: '#409eff',  // 蓝色高亮
          strokeOpacity: 1,
          strokeWeight: 8,
          zIndex: 10,
          map: googleMapInstance,
        })
      }
    }
  }

  // 自动适应视图（绘制路径模式禁用）
  if (bounds.length > 0 && !props.disablePointHover) {
    try {
      // 计算边界
      let minLat = bounds[0].lat
      let maxLat = bounds[0].lat
      let minLng = bounds[0].lng
      let maxLng = bounds[0].lng

      for (const point of bounds) {
        if (point.lat < minLat) minLat = point.lat
        if (point.lat > maxLat) maxLat = point.lat
        if (point.lng < minLng) minLng = point.lng
        if (point.lng > maxLng) maxLng = point.lng
      }

      const boundsObj = new google.maps.LatLngBounds(
        { lat: minLat, lng: minLng },
        { lat: maxLat, lng: maxLng }
      )

      // 获取容器尺寸
      const container = mapContainer.value
      if (!container) return
      const containerWidth = container.clientWidth || 800
      const containerHeight = container.clientHeight || 600

      // 移动端使用百分比 padding，桌面端使用固定像素
      const isMobile = window.innerWidth <= 1366
      let padding: number
      if (isMobile) {
        // 移动端：使用 10% 的 padding（避免 100px 占比太大）
        padding = Math.round(Math.max(containerWidth, containerHeight) * 0.10)
      } else {
        // 桌面端：使用 100px padding
        padding = 100
      }

      googleMapInstance.fitBounds(boundsObj, padding)
    } catch (e) {
      console.error('[GoogleMap] fitBounds error:', e)
    }
  }

  // 更新最新点标记
  updateLatestPointMarker()
}

// 更新轨迹
function updateTracks() {
  drawTracks()
  drawCustomOverlays()
}

// 绘制自定义覆盖层（用于绘制路径模式的控制点和曲线）
function drawCustomOverlays() {
  if (!googleMapInstance) return

  const google = (window as any).google

  // 清除现有的自定义覆盖层
  customOverlayMarkers.forEach(marker => {
    try { marker.setMap(null) } catch { /* ignore */ }
  })
  customOverlayMarkers = []
  customOverlayPolylines.forEach(layer => {
    try { layer.setMap(null) } catch { /* ignore */ }
  })
  customOverlayPolylines = []

  if (!props.customOverlays || props.customOverlays.length === 0) return

  for (const overlay of props.customOverlays) {
    if (overlay.type === 'marker') {
      // 使用 position 字段（WGS84）
      if (!overlay.position || !overlay.icon) continue
      const [lat, lng] = overlay.position

      const radius = overlay.icon.radius || 6
      const fillColor = overlay.icon.fillColor || '#f56c6c'
      const fillOpacity = overlay.icon.fillOpacity !== undefined ? overlay.icon.fillOpacity : 0.9
      const strokeColor = overlay.icon.strokeColor || '#fff'
      const strokeWidth = overlay.icon.strokeWidth || 2

      // 使用 Canvas 绘制圆形标记
      const canvas = document.createElement('canvas')
      const size = radius * 2
      canvas.width = size
      canvas.height = size
      const ctx = canvas.getContext('2d')!

      // 绘制填充圆
      ctx.fillStyle = fillColor
      ctx.globalAlpha = fillOpacity
      ctx.beginPath()
      ctx.arc(radius, radius, radius - strokeWidth / 2, 0, Math.PI * 2)
      ctx.fill()

      // 绘制边框
      ctx.strokeStyle = strokeColor
      ctx.lineWidth = strokeWidth
      ctx.globalAlpha = 1
      ctx.stroke()

      // 绘制标签
      if (overlay.label) {
        ctx.fillStyle = '#fff'
        ctx.font = `bold ${radius * 0.8}px sans-serif`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillText(overlay.label, radius, radius)
      }

      const dataUrl = canvas.toDataURL()

      customOverlayMarkers.push(new google.maps.Marker({
        position: { lat, lng },
        icon: {
          url: dataUrl,
          size: new google.maps.Size(size, size),
          anchor: new google.maps.Point(radius, radius),
        },
        map: googleMapInstance,
      }))
    } else if (overlay.type === 'polyline' && overlay.positions && overlay.positions.length > 1) {
      // 使用 positions 字段（WGS84）
      const positions = overlay.positions
      const color = overlay.color || '#409eff'
      const weight = overlay.weight || 3
      const opacity = overlay.opacity !== undefined ? overlay.opacity : 0.8

      const layer = new google.maps.Polyline({
        path: positions.map(([lat, lng]) => ({ lat, lng })),
        strokeColor: color,
        strokeOpacity: opacity,
        strokeWeight: weight,
        map: googleMapInstance,
      })
      customOverlayPolylines.push(layer)
    }
  }
}

// 监听 tracks 变化
watch(() => props.tracks, () => {
  updateTracks()
}, { deep: true })

watch(() => props.highlightTrackId, () => {
  updateTracks()
})

watch(() => props.highlightSegment, () => {
  updateTracks()
})

watch(() => props.coloredSegments, () => {
  updateTracks()
})

watch(() => props.customOverlays, () => {
  drawCustomOverlays()
}, { deep: true })

// 生命周期
onMounted(async () => {
  await init()

  // 注册动画适配器
  setTimeout(() => {
    const { registerAdapter } = useAnimationMap()
    registerAdapter(animationAdapter)
  }, 100)
})

onUnmounted(() => {
  // 清理动画元素
  if (animationPassedPolyline) {
    animationPassedPolyline.setMap(null)
  }
  if (animationRemainingPolyline) {
    animationRemainingPolyline.setMap(null)
  }
  if (animationMarker) {
    animationMarker.setMap(null)
  }

  // 注销动画适配器
  const { unregisterAdapter } = useAnimationMap()
  unregisterAdapter()

  // 清理标记和提示框
  if (mouseMarker) {
    mouseMarker.setMap(null)
    mouseMarker = null
  }
  if (latestPointMarker) {
    latestPointMarker.setMap(null)
    latestPointMarker = null
  }
  if (customTooltip.value) {
    customTooltip.value.style.display = 'none'
  }
  polylineLayers.forEach(layer => layer.setMap(null))
  polylineLayers = []

  // 移除容器事件监听
  if (mapContainer.value) {
    mapContainer.value.removeEventListener('mousedown', mouseDownHandler, true)
    mapContainer.value.removeEventListener('click', containerClickHandler, false)
    mapContainer.value.removeEventListener('touchend', containerTouchEndHandler, false)
  }

  // 清理地图事件监听
  const google = (window as any).google
  if (google?.maps?.event) {
    mapListeners.forEach(listener => google.maps.event.removeListener(listener))
    mapListeners.length = 0
    // 清理投影助手
    if (projectionHelper) {
      projectionHelper.setMap(null)
      projectionHelper = null
    }
    google.maps.event.clearInstanceListeners(googleMapInstance)
  }
  googleMapInstance = null
})

// 根据边界框直接设置地图视野（用于聚焦到特定区段）
function fitToBounds(bounds: { minLat: number; maxLat: number; minLon: number; maxLon: number }, paddingPercent: number = 15) {
  if (!googleMapInstance) return

  const google = (window as any).google
  const { minLat, maxLat, minLon, maxLon } = bounds

  const boundsObj = new google.maps.LatLngBounds(
    { lat: minLat, lng: minLon },
    { lat: maxLat, lng: maxLon }
  )

  // paddingPercent 转换为像素（Google fitBounds 的 padding 为像素值）
  const container = mapContainer.value
  const size = container ? Math.max(container.clientWidth, container.clientHeight) : 800
  const padding = Math.round(size * (paddingPercent / 100))

  googleMapInstance.fitBounds(boundsObj, padding)
}

// 调整地图大小（用于响应式布局）
function resize() {
  if (googleMapInstance) {
    // Google 地图会自动调整大小
  }
}

// 将所有轨迹居中显示（四周留指定百分比空间）
function fitBounds(paddingPercent: number = 5) {
  if (!googleMapInstance) return

  const google = (window as any).google

  // 计算所有轨迹的边界
  const bounds: { lat: number; lng: number }[] = []

  for (const track of props.tracks) {
    if (!track.points || track.points.length === 0) continue
    for (const point of track.points) {
      const coords = getWGS84Coords(point)
      if (!coords) continue
      const { lat, lng } = coords
      if (!isNaN(lat) && !isNaN(lng)) {
        bounds.push({ lat, lng })
      }
    }
  }

  if (bounds.length === 0) return

  try {
    // 计算边界
    let minLat = bounds[0].lat
    let maxLat = bounds[0].lat
    let minLng = bounds[0].lng
    let maxLng = bounds[0].lng

    for (const point of bounds) {
      if (point.lat < minLat) minLat = point.lat
      if (point.lat > maxLat) maxLat = point.lat
      if (point.lng < minLng) minLng = point.lng
      if (point.lng > maxLng) maxLng = point.lng
    }

    const sw = { lat: minLat, lng: minLng }
    const ne = { lat: maxLat, lng: maxLng }
    const boundsObj = new google.maps.LatLngBounds(sw, ne)

    // 获取容器尺寸
    const container = mapContainer.value
    if (!container) return
    const containerWidth = container.clientWidth || 800
    const containerHeight = container.clientHeight || 600
    const padding = Math.round(Math.max(containerWidth, containerHeight) * (paddingPercent / 100))

    // 检查是否是 map-only 模式（通过 URL 判断）
    const isMapOnlyMode = window.location.pathname.includes('/map-only')
    const mapScale = isMapOnlyMode ? (props.mapScale || 100) : 100

    googleMapInstance.fitBounds(boundsObj, padding)

    // 如果是 map-only 模式且有缩放，根据边界框几何计算目标 zoom
    if (isMapOnlyMode && mapScale > 100) {
      setTimeout(() => {
        const zoomAfter = googleMapInstance.getZoom()

        // 在当前 zoom 下，将边界框转换为像素
        const swPixel = projectionHelper?.toContainerPixel(sw)
        const nePixel = projectionHelper?.toContainerPixel(ne)
        if (!swPixel || !nePixel) return

        const currentPixelWidth = Math.abs(nePixel.x - swPixel.x)
        const currentPixelHeight = Math.abs(nePixel.y - swPixel.y)

        // CSS scale 会放大地图显示，但不改变容器尺寸
        // 目标：边界框在放大后占据容器 90%，即放大前应占据 90% / scale
        const scale = mapScale / 100
        const targetContentWidth = containerWidth * 0.9 / scale
        const targetContentHeight = containerHeight * 0.9 / scale

        // 计算需要的缩放级别（zoom 每增加 1，像素尺寸翻倍）
        const widthZoomDelta = Math.log2(targetContentWidth / currentPixelWidth)
        const heightZoomDelta = Math.log2(targetContentHeight / currentPixelHeight)

        // 取较小的 delta，确保边界框完全在视野内
        const zoomDelta = Math.min(widthZoomDelta, heightZoomDelta)
        const targetZoom = Math.max(3, Math.min(20, zoomAfter + zoomDelta))

        console.log('[GoogleMap] 几何缩放计算:', {
          边界框: `(${minLng}, ${minLat}) → (${maxLng}, ${maxLat})`,
          当前像素: `${currentPixelWidth.toFixed(0)}x${currentPixelHeight.toFixed(0)}`,
          容器尺寸: `${containerWidth}x${containerHeight}`,
          CSS缩放: `${scale}`,
          目标内容: `${targetContentWidth.toFixed(0)}x${targetContentHeight.toFixed(0)}`,
          zoomDelta: zoomDelta.toFixed(2),
          zoom: `${zoomAfter.toFixed(1)} → ${targetZoom.toFixed(1)}`
        })

        googleMapInstance.setZoom(targetZoom)
      }, 500)
    }
  } catch (e) {
    console.error('[GoogleMap] fitBounds failed:', e)
  }
}

// 更新实时轨迹最新点标记
function updateLatestPointMarker() {
  if (!latestPointMarker) return

  if (props.latestPointIndex === null || props.latestPointIndex === undefined) {
    latestPointMarker.setMap(null)
    return
  }

  // 如果还没绘制轨迹（trackPoints 为空），等待绘制完成
  if (!trackPoints.length) {
    nextTick(() => updateLatestPointMarker())
    return
  }

  const index = props.latestPointIndex
  if (index < 0 || index >= trackPoints.length) {
    latestPointMarker.setMap(null)
    return
  }

  const point = trackPoints[index]
  const position = trackPath[index]
  if (!point || !position || !googleMapInstance) {
    latestPointMarker.setMap(null)
    return
  }

  latestPointMarker.setPosition(position)
  latestPointMarker.setMap(googleMapInstance)
}

// 监听最新点索引变化
watch(() => props.latestPointIndex, () => {
  updateLatestPointMarker()
})

// 监听外部指定的高亮点索引（用于指针同步）
watch(() => props.highlightPointIndex, (newIndex) => {
  if (newIndex === undefined || newIndex === null || !props.tracks || props.tracks.length === 0) {
    hideMarker()
    return
  }

  const track = props.tracks[0]
  if (!track || !track.points || newIndex >= track.points.length) {
    hideMarker()
    return
  }

  const point = track.points[newIndex]
  if (!point) {
    hideMarker()
    return
  }

  // 计算位置（WGS84）
  const position = getWGS84Coords(point)
  if (!position) {
    hideMarker()
    return
  }

  updateMarker({ point, index: newIndex, position })
})

// 暴露方法给父组件
defineExpose({
  highlightPoint,
  hideMarker,
  resize,
  fitBounds,
  fitToBounds,
  getMapElement: () => mapContainer.value || null,
  getMapInstance: () => googleMapInstance,
  // Google 光栅地图无 canvas 可捕获，返回 null（海报生成走 html2canvas 容器截取或后端 Playwright）
  async captureMap(): Promise<string | null> {
    return null
  },
})
</script>

<style scoped>
.google-map-container {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
}

.google-map {
  width: 100%;
  height: 100%;
}

/* 自定义 tooltip */
.custom-tooltip {
  position: absolute;
  display: none;
  pointer-events: none;
  z-index: 1000;
}

/* 道路标志 SVG 行内显示 */
:deep(.road-sign-inline) {
  display: inline-flex;
  align-items: center;
  vertical-align: middle;
  line-height: 1;
  margin: 0 1px;
}

:deep(.road-sign-inline svg) {
  display: block;
  height: 1.4em;
  width: auto;
}
</style>
