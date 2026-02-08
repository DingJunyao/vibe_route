<template>
  <div class="bmap-container">
    <div ref="mapContainer" class="bmap"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick, watchEffect } from 'vue'
import { useConfigStore } from '@/stores/config'
import { roadSignApi } from '@/api/roadSign'
import { parseRoadNumber, type ParsedRoadNumber } from '@/utils/roadSignParser'
import { formatDistance, formatDuration } from '@/utils/format'
import { wgs84ToBd09, gcj02ToBd09, bd09ToWgs84 } from '@/utils/coordTransform'

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
  (e: 'map-click', lng: number, lat: number): void  // 地图点击事件（用于添加控制点）
}>()

interface Track {
  id: number
  points: Point[]
  name?: string
  start_time?: string | null
  end_time?: string | null
  distance?: number
  duration?: number
}

// 自定义覆盖层类型（用于绘制路径模式的控制点和曲线）
interface CustomOverlay {
  type: 'marker' | 'polyline'
  position?: [number, number]  // [lat, lng] for marker
  positions?: [number, number][]  // [[lat, lng], ...] for polyline
  positions_gcj02?: [number, number][]  // GCJ02 坐标（高德、腾讯）
  positions_bd09?: [number, number][]  // BD09 坐标（百度）
  icon?: {
    type: 'circle'
    radius?: number
    fillColor?: string
    fillOpacity?: number
    strokeColor?: string
    strokeWidth?: number
  }
  label?: string
  color?: string
  weight?: number
  opacity?: number
  dashArray?: string
  // 多坐标系支持（用于标记）
  latitude_wgs84?: number
  longitude_wgs84?: number
  latitude_gcj02?: number | null
  longitude_gcj02?: number | null
  latitude_bd09?: number | null
  longitude_bd09?: number | null
}

interface Props {
  tracks?: Track[]
  highlightTrackId?: number
  highlightSegment?: { start: number; end: number } | null
  coloredSegments?: Array<{ start: number; end: number; color?: string }> | null  // 多段彩色高亮（用于插值选择区段）
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

// 百度地图实例
const mapContainer = ref<HTMLElement>()
let BMapInstance: any = null
let polylines: any[] = []
let highlightPolyline: any = null  // 路径段高亮图层
let coloredPolylineLayers: any[] = []  // 多段彩色高亮图层（用于插值选择区段）
let mouseMarker: any = null
let customTooltip: HTMLElement | null = null  // 自定义 tooltip 元素
let currentHighlightPoint: { index: number; position: { lng: number; lat: number }; point: Point } | null = null
let trackPoints: Point[] = []
let trackPath: { lng: number; lat: number }[] = []
let latestPointMarker: any = null  // 实时轨迹最新点标记（绿色）
let latestPointMarkerAdded = false  // 标记是否已添加到地图
let lastHoverIndex = -1
let wheelEventHandler: ((e: WheelEvent) => void) | null = null  // 滚轮事件处理器引用
let customOverlayMarkers: any[] = []  // 自定义覆盖层标记（用于绘制路径模式）
let customOverlayPolylines: any[] = []  // 自定义覆盖层折线（用于绘制路径模式）
let hasAutoFocused = false  // 标记是否已自动聚焦过（避免用户编辑时重复聚焦）
// home 模式：按轨迹分开存储
const tracksData = new Map<number, { points: Point[]; path: { lng: number; lat: number }[]; track: Track }>()

// 道路标志 SVG 缓存
const roadSignSvgCache = new Map<string, string>()
const loadingSigns = new Set<string>()
let currentTooltipPoint: Point | null = null  // 当前 tooltip 显示的点（用于异步更新）

// 初始化
async function init() {
  // 等待配置加载
  if (!configStore.config) {
    await configStore.fetchConfig()
  }

  await initMap()
}

// 判断是否使用 Legacy 版本（非 WebGL）
const isLegacyMode = computed(() => props.defaultLayerId === 'baidu_legacy')

// 获取当前使用的百度地图 API 命名空间（GL 或 Legacy）
const BMapAPI = computed(() => {
  return isLegacyMode.value ? (window as any).BMap : (window as any).BMapGL
})

// 辅助函数：创建 Point 对象（兼容两个版本）
function createPoint(lng: number, lat: number): any {
  const BMapClass = isLegacyMode.value ? (window as any).BMap : (window as any).BMapGL
  return new BMapClass.Point(lng, lat)
}

// 辅助函数：创建 Polyline 对象（兼容两个版本）
function createPolyline(points: any[], options: any): any {
  const BMapClass = isLegacyMode.value ? (window as any).BMap : (window as any).BMapGL
  console.log('[BMap] createPolyline - options:', options)
  const polyline = new BMapClass.Polyline(points, options)
  console.log('[BMap] createPolyline - 创建后，获取颜色:', polyline.getStrokeColor?.() || 'N/A')
  return polyline
}

// 加载百度地图 JS API（支持 GL 版本和 Legacy 版本）
async function loadBMapScript(): Promise<void> {
  return new Promise((resolve, reject) => {
    const useLegacy = isLegacyMode.value

    // 检查对应的 API 是否已加载
    if (useLegacy && (window as any).BMap) {
      resolve()
      return
    }
    if (!useLegacy && (window as any).BMapGL) {
      resolve()
      return
    }

    const layerConfig = configStore.getMapLayerById(useLegacy ? 'baidu' : props.defaultLayerId || 'baidu')
    const apiKey = layerConfig?.ak || layerConfig?.api_key || ''

    if (!apiKey) {
      reject(new Error('Baidu Map API Key is required'))
      return
    }

    // 设置全局回调函数
    const callbackName = useLegacy ? 'bmapLegacyInitCallback' : 'bmapInitCallback'
    ;(window as any)[callbackName] = () => {
      resolve()
      delete (window as any)[callbackName]
    }

    const script = document.createElement('script')
    script.type = 'text/javascript'
    // Legacy 版本使用 v=3.0，GL 版本使用 type=webgl
    if (useLegacy) {
      script.src = `https://api.map.baidu.com/api?v=3.0&ak=${apiKey}&callback=${callbackName}`
      console.log('[BMap] 加载百度地图 Legacy 版本')
    } else {
      script.src = `https://api.map.baidu.com/api?v=1.0&type=webgl&ak=${apiKey}&callback=${callbackName}`
      console.log('[BMap] 加载百度地图 GL 版本')
    }
    script.onerror = () => {
      reject(new Error('Failed to load Baidu Map API'))
      delete (window as any)[callbackName]
    }
    document.head.appendChild(script)
  })
}

// 计算两点距离
function distance(p1: [number, number], p2: [number, number]): number {
  const dx = p1[0] - p2[0]
  const dy = p1[1] - p2[1]
  return Math.sqrt(dx * dx + dy * dy)
}

// 计算点到线段的最近点
function closestPointOnSegment(p: [number, number], v: [number, number], w: [number, number]): [number, number] {
  const l2 = (v[0] - w[0]) ** 2 + (v[1] - w[1]) ** 2
  if (l2 === 0) return v

  let t = ((p[0] - w[0]) * (v[0] - w[0]) + (p[1] - w[1]) * (v[1] - w[1])) / l2
  t = Math.max(0, Math.min(1, t))

  return [
    w[0] + t * (v[0] - w[0]),
    w[1] + t * (v[1] - w[1]),
  ]
}

// 创建自定义覆盖物类（蓝色圆点标记）- 支持两个版本
function createMouseMarkerOverlay() {
  const useLegacy = isLegacyMode.value
  const BMapClass = useLegacy ? (window as any).BMap : (window as any).BMapGL

  class MouseMarkerOverlay extends BMapClass.Overlay {
    private point: any = null
    private element: HTMLElement | null = null
    private map: any = null
    private _mapMoveHandler: any = null

    constructor(point: any) {
      super()
      this.point = point
    }

    initialize(map: any): HTMLElement {
      this.map = map

      this.element = document.createElement('div')
      this.element.style.cssText = `
        width: 12px;
        height: 12px;
        background: #409eff;
        border: 2px solid #fff;
        border-radius: 50%;
        box-shadow: 0 0 4px rgba(0, 0, 0, 0.3);
        position: absolute;
        transform: translate(-50%, -50%);
        pointer-events: none;
      `

      map.getPanes().floatPane.appendChild(this.element)

      this._mapMoveHandler = () => this.draw()
      map.addEventListener('moveend', this._mapMoveHandler)
      map.addEventListener('zoomend', this._mapMoveHandler)

      return this.element
    }

    draw() {
      if (!this.element || !this.point || !this.map) return

      // Legacy 版本使用 pointToPixel，GL 版本使用 pointToOverlayPixel
      const position = this.map.pointToPixel
        ? this.map.pointToPixel(this.point)
        : this.map.pointToOverlayPixel(this.point)
      if (position) {
        this.element.style.left = position.x + 'px'
        this.element.style.top = position.y + 'px'
      }
    }

    setPosition(point: any) {
      this.point = point
      this.draw()
    }

    remove() {
      if (this.element && this.element.parentNode) {
        this.element.parentNode.removeChild(this.element)
      }

      if (this.map && this._mapMoveHandler) {
        this.map.removeEventListener('moveend', this._mapMoveHandler)
        this.map.removeEventListener('zoomend', this._mapMoveHandler)
      }

      this.element = null
      this.map = null
      this._mapMoveHandler = null
    }
  }

  return MouseMarkerOverlay
}

// 创建绿色自定义覆盖物类（用于实时轨迹最新点）- 支持两个版本
function createLatestPointMarkerOverlay() {
  const useLegacy = isLegacyMode.value
  const BMapClass = useLegacy ? (window as any).BMap : (window as any).BMapGL

  class LatestPointMarkerOverlay extends BMapClass.Overlay {
    private point: any = null
    private element: HTMLElement | null = null
    private map: any = null
    private _mapMoveHandler: any = null

    constructor(point: any) {
      super()
      this.point = point
    }

    initialize(map: any): HTMLElement {
      this.map = map

      this.element = document.createElement('div')
      this.element.style.cssText = `
        width: 12px;
        height: 12px;
        background: #67c23a;
        border: 2px solid #fff;
        border-radius: 50%;
        box-shadow: 0 0 4px rgba(0, 0, 0, 0.3);
        position: absolute;
        transform: translate(-50%, -50%);
        pointer-events: none;
      `

      map.getPanes().floatPane.appendChild(this.element)

      this._mapMoveHandler = () => this.draw()
      map.addEventListener('moveend', this._mapMoveHandler)
      map.addEventListener('zoomend', this._mapMoveHandler)

      return this.element
    }

    draw() {
      if (!this.element || !this.point || !this.map) return

      // Legacy 版本使用 pointToPixel，GL 版本使用 pointToOverlayPixel
      const position = this.map.pointToPixel
        ? this.map.pointToPixel(this.point)
        : this.map.pointToOverlayPixel(this.point)
      if (position) {
        this.element.style.left = position.x + 'px'
        this.element.style.top = position.y + 'px'
      }
    }

    setPosition(point: any) {
      this.point = point
      this.draw()
    }

    remove() {
      if (this.element && this.element.parentNode) {
        this.element.parentNode.removeChild(this.element)
      }

      if (this.map && this._mapMoveHandler) {
        this.map.removeEventListener('moveend', this._mapMoveHandler)
        this.map.removeEventListener('zoomend', this._mapMoveHandler)
      }

      this.element = null
      this.map = null
      this._mapMoveHandler = null
    }
  }

  return LatestPointMarkerOverlay
}

// 创建自定义标记覆盖类（用于绘制路径模式的控制点）- 支持两个版本
function createCustomMarkerOverlay() {
  const useLegacy = isLegacyMode.value
  const BMapClass = useLegacy ? (window as any).BMap : (window as any).BMapGL

  class CustomMarkerOverlay extends BMapClass.Overlay {
    private _position: any = null
    private _div: HTMLElement | null = null
    private _radius: number = 6
    private map: any = null
    private _mapMoveHandler: any = null

    constructor(position: any, div: HTMLElement, radius: number) {
      super()
      this._position = position
      this._div = div
      this._radius = radius
    }

    initialize(map: any): HTMLElement {
      this.map = map
      map.getPanes().markerPane.appendChild(this._div!)

      this._mapMoveHandler = () => this.draw()
      map.addEventListener('moveend', this._mapMoveHandler)
      map.addEventListener('zoomend', this._mapMoveHandler)

      return this._div!
    }

    draw() {
      if (!this._div || !this._position || !this.map) return

      // Legacy 版本使用 pointToPixel，GL 版本使用 pointToOverlayPixel
      const position = this.map.pointToPixel
        ? this.map.pointToPixel(this._position)
        : this.map.pointToOverlayPixel(this._position)

      if (position) {
        this._div.style.left = (position.x - this._radius) + 'px'
        this._div.style.top = (position.y - this._radius) + 'px'
        console.log('[BMap] CustomMarkerOverlay draw:', {
          position: this._position,
          pixel: position,
          style: { left: this._div.style.left, top: this._div.style.top },
          divContent: this._div.textContent
        })
      }
    }

    remove() {
      if (this._div && this._div.parentNode) {
        this._div.parentNode.removeChild(this._div)
      }

      if (this.map && this._mapMoveHandler) {
        this.map.removeEventListener('moveend', this._mapMoveHandler)
        this.map.removeEventListener('zoomend', this._mapMoveHandler)
      }

      this._div = null
      this.map = null
      this._mapMoveHandler = null
    }
  }

  return CustomMarkerOverlay
}

// 创建鼠标位置标记
function createMouseMarker() {
  if (!BMapInstance) return

  const MouseMarkerOverlay = createMouseMarkerOverlay()
  mouseMarker = new MouseMarkerOverlay(createPoint(0, 0))
}

// 创建最新点标记
function createLatestPointMarker() {
  if (!BMapInstance) return

  const LatestPointMarkerOverlay = createLatestPointMarkerOverlay()
  latestPointMarker = new LatestPointMarkerOverlay(createPoint(0, 0))
}

// 创建自定义 tooltip 元素
function createCustomTooltip() {
  if (!mapContainer.value) return
  const tooltipDiv = document.createElement('div')
  tooltipDiv.className = 'custom-map-tooltip'
  tooltipDiv.style.cssText = `
    position: absolute;
    z-index: 1000;
    pointer-events: none;
    display: none;
  `
  mapContainer.value.appendChild(tooltipDiv)
  customTooltip = tooltipDiv

  // 监听 tooltip 点击事件（用于点击跳转）
  tooltipDiv.addEventListener('click', (e) => {
    const trackId = (e.target as HTMLElement).closest('.track-tooltip')?.getAttribute('data-track-id')
    if (trackId) {
      emit('track-click', parseInt(trackId))
    }
  })
}

// 将经纬度转换为容器像素坐标
function lngLatToContainerPoint(lng: number, lat: number): { x: number; y: number } | null {
  if (!BMapInstance || !mapContainer.value) return null

  const point = createPoint(lng, lat)
  // Legacy 版本使用 pointToPixel，GL 版本使用 pointToOverlayPixel
  const pixel = BMapInstance.pointToPixel ? BMapInstance.pointToPixel(point) : BMapInstance.pointToOverlayPixel(point)

  if (!pixel) return null

  // 获取容器的位置信息
  const containerRect = mapContainer.value.getBoundingClientRect()

  // 计算相对于容器的坐标
  return {
    x: pixel.x,
    y: pixel.y,
  }
}

// 更新自定义 tooltip 的位置和内容
function updateCustomTooltip(content: string, pointPixel: { x: number; y: number }, containerSize: { x: number; y: number }) {
  if (!customTooltip) return
  const tooltip = customTooltip
  tooltip.innerHTML = content
  tooltip.style.display = 'block'

  const tooltipRect = tooltip.getBoundingClientRect()
  const tooltipWidth = tooltipRect.width
  const tooltipHeight = tooltipRect.height
  const padding = 10

  let positionX = pointPixel.x
  let positionY = pointPixel.y - tooltipHeight - 10  // 默认显示在点上方

  // 检查上方空间是否足够
  if (pointPixel.y - tooltipHeight < padding) {
    if (pointPixel.y + tooltipHeight + 10 < containerSize.y - padding) {
      positionY = pointPixel.y + 10  // 显示在点下方
    }
  }

  // 检查左右空间
  if (pointPixel.x - tooltipWidth / 2 < padding) {
    positionX = padding + tooltipWidth / 2
  } else if (pointPixel.x + tooltipWidth / 2 > containerSize.x - padding) {
    positionX = containerSize.x - padding - tooltipWidth / 2
  }

  tooltip.style.left = `${positionX - tooltipWidth / 2}px`
  tooltip.style.top = `${positionY}px`
}

// 显示 tooltip（使用自定义 HTML 元素）
function showTooltip(nearestIndex: number, point: Point, position: { lng: number; lat: number }) {
  if (!BMapInstance || !customTooltip || !mapContainer.value) return

  // 保存当前显示的点（用于异步更新）
  currentTooltipPoint = point

  const timeStr = point.time ? new Date(point.time).toLocaleTimeString('zh-CN') : '-'
  const elevation = point.elevation != null ? `${point.elevation.toFixed(1)} m` : '-'
  const speed = point.speed != null ? `${(point.speed * 3.6).toFixed(1)} km/h` : '-'
  const locationResult = formatLocationInfo(point)

  const content = `
    <div style="padding: 8px 12px; background: rgba(255, 255, 255, 0.95); border-radius: 6px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15); font-size: 12px; line-height: 1.6; pointer-events: auto;">
      <div style="font-weight: bold; color: #333; margin-bottom: 4px;">点 #${nearestIndex}</div>
      ${locationResult.html ? `<div style="color: #666;">${locationResult.html}</div>` : ''}
      <div style="color: #666;">时间: ${timeStr}</div>
      <div style="color: #666;">速度: ${speed}</div>
      <div style="color: #666;">海拔: ${elevation}</div>
    </div>
  `

  // 保存当前高亮的点信息
  currentHighlightPoint = { index: nearestIndex, position, point }

  // 计算点的屏幕坐标
  const pointPixel = lngLatToContainerPoint(position.lng, position.lat)
  if (pointPixel) {
    const containerSize = { x: mapContainer.value.clientWidth, y: mapContainer.value.clientHeight }
    updateCustomTooltip(content, pointPixel, containerSize)
  }

  // 异步加载道路标志 SVG
  if (locationResult.needLoad.length > 0) {
    nextTick(async () => {
      const loaded = await loadRoadSignsForTooltip(locationResult.needLoad)
      if (loaded && currentTooltipPoint === point) {
        showTooltip(nearestIndex, point, position)
      }
    })
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

  if (!BMapInstance || !mouseMarker || !point || !position) return

  // Legacy mode handled by BMapAPI

  // 检查点是否在视野内，如果不在则平移地图到该点
  const bounds = BMapInstance.getBounds()
  const pointBMapPoint = createPoint(position.lng, position.lat)
  if (bounds && !bounds.containsPoint(pointBMapPoint)) {
    BMapInstance.panTo(pointBMapPoint)
  }

  // 先移除旧覆盖物（如果存在）
  try {
    BMapInstance.removeOverlay(mouseMarker)
  } catch (e) {
    // ignore
  }

  // 创建新的覆盖物实例
  const MouseMarkerOverlay = createMouseMarkerOverlay()
  mouseMarker = new MouseMarkerOverlay(createPoint(position.lng, position.lat))
  BMapInstance.addOverlay(mouseMarker)

  showTooltip(index, point, position)
}

// 隐藏标记
function hideMarker() {
  if (lastHoverIndex === -1) return

  lastHoverIndex = -1
  currentHighlightPoint = null
  currentTooltipPoint = null

  if (mouseMarker && BMapInstance) {
    try {
      BMapInstance.removeOverlay(mouseMarker)
    } catch (e) {
      // ignore
    }
  }

  // 隐藏自定义 tooltip
  if (customTooltip) {
    customTooltip.style.display = 'none'
  }

  if (props.mode === 'home') {
    emit('track-hover', null)
  } else {
    emit('point-hover', null, -1)
  }
}

// 初始化地图
async function initMap() {
  console.log('[BMap] initMap 开始 - customOverlays:', props.customOverlays?.length || 0)
  if (!mapContainer.value) return

  try {
    await loadBMapScript()

    const useLegacy = isLegacyMode.value
    // Legacy mode handled by BMapAPI
    const BMapLegacy = (window as any).BMap

    // 创建地图实例
    if (useLegacy) {
      // Legacy 版本（非 WebGL）
      // 检查 map-only 模式下的容器尺寸
      const isMapOnlyMode = window.location.pathname.includes('/map-only')
      if (isMapOnlyMode) {
        const containerRect = mapContainer.value.getBoundingClientRect()
        console.log('[BMap] Legacy 地图初始化 - map-only 模式', {
          clientWidth: mapContainer.value.clientWidth,
          clientHeight: mapContainer.value.clientHeight,
          getBoundingClientRect: `${containerRect.width.toFixed(0)}x${containerRect.height.toFixed(0)}`,
          offsetWidth: mapContainer.value.offsetWidth,
          offsetHeight: mapContainer.value.offsetHeight
        })
      }

      BMapInstance = new BMapLegacy.Map(mapContainer.value)
      const point = new BMapLegacy.Point(116.404, 39.915)
      BMapInstance.centerAndZoom(point, 12)

      // 启用滚轮缩放（Legacy 版本）
      BMapInstance.enableScrollWheelZoom(true)

      // 添加缩放和比例尺控件（Legacy v3.0 使用 NavigationControl）
      BMapInstance.addControl(new BMapLegacy.NavigationControl())
      BMapInstance.addControl(new BMapLegacy.ScaleControl())

      // 启用双击缩放
      BMapInstance.enableDoubleClickZoom()

      // 启用键盘操作
      BMapInstance.enableKeyboard()

      console.log('[BMap] Legacy 地图初始化完成')
    } else {
      // GL 版本（WebGL）
      BMapInstance = new BMapAPI.value.Map(mapContainer.value, {
        enableDblclickZoom: true,
        enableMapClick: false,
        enableRotate: false,
        enableTilt: false,
      })
      const point = createPoint(116.404, 39.915)
      BMapInstance.centerAndZoom(point, 12)
      BMapInstance.enableScrollWheelZoom(true)

      // 添加缩放和比例尺控件
      const zoomCtrl = new BMapAPI.value.ZoomControl()
      BMapInstance.addControl(zoomCtrl)
      const scaleCtrl = new BMapAPI.value.ScaleControl()
      BMapInstance.addControl(scaleCtrl)
      console.log('[BMap] GL 地图初始化完成')
    }

    // 创建标记和自定义 tooltip
    createMouseMarker()
    createLatestPointMarker()
    createCustomTooltip()

    // 监听地图移动事件，在地图平移时更新 tooltip 位置
    BMapInstance.addEventListener('moveend', () => {
      if (currentHighlightPoint && customTooltip && mapContainer.value) {
        const pointPixel = lngLatToContainerPoint(currentHighlightPoint.position.lng, currentHighlightPoint.position.lat)
        if (pointPixel) {
          const timeStr = currentHighlightPoint.point.time ? new Date(currentHighlightPoint.point.time).toLocaleTimeString('zh-CN') : '-'
          const elevation = currentHighlightPoint.point.elevation != null ? `${currentHighlightPoint.point.elevation.toFixed(1)} m` : '-'
          const speed = currentHighlightPoint.point.speed != null ? `${(currentHighlightPoint.point.speed * 3.6).toFixed(1)} km/h` : '-'
          const locationResult = formatLocationInfo(currentHighlightPoint.point)

          const content = `
            <div style="padding: 8px 12px; background: rgba(255, 255, 255, 0.95); border-radius: 6px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15); font-size: 12px; line-height: 1.6; pointer-events: auto;">
              <div style="font-weight: bold; color: #333; margin-bottom: 4px;">点 #${currentHighlightPoint.index}</div>
              ${locationResult.html ? `<div style="color: #666;">${locationResult.html}</div>` : ''}
              <div style="color: #666;">时间: ${timeStr}</div>
              <div style="color: #666;">速度: ${speed}</div>
              <div style="color: #666;">海拔: ${elevation}</div>
            </div>
          `

          const containerSize = { x: mapContainer.value.clientWidth, y: mapContainer.value.clientHeight }
          updateCustomTooltip(content, pointPixel, containerSize)
        }
      }

      // 拖动结束日志
      const center = BMapInstance.getCenter()
      const zoom = BMapInstance.getZoom()
      console.log('[BMap] 拖动结束:', {
        缩放级别: zoom,
        中心点: `${center.lng.toFixed(4)}, ${center.lat.toFixed(4)}`
      })
    })

    // 监听缩放结束事件（鼠标滚轮缩放）
    BMapInstance.addEventListener('zoomend', () => {
      const center = BMapInstance.getCenter()
      const zoom = BMapInstance.getZoom()
      const bounds = BMapInstance.getBounds()
      // Legacy 版本使用 getSouthWest()/getNorthEast() 方法
      const sw = bounds.getSouthWest ? bounds.getSouthWest() : bounds.sw
      const ne = bounds.getNorthEast ? bounds.getNorthEast() : bounds.ne
      console.log('[BMap] 缩放结束:', {
        缩放级别: zoom,
        中心点: `${center.lng.toFixed(4)}, ${center.lat.toFixed(4)}`,
        边界: {
          sw: `${sw.lng.toFixed(4)}, ${sw.lat.toFixed(4)}`,
          ne: `${ne.lng.toFixed(4)}, ${ne.lat.toFixed(4)}`
        }
      })
    })

    // 统一的鼠标处理函数
    const handleMouseMove = (e: any) => {
      // 百度地图事件对象可能有多种属性名，尝试不同的方式获取坐标
      let lng: number | undefined
      let lat: number | undefined

      if (e.latLng) {
        // 百度地图 BMapGL 事件对象
        lng = e.latLng.lng
        lat = e.latLng.lat
      } else if (e.latlng) {
        // Leaflet 风格
        lng = e.latlng.lng
        lat = e.latlng.lat
      } else if (e.point) {
        // 百度地图可能使用 point
        lng = e.point.lng
        lat = e.point.lat
      } else if (e.lnglat) {
        // 高德风格
        lng = e.lnglat.lng
        lat = e.lnglat.lat
      }

      if (lng === undefined || lat === undefined) return

      const mouseLngLat: [number, number] = [lng, lat]

      if (props.mode === 'home') {
        handleHomeModeMouseMove(mouseLngLat)
      } else {
        handleDetailModeMouseMove(mouseLngLat)
      }
    }

    // detail 模式：显示最近的点信息
    const handleDetailModeMouseMove = (mouseLngLat: [number, number]) => {
      if (trackPath.length < 2 || !BMapInstance) return

      const zoom = BMapInstance.getZoom()
      const dynamicDistance = Math.pow(2, 12 - zoom) * 0.008

      let minDistance = Infinity
      let nearestIndex = -1
      let nearestPosition: { lng: number; lat: number } = { lng: 0, lat: 0 }

      // 快速查找最近的点
      for (let i = 0; i < trackPath.length - 1; i++) {
        const p1: [number, number] = [trackPath[i].lng, trackPath[i].lat]
        const p2: [number, number] = [trackPath[i + 1].lng, trackPath[i + 1].lat]
        const closest = closestPointOnSegment(mouseLngLat, p1, p2)
        const dist = distance(mouseLngLat, closest)

        if (dist < minDistance) {
          minDistance = dist
          nearestPosition = { lng: closest[0], lat: closest[1] }
          const distToP1 = distance(closest, p1)
          const distToP2 = distance(closest, p2)
          nearestIndex = distToP1 < distToP2 ? i : i + 1
        }
      }

      const triggered = minDistance < dynamicDistance

      // 更新或隐藏标记
      if (triggered && nearestIndex >= 0 && nearestIndex < trackPoints.length) {
        const point = trackPoints[nearestIndex]

        // 先移除旧覆盖物
        if (mouseMarker) {
          try {
            BMapInstance.removeOverlay(mouseMarker)
          } catch (e) {
            // ignore
          }
        }

        // 创建新覆盖物实例并添加到地图
        const MouseMarkerOverlay = createMouseMarkerOverlay()
        mouseMarker = new MouseMarkerOverlay(createPoint(nearestPosition.lng, nearestPosition.lat))
        BMapInstance.addOverlay(mouseMarker)

        // 显示 tooltip（每次创建新实例）
        showTooltip(nearestIndex, point, nearestPosition)

        // 如果点的索引改变了，发射事件
        if (nearestIndex !== lastHoverIndex) {
          lastHoverIndex = nearestIndex
          emit('point-hover', point, nearestIndex)
        }
      } else {
        hideMarker()
      }
    }

    // home 模式：显示最近的轨迹信息
    const handleHomeModeMouseMove = (mouseLngLat: [number, number]) => {
      if (!BMapInstance) return

      const zoom = BMapInstance.getZoom()
      const dynamicDistance = Math.pow(2, 12 - zoom) * 0.008

      let minDistance = Infinity
      let nearestTrackId: number | null = null
      let nearestPosition: { lng: number; lat: number } = { lng: 0, lat: 0 }

      // 遍历所有轨迹，找到最近的轨迹
      for (const [trackId, data] of tracksData) {
        if (data.path.length < 2) continue

        for (let i = 0; i < data.path.length - 1; i++) {
          const p1: [number, number] = [data.path[i].lng, data.path[i].lat]
          const p2: [number, number] = [data.path[i + 1].lng, data.path[i + 1].lat]
          const closest = closestPointOnSegment(mouseLngLat, p1, p2)
          const dist = distance(mouseLngLat, closest)

          if (dist < minDistance) {
            minDistance = dist
            nearestPosition = { lng: closest[0], lat: closest[1] }
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

        // Legacy mode handled by BMapAPI

        // 先移除旧覆盖物
        if (mouseMarker) {
          try {
            BMapInstance.removeOverlay(mouseMarker)
          } catch (e) {
            // ignore
          }
        }

        // 创建新覆盖物实例并添加到地图
        const MouseMarkerOverlay = createMouseMarkerOverlay()
        mouseMarker = new MouseMarkerOverlay(createPoint(nearestPosition.lng, nearestPosition.lat))
        BMapInstance.addOverlay(mouseMarker)

        // 格式化时间和里程
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

        const content = `
          <div class="track-tooltip" data-track-id="${track.id}" style="padding: 8px 12px; background: rgba(255, 255, 255, 0.95); border-radius: 6px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15); font-size: 12px; line-height: 1.6; cursor: pointer; pointer-events: auto;">
            <div style="font-weight: bold; color: #333; margin-bottom: 4px;">${track.name || '未命名轨迹'}</div>
            <div style="color: #666;">时间: ${formatTimeRange()}</div>
            <div style="color: #666;">里程: ${formatDistance(track.distance)}</div>
            <div style="color: #666;">历时: ${formatDuration(track.duration)}</div>
            ${isMobile ? '<div style="font-size: 10px; color: #409eff; margin-top: 4px;">点击查看详情</div>' : ''}
          </div>
        `

        // 使用自定义 tooltip
        if (customTooltip && mapContainer.value) {
          const pointPixel = lngLatToContainerPoint(nearestPosition.lng, nearestPosition.lat)
          if (pointPixel) {
            const containerSize = { x: mapContainer.value.clientWidth, y: mapContainer.value.clientHeight }
            updateCustomTooltip(content, pointPixel, containerSize)
          }
        }

        // 发射事件
        emit('track-hover', nearestTrackId)
      } else {
        hideMarker()
      }
    }

    // 百度地图 mousemove 监听
    BMapInstance.addEventListener('mousemove', handleMouseMove)

    // 定义点击处理函数（绘制路径模式和移动端都需要）
    const handleMapClick = (e: any) => {
      console.log('[BMap] handleMapClick - 触发点击事件:', e)

      // 绘制路径模式：直接发射点击事件（转换为 WGS84）
      if (props.disablePointHover) {
        let lng: number | undefined
        let lat: number | undefined

        if (e.latLng) {
          lng = e.latLng.lng
          lat = e.latLng.lat
        } else if (e.latlng) {
          lng = e.latlng.lng
          lat = e.latlng.lat
        } else if (e.point) {
          lng = e.point.lng
          lat = e.point.lat
        } else if (e.lnglat) {
          lng = e.lnglat.lng
          lat = e.lnglat.lat
        }

        if (lng !== undefined && lat !== undefined) {
          // 百度地图使用 BD09 坐标，需要转换为 WGS84
          const [wgsLng, wgsLat] = bd09ToWgs84(lng, lat)
          console.log('[BMap] handleMapClick - 绘制路径模式，发射 map-click:', wgsLng, wgsLat)
          emit('map-click', wgsLng, wgsLat)
        } else {
          console.warn('[BMap] handleMapClick - 无法获取坐标:', e)
        }
        return
      }

      // 移动端：点击地图显示轨迹信息
      const isMobile = window.innerWidth <= 1366
      if (!isMobile) return  // 桌面端不处理点击显示信息

      // 百度地图事件对象可能有多种属性名，尝试不同的方式获取坐标
      let lng: number | undefined
      let lat: number | undefined

      if (e.latLng) {
        lng = e.latLng.lng
        lat = e.latLng.lat
      } else if (e.latlng) {
        lng = e.latlng.lng
        lat = e.latlng.lat
      } else if (e.point) {
        lng = e.point.lng
        lat = e.point.lat
      } else if (e.lnglat) {
        lng = e.lnglat.lng
        lat = e.lnglat.lat
      }

      if (lng === undefined || lat === undefined) return

      // 根据模式处理不同的逻辑
      if (props.mode === 'home') {
        // home 模式：显示轨迹信息
        if (tracksData.size === 0) {
          hideMarker()
          return
        }

        const zoom = BMapInstance.getZoom()
        const dynamicDistance = Math.pow(2, 12 - zoom) * 0.008

        let minDistance = Infinity
        let nearestTrackId: number | null = null
        let nearestPosition: { lng: number; lat: number } = { lng: 0, lat: 0 }

        // 遍历所有轨迹，找到最近的轨迹
        for (const [trackId, data] of tracksData) {
          if (data.path.length < 2) continue

          for (let i = 0; i < data.path.length - 1; i++) {
            const p1: [number, number] = [data.path[i].lng, data.path[i].lat]
            const p2: [number, number] = [data.path[i + 1].lng, data.path[i + 1].lat]
            const closest = closestPointOnSegment([lng, lat], p1, p2)
            const dist = distance([lng, lat], closest)

            if (dist < minDistance) {
              minDistance = dist
              nearestPosition = { lng: closest[0], lat: closest[1] }
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

          // 先移除旧覆盖物
          if (mouseMarker) {
            try {
              BMapInstance.removeOverlay(mouseMarker)
            } catch (e) {
              // ignore
            }
          }

          // 创建新覆盖物实例并添加到地图
          const MouseMarkerOverlay = createMouseMarkerOverlay()
          mouseMarker = new MouseMarkerOverlay(createPoint(nearestPosition.lng, nearestPosition.lat))
          BMapInstance.addOverlay(mouseMarker)

          // 格式化时间和里程
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

          const formatDistance = (meters: number | undefined) => {
            if (meters === undefined) return '-'
            if (meters < 1000) return `${meters.toFixed(1)} m`
            return `${(meters / 1000).toFixed(2)} km`
          }

          const formatDuration = (seconds: number | undefined) => {
            if (seconds === undefined) return '-'
            const hours = Math.floor(seconds / 3600)
            const minutes = Math.floor((seconds % 3600) / 60)
            if (hours > 0) {
              return `${hours}小时${minutes}分钟`
            }
            return `${minutes}分钟`
          }

          const content = `
            <div class="track-tooltip" data-track-id="${track.id}" style="padding: 8px 12px; background: rgba(255, 255, 255, 0.95); border-radius: 6px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15); font-size: 12px; line-height: 1.6; cursor: pointer; pointer-events: auto;">
              <div style="font-weight: bold; color: #333; margin-bottom: 4px;">${track.name || '未命名轨迹'}</div>
              <div style="color: #666;">时间: ${formatTimeRange()}</div>
              <div style="color: #666;">里程: ${formatDistance(track.distance)}</div>
              <div style="color: #666;">历时: ${formatDuration(track.duration)}</div>
              <div style="font-size: 10px; color: #409eff; margin-top: 4px;">点击查看详情</div>
            </div>
          `

          // 使用自定义 tooltip
          if (customTooltip && mapContainer.value) {
            const pointPixel = lngLatToContainerPoint(nearestPosition.lng, nearestPosition.lat)
            if (pointPixel) {
              const containerSize = { x: mapContainer.value.clientWidth, y: mapContainer.value.clientHeight }
              updateCustomTooltip(content, pointPixel, containerSize)
            }
          }

          // 发射事件
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

        const zoom = BMapInstance.getZoom()
        const dynamicDistance = Math.pow(2, 12 - zoom) * 0.008

        let minDistance = Infinity
        let nearestIndex = -1
        let nearestPosition: { lng: number; lat: number } = { lng: 0, lat: 0 }

        // 查找最近的点
        for (let i = 0; i < trackPath.length - 1; i++) {
          const p1: [number, number] = [trackPath[i].lng, trackPath[i].lat]
          const p2: [number, number] = [trackPath[i + 1].lng, trackPath[i + 1].lat]
          const closest = closestPointOnSegment([lng, lat], p1, p2)
          const dist = distance([lng, lat], closest)

          if (dist < minDistance) {
            minDistance = dist
            nearestPosition = { lng: closest[0], lat: closest[1] }
            const distToP1 = distance(closest, p1)
            const distToP2 = distance(closest, p2)
            nearestIndex = distToP1 < distToP2 ? i : i + 1
          }
        }

        const triggered = minDistance < dynamicDistance

        if (triggered && nearestIndex >= 0 && nearestIndex < trackPoints.length) {
          const point = trackPoints[nearestIndex]

          // 先移除旧覆盖物
          if (mouseMarker) {
            try {
              BMapInstance.removeOverlay(mouseMarker)
            } catch (e) {
              // ignore
            }
          }

          // 创建新覆盖物实例并添加到地图
          const MouseMarkerOverlay = createMouseMarkerOverlay()
          mouseMarker = new MouseMarkerOverlay(createPoint(nearestPosition.lng, nearestPosition.lat))
          BMapInstance.addOverlay(mouseMarker)

          // 显示 tooltip（每次创建新实例）
          showTooltip(nearestIndex, point, nearestPosition)

          lastHoverIndex = nearestIndex
          emit('point-hover', point, nearestIndex)
        } else {
          hideMarker()
        }
      }
    }

    // 注册点击事件监听器
    BMapInstance.addEventListener('click', handleMapClick)
    console.log('[BMap] 已注册点击事件监听器（绘制路径模式和移动端）')

    // Legacy 版本：手动添加滚轮缩放支持
    if (isLegacyMode.value && mapContainer.value) {
      let wheelTimeout: any = null
      wheelEventHandler = (e: WheelEvent) => {
        if (!BMapInstance) return
        e.preventDefault()

        // 清除之前的定时器
        if (wheelTimeout) {
          clearTimeout(wheelTimeout)
        }

        // 计算缩放方向
        const delta = e.deltaY
        const currentZoom = BMapInstance.getZoom()

        // 设置新的缩放级别（延迟执行，避免频繁调用）
        wheelTimeout = setTimeout(() => {
          if (delta < 0) {
            // 向上滚动，放大
            BMapInstance.setZoom(Math.min(18, currentZoom + 1))
          } else {
            // 向下滚动，缩小
            BMapInstance.setZoom(Math.max(3, currentZoom - 1))
          }
        }, 50)

        console.log('[BMap] 滚轮事件:', delta, '当前缩放:', currentZoom)
      }
      mapContainer.value.addEventListener('wheel', wheelEventHandler, { passive: false })

      console.log('[BMap] Legacy 版本已添加滚轮缩放支持')
    }

    // 绘制轨迹
    drawTracks()
    // 绘制自定义覆盖层（用于绘制路径模式）
    // 延迟调用，确保 customOverlays prop 已传递
    // 百度地图脚本加载需要时间，可能需要多次尝试
    nextTick(() => {
      setTimeout(() => {
        console.log('[BMap] initMap - 延迟后检查 customOverlays:', props.customOverlays?.length || 0)
        drawCustomOverlays()

        // 绘制路径模式：仅在首次加载时自动聚焦到覆盖物区域
        if (props.disablePointHover && props.customOverlays && props.customOverlays.length > 0 && !hasAutoFocused) {
          // 计算所有标记点的边界
          let minLat = Infinity, maxLat = -Infinity, minLon = Infinity, maxLon = -Infinity
          let hasValidPoint = false

          for (const overlay of props.customOverlays) {
            if (overlay.type === 'marker') {
              let lat: number | undefined, lng: number | undefined
              // 优先使用 BD09 坐标
              if (overlay.latitude_bd09 != null && overlay.longitude_bd09 != null) {
                lat = overlay.latitude_bd09
                lng = overlay.longitude_bd09
              } else if (overlay.position) {
                // WGS84 坐标，需要转换
                const [bdLng, bdLat] = wgs84ToBd09(overlay.position[1], overlay.position[0])
                lat = bdLat
                lng = bdLng
              }

              if (lat !== undefined && lng !== undefined) {
                hasValidPoint = true
                minLat = Math.min(minLat, lat)
                maxLat = Math.max(maxLat, lat)
                minLon = Math.min(minLon, lng)
                maxLon = Math.max(maxLon, lng)
              }
            }
          }

          // 如果有有效的标记点，聚焦到它们
          if (hasValidPoint && BMapInstance) {
            const BMapClass = isLegacyMode.value ? (window as any).BMap : (window as any).BMapGL
            const boundsPoints = [
              new BMapClass.Point(minLon, minLat),
              new BMapClass.Point(maxLon, maxLat)
            ]

            // 计算合适的 padding
            const container = mapContainer.value
            let padding = 50
            if (container) {
              const size = Math.max(container.clientWidth, container.clientHeight)
              padding = Math.round(size * 0.15) // 15% padding
            }

            // 延迟执行，确保覆盖物绘制完成和地图初始化稳定
            setTimeout(() => {
              BMapInstance.setViewport(boundsPoints, {
                margins: [padding, padding, padding, padding]
              })
              console.log('[BMap] initMap - 自动聚焦到覆盖物区域')
              hasAutoFocused = true  // 标记已自动聚焦
            }, 800)
          }
        }

        // 如果仍然没有覆盖层，再次尝试
        if (!props.customOverlays || props.customOverlays.length === 0) {
          setTimeout(() => {
            console.log('[BMap] initMap - 二次检查 customOverlays:', props.customOverlays?.length || 0)
            drawCustomOverlays()
          }, 200)
        }
      }, 100)
    })
  } catch (error) {
    console.error('[BMap] Failed to initialize:', error)
  }
}

// 根据坐标系获取经纬度（BD09）
function getBD09Coords(point: Point): { lng: number; lat: number } | null {
  // 如果已有 BD09 坐标，直接使用
  if (point.latitude_bd09 !== undefined && point.longitude_bd09 !== undefined &&
      !isNaN(point.latitude_bd09) && !isNaN(point.longitude_bd09)) {
    return { lng: point.longitude_bd09, lat: point.latitude_bd09 }
  }

  // 如果有 GCJ02 坐标，转换为 BD09
  if (point.latitude_gcj02 !== undefined && point.longitude_gcj02 !== undefined &&
      !isNaN(point.latitude_gcj02) && !isNaN(point.longitude_gcj02)) {
    const [bdLng, bdLat] = gcj02ToBd09(point.longitude_gcj02, point.latitude_gcj02)
    return { lng: bdLng, lat: bdLat }
  }

  // 如果有 WGS84 坐标，转换为 BD09
  if (point.latitude_wgs84 !== undefined && point.longitude_wgs84 !== undefined &&
      !isNaN(point.latitude_wgs84) && !isNaN(point.longitude_wgs84)) {
    const [bdLng, bdLat] = wgs84ToBd09(point.longitude_wgs84, point.latitude_wgs84)
    return { lng: bdLng, lat: bdLat }
  }

  // 最后回退到原始坐标（假设是 WGS84，转换到 BD09）
  if (point.latitude !== undefined && point.longitude !== undefined &&
      !isNaN(point.latitude) && !isNaN(point.longitude)) {
    const [bdLng, bdLat] = wgs84ToBd09(point.longitude, point.latitude)
    return { lng: bdLng, lat: bdLat }
  }

  return null
}

// 绘制轨迹
function drawTracks() {
  if (!BMapInstance || !props.tracks || props.tracks.length === 0) return

  // 清除现有轨迹
  clearTracks()

  // 重置轨迹数据
  trackPoints = []
  trackPath = []
  tracksData.clear()

  // Legacy mode handled by BMapAPI
  const bounds: any[] = []

  // 调试：检查 map-only 模式
  const isMapOnlyMode = window.location.pathname.includes('/map-only')
  if (isMapOnlyMode) {
    console.log('[BMap] drawTracks - map-only 模式，开始绘制轨迹')
  }

  // 调试：记录 tracks 信息
  console.log('[BMap] drawTracks - 开始绘制, tracks 数量:', props.tracks?.length || 0)
  if (props.tracks && props.tracks.length > 0) {
    console.log('[BMap] drawTracks - 第一个 track:', {
      id: props.tracks[0].id,
      opacity: props.tracks[0].opacity,
      color: props.tracks[0].color,
      pointsCount: props.tracks[0].points?.length
    })
  }

  for (const track of props.tracks) {
    if (!track.points || track.points.length === 0) continue

    const points: any[] = []
    const trackPathData: { lng: number; lat: number }[] = []
    const trackPointsData: Point[] = []

    // 调试：记录第一个点的坐标转换
    if (isMapOnlyMode && track.points.length > 0) {
      const firstPoint = track.points[0]
      const coords = getBD09Coords(firstPoint)
      console.log('[BMap] drawTracks - 第一个点坐标转换:', {
        原始: { lng: firstPoint.longitude, lat: firstPoint.latitude },
        BD09: coords,
        has_bd09: !!(firstPoint.latitude_bd09 && firstPoint.longitude_bd09),
        has_wgs84: !!(firstPoint.latitude_wgs84 && firstPoint.longitude_wgs84)
      })
    }

    for (const point of track.points) {
      const coords = getBD09Coords(point)
      if (!coords) continue

      const { lng, lat } = coords
      points.push(createPoint(lng, lat))
      bounds.push(createPoint(lng, lat))

      // detail 模式：合并所有轨迹
      trackPoints.push(point)
      trackPath.push({ lng, lat })

      // home 模式：按轨迹分开存储
      trackPointsData.push(point)
      trackPathData.push({ lng, lat })
    }

    if (points.length === 0) continue

    // 保存轨迹数据用于 home 模式
    tracksData.set(track.id, {
      points: trackPointsData,
      path: trackPathData,
      track,
    })

    // 绘制轨迹线
    const isHighlighted = track.id === props.highlightTrackId
    // 使用 track.color 或默认红色
    const strokeColor = track.color || '#FF0000'
    // 使用 track.opacity 或默认 0.8
    const strokeOpacity = track.opacity !== undefined ? track.opacity : 0.8
    console.log('[BMap] drawTracks - 绘制轨迹:', {
      trackId: track.id,
      trackColor: track.color,
      strokeColor,
      trackOpacity: track.opacity,
      strokeOpacity
    })
    const polyline = createPolyline(points, {
      strokeColor,
      strokeWeight: isHighlighted ? 5 : 3,
      strokeOpacity,
    })

    // 桌面端：点击轨迹直接跳转
    // Legacy 版本的事件监听方式
    if (isLegacyMode.value) {
      // Legacy 版本：使用 addEventListener
      polyline.addEventListener('click', () => {
        const isMobile = window.innerWidth <= 1366
        if (!isMobile) {
          emit('track-click', track.id)
        }
      })
    } else {
      // GL 版本
      polyline.addEventListener('click', () => {
        const isMobile = window.innerWidth <= 1366
        if (!isMobile) {
          emit('track-click', track.id)
        }
      })
    }

    BMapInstance.addOverlay(polyline)
    polylines.push(polyline)
  }

  // 绘制多段彩色高亮（插值选择区段）
  if (props.mode === 'detail' && props.coloredSegments && trackPath.length > 0) {
    for (const seg of props.coloredSegments) {
      const { start, end, color } = seg
      if (start >= 0 && end < trackPath.length && start <= end) {
        const segmentPath = trackPath.slice(start, end + 1)
        const pointPath = segmentPath.map(p => createPoint(p.lng, p.lat))
        if (pointPath.length > 0) {
          const coloredPolyline = createPolyline(pointPath, {
            strokeColor: color || '#67c23a',  // 默认绿色
            strokeWeight: 7,
            strokeOpacity: 0.9,
          })
          BMapInstance.addOverlay(coloredPolyline)
          coloredPolylineLayers.push(coloredPolyline)
        }
      }
    }
  }

  // 绘制路径段高亮（detail 模式，兼容旧逻辑）
  if (props.mode === 'detail' && props.highlightSegment && trackPath.length > 0) {
    const { start, end } = props.highlightSegment
    // 确保索引在有效范围内
    if (start >= 0 && end < trackPath.length && start <= end) {
      const segmentPath = trackPath.slice(start, end + 1)
      // 转换为 Point 对象数组（兼容 GL 和 Legacy 版本）
      const pointPath = segmentPath.map(p => createPoint(p.lng, p.lat))
      if (pointPath.length > 0) {
        highlightPolyline = createPolyline(pointPath, {
          strokeColor: '#409eff',  // 蓝色高亮
          strokeWeight: 7,
          strokeOpacity: 0.9,
        })
        BMapInstance.addOverlay(highlightPolyline)
      }
    }
  }

  // 自动适应视图（绘制路径模式下禁用，仅在非 map-only 模式下）
  if (bounds.length > 0 && !isMapOnlyMode && !props.disablePointHover) {
    // 延迟执行，确保地图已完全渲染
    setTimeout(() => {
      if (isLegacyMode.value) {
        // Legacy 版本：使用二分查找法找到合适的缩放级别
        let minLng = Infinity, maxLng = -Infinity, minLat = Infinity, maxLat = -Infinity
        for (const pt of bounds) {
          if (pt.lng < minLng) minLng = pt.lng
          if (pt.lng > maxLng) maxLng = pt.lng
          if (pt.lat < minLat) minLat = pt.lat
          if (pt.lat > maxLat) maxLat = pt.lat
        }
        const centerLng = (minLng + maxLng) / 2
        const centerLat = (minLat + maxLat) / 2

        // 先设置中心点
        BMapInstance.centerAndZoom(createPoint(centerLng, centerLat), 12)

        // 使用二分查找法找到合适的缩放级别（需要等待缩放完成）
        setTimeout(async () => {
          let low = 3, high = 18
          while (low < high) {
            const mid = Math.floor((low + high + 1) / 2)
            BMapInstance.setZoom(mid)

            // Legacy 版本需要等待缩放完成后再检查边界（使用更长的等待时间）
            await new Promise(resolve => setTimeout(resolve, 200))

            // 检查当前视野是否包含所有点
            const currentBounds = BMapInstance.getBounds()
            const sw = currentBounds.getSouthWest ? currentBounds.getSouthWest() : currentBounds.sw
            const ne = currentBounds.getNorthEast ? currentBounds.getNorthEast() : currentBounds.ne

            let allVisible = true
            for (const pt of bounds) {
              if (pt.lng < sw.lng || pt.lng > ne.lng || pt.lat < sw.lat || pt.lat > ne.lat) {
                allVisible = false
                break
              }
            }

            if (allVisible) {
              low = mid
            } else {
              high = mid - 1
            }
          }
          BMapInstance.setZoom(low)
          console.log('[BMap] drawTracks 自动适应完成，缩放级别:', low)
        }, 400)
      } else {
        // GL 版本：使用 setViewport
        BMapInstance.setViewport(bounds)
      }
    }, 300)
  }

  // 更新最新点标记
  updateLatestPointMarker()
}

// 清除轨迹
function clearTracks() {
  if (!BMapInstance) return

  polylines.forEach((polyline) => {
    try {
      BMapInstance.removeOverlay(polyline)
    } catch (e) {
      // ignore
    }
  })
  polylines = []

  // 清除路径段高亮
  if (highlightPolyline) {
    try {
      BMapInstance.removeOverlay(highlightPolyline)
    } catch (e) {
      // ignore
    }
    highlightPolyline = null
  }

  // 清除多段彩色高亮图层
  coloredPolylineLayers.forEach(polyline => {
    try {
      BMapInstance.removeOverlay(polyline)
    } catch (e) {
      // ignore
    }
  })
  coloredPolylineLayers = []
}

// 更新轨迹
function updateTracks() {
  drawTracks()
}

// 绘制自定义覆盖层（用于绘制路径模式的控制点和曲线）
function drawCustomOverlays() {
  if (!BMapInstance) {
    console.log('[BMap] drawCustomOverlays - BMapInstance 未初始化')
    return
  }

  const BMap = isLegacyMode.value ? (window as any).BMap : (window as any).BMapGL
  console.log('[BMap] drawCustomOverlays - 开始绘制，覆盖层数量:', props.customOverlays?.length || 0, 'isLegacyMode:', isLegacyMode.value)

  // 清除现有的自定义覆盖层
  customOverlayMarkers.forEach(marker => {
    try { BMapInstance.removeOverlay(marker) } catch { /* ignore */ }
  })
  customOverlayMarkers = []
  customOverlayPolylines.forEach(polyline => {
    try { BMapInstance.removeOverlay(polyline) } catch { /* ignore */ }
  })
  customOverlayPolylines = []

  if (!props.customOverlays || props.customOverlays.length === 0) {
    console.log('[BMap] drawCustomOverlays - 没有覆盖层需要绘制')
    return
  }

  // 使用工厂函数创建的自定义覆盖类
  const CustomMarkerOverlay = createCustomMarkerOverlay()

  for (const overlay of props.customOverlays) {
    if (overlay.type === 'marker') {
      // 优先使用 BD09 坐标（百度地图坐标系），否则使用 position 字段（WGS84）
      let lat: number, lng: number
      if (overlay.latitude_bd09 != null && overlay.longitude_bd09 != null) {
        lat = overlay.latitude_bd09
        lng = overlay.longitude_bd09
        console.log('[BMap] 使用 BD09 坐标:', { label: overlay.label, lat, lng })
      } else if (overlay.position) {
        [lat, lng] = overlay.position
        console.log('[BMap] 使用 position (WGS84):', { label: overlay.label, lat, lng })
      } else {
        console.log('[BMap] 跳过标记: 无有效坐标', overlay)
        continue
      }

      if (!overlay.icon) {
        console.log('[BMap] 跳过标记: 无 icon', overlay)
        continue
      }

      const radius = overlay.icon.radius || 6
      const fillColor = overlay.icon.fillColor || '#f56c6c'
      const fillOpacity = overlay.icon.fillOpacity !== undefined ? overlay.icon.fillOpacity : 0.9
      const strokeColor = overlay.icon.strokeColor || '#fff'
      const strokeWidth = overlay.icon.strokeWidth || 2

      // 创建自定义内容
      const div = document.createElement('div')
      div.style.cssText = `
        position: absolute;
        width: ${radius * 2}px;
        height: ${radius * 2}px;
        border-radius: 50%;
        background-color: ${fillColor};
        opacity: ${fillOpacity};
        border: ${strokeWidth}px solid ${strokeColor};
        box-sizing: border-box;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #fff;
        font-size: ${radius * 0.8}px;
        font-weight: bold;
      `

      if (overlay.label) {
        div.textContent = overlay.label
      }

      // 使用工厂函数创建的自定义覆盖类
      const point = new BMap.Point(lng, lat)
      console.log('[BMap] 创建标记覆盖物:', { label: overlay.label, point, radius })
      const marker = new CustomMarkerOverlay(point, div, radius)
      BMapInstance.addOverlay(marker)
      customOverlayMarkers.push(marker)
      console.log('[BMap] 标记覆盖物已添加, 当前数量:', customOverlayMarkers.length)
    } else if (overlay.type === 'polyline' && overlay.positions && overlay.positions.length > 1) {
      // 优先使用 BD09 坐标，回退到 WGS84
      const positions = overlay.positions_bd09 || overlay.positions
      const points = positions.map(([lat, lng]) => new BMap.Point(lng, lat))
      const color = overlay.color || '#409eff'
      const weight = overlay.weight || 3
      const opacity = overlay.opacity !== undefined ? overlay.opacity : 0.8
      const dashArray = overlay.dashArray

      const PolylineClass = BMap.Polyline
      const polyline = new PolylineClass(points, {
        strokeColor: color,
        strokeWeight: weight,
        strokeOpacity: opacity,
        strokeStyle: dashArray ? 'dashed' : 'solid',
      })

      BMapInstance.addOverlay(polyline)
      customOverlayPolylines.push(polyline)
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

// 监听 customOverlays 变化（用于绘制路径模式）
watch(() => props.customOverlays, (newVal) => {
  console.log('[BMap] watch customOverlays - 覆盖层数量:', newVal?.length || 0)
  drawCustomOverlays()
}, { deep: true })

// 生命周期
onMounted(async () => {
  await init()
})

// 使用 watchEffect 监听 customOverlays 变化，确保在地图初始化后也能绘制
watchEffect(() => {
  // 只在地图实例存在且 customOverlays 有数据时才绘制
  if (BMapInstance && props.customOverlays && props.customOverlays.length > 0) {
    console.log('[BMap] watchEffect - 检测到 customOverlays 变化:', props.customOverlays.length)
    drawCustomOverlays()

    // 绘制路径模式：仅在首次加载时自动聚焦到覆盖物区域
    if (props.disablePointHover && props.customOverlays.length > 0 && !hasAutoFocused) {
      // 计算所有标记点的边界
      let minLat = Infinity, maxLat = -Infinity, minLon = Infinity, maxLon = -Infinity
      let hasValidPoint = false

      for (const overlay of props.customOverlays) {
        if (overlay.type === 'marker') {
          let lat: number | undefined, lng: number | undefined
          // 优先使用 BD09 坐标
          if (overlay.latitude_bd09 != null && overlay.longitude_bd09 != null) {
            lat = overlay.latitude_bd09
            lng = overlay.longitude_bd09
          } else if (overlay.position) {
            // WGS84 坐标，需要转换
            const [bdLng, bdLat] = wgs84ToBd09(overlay.position[1], overlay.position[0])
            lat = bdLat
            lng = bdLng
          }

          if (lat !== undefined && lng !== undefined) {
            hasValidPoint = true
            minLat = Math.min(minLat, lat)
            maxLat = Math.max(maxLat, lat)
            minLon = Math.min(minLon, lng)
            maxLon = Math.max(maxLon, lng)
          }
        }
      }

      // 如果有有效的标记点，聚焦到它们
      if (hasValidPoint) {
        const BMapClass = isLegacyMode.value ? (window as any).BMap : (window as any).BMapGL
        const boundsPoints = [
          new BMapClass.Point(minLon, minLat),
          new BMapClass.Point(maxLon, maxLat)
        ]

        // 计算合适的 padding
        const container = mapContainer.value
        let padding = 50
        if (container) {
          const size = Math.max(container.clientWidth, container.clientHeight)
          padding = Math.round(size * 0.15) // 15% padding
        }

        // 延迟执行，确保覆盖物绘制完成
        setTimeout(() => {
          BMapInstance.setViewport(boundsPoints, {
            margins: [padding, padding, padding, padding]
          })
          console.log('[BMap] watchEffect - 自动聚焦到覆盖物区域')
          hasAutoFocused = true  // 标记已自动聚焦，后续不再重复
        }, 200)
      }
    }
  }
})

onUnmounted(() => {
  // 清理滚轮事件监听器
  if (wheelEventHandler && mapContainer.value) {
    mapContainer.value.removeEventListener('wheel', wheelEventHandler)
    wheelEventHandler = null
  }

  if (BMapInstance) {
    try {
      // Legacy 版本可能没有 destroy 方法，先检查
      if (typeof BMapInstance.destroy === 'function') {
        BMapInstance.destroy()
      }
    } catch (e) {
      // ignore
    }
    BMapInstance = null
  }
})

// 调整地图大小（用于响应式布局）
function resize() {
  if (BMapInstance) {
    // 百度地图会自动调整大小，这里可以调用 reset 来确保地图正确显示
    // 但为了避免改变用户当前视角，我们不做额外操作
  }
}

// 将所有轨迹居中显示（四周留指定百分比空间）
function fitBounds(paddingPercent: number = 5) {
  if (!BMapInstance) return

  // 获取当前使用的地图 API 命名空间（GL 或 Legacy）
  const BMapClass = isLegacyMode.value ? (window as any).BMap : (window as any).BMapGL

  // 计算所有轨迹的边界
  const bounds: any[] = []

  for (const track of props.tracks) {
    if (!track.points || track.points.length === 0) continue
    for (const point of track.points) {
      const coords = getBD09Coords(point)
      if (!coords) continue
      const { lng, lat } = coords
      if (!isNaN(lat) && !isNaN(lng)) {
        bounds.push(new BMapClass.Point(lng, lat))
      }
    }
  }

  if (bounds.length === 0) return

  console.log('[BMap] fitBounds - 使用 API:', isLegacyMode.value ? 'BMap (Legacy)' : 'BMapGL', '边界点数:', bounds.length, '第一个点:', bounds[0])

  try {
    // 获取容器尺寸
    const container = mapContainer.value
    if (!container) {
      // 没有容器时，使用默认方式
      if (isLegacyMode.value) {
        // Legacy 版本：计算中心点和缩放级别
        let minLng = Infinity, maxLng = -Infinity, minLat = Infinity, maxLat = -Infinity
        for (const pt of bounds) {
          if (pt.lng < minLng) minLng = pt.lng
          if (pt.lng > maxLng) maxLng = pt.lng
          if (pt.lat < minLat) minLat = pt.lat
          if (pt.lat > maxLat) maxLat = pt.lat
        }
        const centerLng = (minLng + maxLng) / 2
        const centerLat = (minLat + maxLat) / 2
        BMapInstance.centerAndZoom(new BMapClass.Point(centerLng, centerLat), 12)
      } else {
        BMapInstance.setViewport(bounds)
      }
      return
    }
    // 检查是否是 map-only 模式（通过 URL 判断）
    const isMapOnlyMode = window.location.pathname.includes('/map-only')
    const mapScale = isMapOnlyMode ? (props.mapScale || 100) : 100

    // 在 map-only 模式下，从 URL 参数读取目标尺寸（而非 clientWidth/clientHeight）
    // 因为 iframe 模式下容器使用 100vw/100vh，clientWidth 返回的值可能不正确
    let containerWidth = container.clientWidth || 800
    let containerHeight = container.clientHeight || 600
    if (isMapOnlyMode) {
      const urlParams = new URLSearchParams(window.location.search)
      const urlWidth = parseInt(urlParams.get('width') || '')
      const urlHeight = parseInt(urlParams.get('height') || '')
      if (urlWidth > 0 && urlHeight > 0) {
        containerWidth = urlWidth
        containerHeight = urlHeight
        console.log('[BMap] map-only 模式：使用 URL 参数尺寸', `${containerWidth}x${containerHeight}`)
      }
    }

    if (isLegacyMode.value) {
      // Legacy 版本：计算边界框中心点和缩放级别
      let minLng = Infinity, maxLng = -Infinity, minLat = Infinity, maxLat = -Infinity
      for (const pt of bounds) {
        if (pt.lng < minLng) minLng = pt.lng
        if (pt.lng > maxLng) maxLng = pt.lng
        if (pt.lat < minLat) minLat = pt.lat
        if (pt.lat > maxLat) maxLat = pt.lat
      }
      const centerLng = (minLng + maxLng) / 2
      const centerLat = (minLat + maxLat) / 2

      // 先设置中心点
      BMapInstance.centerAndZoom(new BMapClass.Point(centerLng, centerLat), 12)

      // 延迟确保中心点设置完成
      setTimeout(() => {
        // 计算边界框的经纬度范围
        let minLng2 = Infinity, maxLng2 = -Infinity, minLat2 = Infinity, maxLat2 = -Infinity
        for (const pt of bounds) {
          if (pt.lng < minLng2) minLng2 = pt.lng
          if (pt.lng > maxLng2) maxLng2 = pt.lng
          if (pt.lat < minLat2) minLat2 = pt.lat
          if (pt.lat > maxLat2) maxLat2 = pt.lat
        }
        const boundsLng = maxLng2 - minLng2
        const boundsLat = maxLat2 - minLat2

        // 在 map-only 模式下，通过调整 zoom 级别实现视觉缩放（而非 CSS transform）
        // 因为 CSS transform 会导致 getBoundingClientRect() 返回错误的尺寸
        const scale = isMapOnlyMode ? (mapScale / 100) : 1

        // 目标：边界框占据容器的 90%（留 10% 边距）
        // 当 scale > 1 时，目标内容尺寸变小，从而实现更高的 zoom（放大效果）
        const targetContentWidth = containerWidth * 0.9 / scale
        const targetContentHeight = containerHeight * 0.9 / scale

        // 先设置一个初始 zoom，然后测量边界框的像素尺寸，再调整
        BMapInstance.setZoom(12)

        // 等待缩放完成后进行几何调整
        setTimeout(() => {
          // 在当前 zoom 下，将边界框转换为像素
          const swPixel = BMapInstance.pointToPixel ? BMapInstance.pointToPixel(new BMapClass.Point(minLng2, minLat2)) : null
          const nePixel = BMapInstance.pointToPixel ? BMapInstance.pointToPixel(new BMapClass.Point(maxLng2, maxLat2)) : null

          if (!swPixel || !nePixel) {
            // 如果 pointToPixel 不可用，使用简单估算
            console.warn('[BMap] Legacy pointToPixel 不可用，使用估算方法')
            return
          }

          const currentPixelWidth = Math.abs(nePixel.x - swPixel.x)
          const currentPixelHeight = Math.abs(nePixel.y - swPixel.y)

          // CSS scale 会放大地图显示，但不改变容器尺寸
          // 目标：边界框在放大后占据容器 90%，即放大前应占据 90% / scale
          const targetContentWidth = containerWidth * 0.9 / scale
          const targetContentHeight = containerHeight * 0.9 / scale

          // 计算需要调整的 zoom delta
          // 如果 currentPixel < targetPixel，需要放大（delta > 0）
          // 如果 currentPixel > targetPixel，需要缩小（delta < 0）
          const widthZoomDelta = Math.log2(targetContentWidth / currentPixelWidth)
          const heightZoomDelta = Math.log2(targetContentHeight / currentPixelHeight)

          // 取较小的 delta，确保边界框完全在视野内
          const zoomDelta = Math.min(widthZoomDelta, heightZoomDelta)
          const rawZoom = 12 + zoomDelta
          let targetZoom = Math.floor(rawZoom)

          // 精细策略：当小数部分 ≥ 0.9 时，尝试 zoom+1 并验证边界框是否仍在容器 95% 内
          const fractionalPart = rawZoom - targetZoom
          if (fractionalPart >= 0.9 && targetZoom < 18) {
            // 计算在 zoom+1 下的边界框像素尺寸
            const nextZoom = targetZoom + 1
            const zoomRatio = Math.pow(2, nextZoom - 12)  // 相对于 zoom 12 的倍数
            const nextPixelWidth = currentPixelWidth * zoomRatio
            const nextPixelHeight = currentPixelHeight * zoomRatio

            // 检查边界框是否在容器的 95% 内（允许略微超出）
            const fitsWidth = nextPixelWidth <= targetContentWidth / 0.95
            const fitsHeight = nextPixelHeight <= targetContentHeight / 0.95

            if (fitsWidth && fitsHeight) {
              targetZoom = nextZoom
            }
          }

          targetZoom = Math.max(3, Math.min(18, targetZoom))

          console.log('[BMap] Legacy fitBounds 几何调整:', {
            边界框: `(${minLng2.toFixed(4)}, ${minLat2.toFixed(4)}) → (${maxLng2.toFixed(4)}, ${maxLat2.toFixed(4)})`,
            边界尺寸: `lng=${boundsLng.toFixed(4)}°, lat=${boundsLat.toFixed(4)}°`,
            当前像素: `${currentPixelWidth.toFixed(0)}x${currentPixelHeight.toFixed(0)}`,
            容器尺寸: `${containerWidth}x${containerHeight}`,
            CSS缩放: `${scale}`,
            目标内容: `${targetContentWidth.toFixed(0)}x${targetContentHeight.toFixed(0)}`,
            widthDelta: widthZoomDelta.toFixed(2),
            heightDelta: heightZoomDelta.toFixed(2),
            最终zoom: targetZoom
          })

          BMapInstance.setZoom(targetZoom)
        }, 400)
      }, 400)
    } else {
      // GL 版本：使用 setViewport
      const padding = Math.round(Math.max(containerWidth, containerHeight) * (paddingPercent / 100))
      BMapInstance.setViewport(bounds, {
        margins: [padding, padding, padding, padding]
      })
    }

    // 如果是 map-only 模式且有缩放，根据边界框几何计算目标 zoom（仅 GL 版本）
    if (!isLegacyMode.value && isMapOnlyMode && mapScale > 100 && bounds.length > 0) {
      setTimeout(() => {
        const zoomAfter = BMapInstance.getZoom()

        // 计算边界框的经纬度范围
        let minLng = Infinity, maxLng = -Infinity, minLat = Infinity, maxLat = -Infinity
        for (const pt of bounds) {
          const lng = pt.lng, lat = pt.lat
          if (lng < minLng) minLng = lng
          if (lng > maxLng) maxLng = lng
          if (lat < minLat) minLat = lat
          if (lat > maxLat) maxLat = lat
        }

        // 在当前 zoom 下，将边界框转换为像素
        const swPixel = BMapInstance.pointToPixel(new BMapClass.Point(minLng, minLat))
        const nePixel = BMapInstance.pointToPixel(new BMapClass.Point(maxLng, maxLat))
        const currentPixelWidth = Math.abs(nePixel.x - swPixel.x)
        const currentPixelHeight = Math.abs(nePixel.y - swPixel.y)

        // CSS scale 会放大地图显示，但不改变容器尺寸
        // 目标：边界框在放大后占据容器 90%，即放大前应占据 90% / scale
        const scale = mapScale / 100
        const targetContentWidth = containerWidth * 0.9 / scale
        const targetContentHeight = containerHeight * 0.9 / scale
        const widthZoomDelta = Math.log2(targetContentWidth / currentPixelWidth)
        const heightZoomDelta = Math.log2(targetContentHeight / currentPixelHeight)

        // 取较小的 delta，确保边界框完全在视野内
        const zoomDelta = Math.min(widthZoomDelta, heightZoomDelta)
        const targetZoom = Math.max(3, Math.min(20, zoomAfter + zoomDelta))

        console.log('[BMap] 几何缩放计算:', {
          边界框: `(${minLng}, ${minLat}) → (${maxLng}, ${maxLat})`,
          当前像素: `${currentPixelWidth.toFixed(0)}x${currentPixelHeight.toFixed(0)}`,
          容器尺寸: `${containerWidth}x${containerHeight}`,
          CSS缩放: `${scale}`,
          目标内容: `${targetContentWidth.toFixed(0)}x${targetContentHeight.toFixed(0)}`,
          zoomDelta: zoomDelta.toFixed(2),
          zoom: `${zoomAfter.toFixed(1)} → ${targetZoom.toFixed(1)}`
        })

        BMapInstance.setZoom(targetZoom)
      }, 500)
    }
  } catch (e) {
    console.error('[BMap] fitBounds failed:', e)
  }
}

// 根据边界框直接设置地图视野（用于聚焦到特定区段）
function fitToBounds(bounds: { minLat: number; maxLat: number; minLon: number; maxLon: number }, paddingPercent: number = 15) {
  if (!BMapInstance) {
    console.log('[BMap] fitToBounds - BMapInstance 未初始化')
    return
  }

  // 获取当前使用的地图 API 命名空间（GL 或 Legacy）
  const BMapClass = isLegacyMode.value ? (window as any).BMap : (window as any).BMapGL
  const { minLat, maxLat, minLon, maxLon } = bounds

  // 将 WGS84 坐标转换为 BD09（百度地图坐标系）
  const [bdMinLon, bdMinLat] = wgs84ToBd09(minLon, minLat)
  const [bdMaxLon, bdMaxLat] = wgs84ToBd09(maxLon, maxLat)

  console.log('[BMap] fitToBounds - WGS84边界:', { minLat, maxLat, minLon, maxLon },
              'BD09边界:', { minLat: bdMinLat, maxLat: bdMaxLat, minLon: bdMinLon, maxLon: bdMaxLon })

  // 创建边界点数组
  const boundsPoints = [
    new BMapClass.Point(bdMinLon, bdMinLat),
    new BMapClass.Point(bdMaxLon, bdMaxLat)
  ]

  // 获取容器尺寸计算 padding 像素值
  const container = mapContainer.value
  let padding = 50 // 默认 50px
  if (container) {
    const size = Math.max(container.clientWidth, container.clientHeight)
    padding = Math.round(size * (paddingPercent / 100))
  }

  if (isLegacyMode.value) {
    // Legacy 版本：使用 setViewport
    BMapInstance.setViewport(boundsPoints, {
      margins: [padding, padding, padding, padding]
    })
    console.log('[BMap] fitToBounds - Legacy版本 setViewport called, padding:', padding)
  } else {
    // GL 版本：使用 setViewport
    BMapInstance.setViewport(boundsPoints, {
      margins: [padding, padding, padding, padding]
    })
    console.log('[BMap] fitToBounds - GL版本 setViewport called, padding:', padding)
  }
}

// 更新实时轨迹最新点标记
function updateLatestPointMarker() {
  if (!latestPointMarker) return

  if (props.latestPointIndex === null || props.latestPointIndex === undefined) {
    try {
      if (latestPointMarkerAdded) {
        BMapInstance.removeOverlay(latestPointMarker)
        latestPointMarkerAdded = false
      }
    } catch (e) {
      // ignore
    }
    return
  }

  // 如果还没绘制轨迹（trackPoints 为空），等待绘制完成
  if (!trackPoints.length) {
    nextTick(() => updateLatestPointMarker())
    return
  }

  const index = props.latestPointIndex
  if (index < 0 || index >= trackPoints.length) {
    try {
      if (latestPointMarkerAdded) {
        BMapInstance.removeOverlay(latestPointMarker)
        latestPointMarkerAdded = false
      }
    } catch (e) {
      // ignore
    }
    return
  }

  const point = trackPoints[index]
  const position = trackPath[index]
  if (!point || !position || !BMapInstance) {
    try {
      if (latestPointMarkerAdded) {
        BMapInstance.removeOverlay(latestPointMarker)
        latestPointMarkerAdded = false
      }
    } catch (e) {
      // ignore
    }
    return
  }

  // Legacy mode handled by BMapAPI
  latestPointMarker.setPosition(createPoint(position.lng, position.lat))

  // 如果还没添加到地图，先添加
  if (!latestPointMarkerAdded) {
    BMapInstance.addOverlay(latestPointMarker)
    latestPointMarkerAdded = true
  }
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

  // 直接调用已有的 highlightPoint 函数
  highlightPoint(newIndex)
})

/**
 * 异步检查图片是否为空白或接近空白
 * 通过实际加载图像并采样检查像素内容
 */
async function isBlankImage(dataUrl: string): Promise<boolean> {
  return new Promise((resolve) => {
    const img = new Image()
    img.onload = () => {
      const tempCanvas = document.createElement('canvas')
      const tempCtx = tempCanvas.getContext('2d')
      if (!tempCtx) {
        resolve(false)
        return
      }

      const sampleSize = 100
      tempCanvas.width = sampleSize
      tempCanvas.height = sampleSize

      tempCtx.drawImage(img, 0, 0, sampleSize, sampleSize)
      const imageData = tempCtx.getImageData(0, 0, sampleSize, sampleSize)
      const data = imageData.data

      let hasContent = false
      for (let i = 0; i < data.length; i += 4) {
        const a = data[i + 3]
        if (a > 10) {
          const r = data[i]
          const g = data[i + 1]
          const b = data[i + 2]
          if (r < 240 || g < 240 || b < 240) {
            hasContent = true
            break
          }
        }
      }

      console.log('[BMap] Image content check:', hasContent ? 'has content' : 'blank')
      resolve(!hasContent)
    }
    img.onerror = () => resolve(false)
    img.src = dataUrl
  })
}

// 暴露方法给父组件
defineExpose({
  highlightPoint,
  hideMarker,
  resize,
  fitBounds,
  fitToBounds,
  getMapElement: () => mapContainer.value || null,
  async captureMap(): Promise<string | null> {
    if (!BMapInstance || !mapContainer.value) return null

    try {
      const canvas = mapContainer.value.querySelector('canvas') as HTMLCanvasElement
      if (!canvas) return null

      return new Promise<string | null>((resolve) => {
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            try {
              const dataUrl = canvas.toDataURL('image/png')
              isBlankImage(dataUrl).then((blank) => {
                if (blank) {
                  console.warn('[BMap] WebGL capture failed - drawing buffer was cleared')
                  resolve(null)
                } else {
                  console.log('[BMap] Captured image has content')
                  resolve(dataUrl)
                }
              })
            } catch (error) {
              console.error('[BMap] captureMap failed:', error)
              resolve(null)
            }
          })
        })
      })
    } catch (error) {
      console.error('[BMap] captureMap failed:', error)
      return null
    }
  },
})
</script>

<style scoped>
.bmap-container {
  width: 100%;
  height: 100%;
  position: relative;
}

.bmap {
  width: 100%;
  height: 100%;
}

/* 百度地图控件位置调整 */
:deep(.anchorBR) {
  top: 10px !important;
  left: 10px !important;
  right: auto !important;
  bottom: auto !important;
}

/* :deep(.BMap_bubble_top) {
  display: none;

} */

/* :deep(.BMap_bubble_bottom + img) {
  position: relative;
  bottom: 0px !important;
  top: 0px !important;
} */

/* 道路标志 SVG 行内显示 */
:deep(.road-sign-inline),
:deep(.BMap_bubble_content .road-sign-inline) {
  display: inline-flex;
  align-items: center;
  vertical-align: middle;
  line-height: 1;
  margin: 0 1px;
}

:deep(.road-sign-inline svg),
:deep(.BMap_bubble_content .road-sign-inline svg) {
  display: block;
  height: 1.4em;
  width: auto;
}

</style>
