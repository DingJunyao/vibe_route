<template>
  <div class="bmap-container">
    <div ref="mapContainer" class="bmap"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useConfigStore } from '@/stores/config'
import { roadSignApi } from '@/api/roadSign'
import { parseRoadNumber, type ParsedRoadNumber } from '@/utils/roadSignParser'

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

interface Props {
  tracks?: Track[]
  highlightTrackId?: number
  highlightSegment?: { start: number; end: number } | null
  defaultLayerId?: string
  mode?: 'home' | 'detail'
}

const props = withDefaults(defineProps<Props>(), {
  tracks: () => [],
  highlightTrackId: undefined,
  highlightSegment: null,
  defaultLayerId: undefined,
  mode: 'detail',
})

const configStore = useConfigStore()

// 百度地图实例
const mapContainer = ref<HTMLElement>()
let BMapInstance: any = null
let polylines: any[] = []
let highlightPolyline: any = null  // 路径段高亮图层
let mouseMarker: any = null
let customTooltip: HTMLElement | null = null  // 自定义 tooltip 元素
let currentHighlightPoint: { index: number; position: { lng: number; lat: number }; point: Point } | null = null
let trackPoints: Point[] = []
let trackPath: { lng: number; lat: number }[] = []
let lastHoverIndex = -1
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

// 加载百度地图 JS API GL
async function loadBMapScript(): Promise<void> {
  return new Promise((resolve, reject) => {
    if ((window as any).BMapGL) {
      resolve()
      return
    }

    const layerConfig = configStore.getMapLayerById('baidu')
    const apiKey = layerConfig?.ak || layerConfig?.api_key || ''

    if (!apiKey) {
      reject(new Error('Baidu Map API Key is required'))
      return
    }

    // 设置全局回调函数
    const callbackName = 'bmapInitCallback'
    ;(window as any)[callbackName] = () => {
      resolve()
      delete (window as any)[callbackName]
    }

    const script = document.createElement('script')
    script.type = 'text/javascript'
    script.src = `https://api.map.baidu.com/api?v=1.0&type=webgl&ak=${apiKey}&callback=${callbackName}`
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

// 创建自定义覆盖物类（蓝色圆点标记）
function createMouseMarkerOverlay() {
  const BMapGL = (window as any).BMapGL

  // 百度地图 GL 版本自定义覆盖物需要继承 BMapGL.Overlay
  class MouseMarkerOverlay extends BMapGL.Overlay {
    private point: any = null
    private element: HTMLElement | null = null
    private map: any = null
    private _mapMoveHandler: any = null

    constructor(point: any) {
      super()
      this.point = point
    }

    // 百度地图 GL 覆盖物必须实现 initialize 方法
    initialize(map: any): HTMLElement {
      this.map = map

      // 创建 DOM 元素
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

      // 添加到地图浮层面
      map.getPanes().floatPane.appendChild(this.element)

      // 监听地图移动事件，自动重绘标记位置
      this._mapMoveHandler = () => this.draw()
      map.addEventListener('moveend', this._mapMoveHandler)
      map.addEventListener('zoomend', this._mapMoveHandler)

      return this.element
    }

    // 百度地图 GL 覆盖物必须实现 draw 方法
    draw() {
      if (!this.element || !this.point || !this.map) return

      const position = this.map.pointToOverlayPixel(this.point)
      if (position) {
        this.element.style.left = position.x + 'px'
        this.element.style.top = position.y + 'px'
      }
    }

    // 设置覆盖物的地理位置
    setPosition(point: any) {
      this.point = point
      this.draw()
    }

    // 清理资源
    remove() {
      if (this.element && this.element.parentNode) {
        this.element.parentNode.removeChild(this.element)
      }

      // 移除地图事件监听
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

// 创建鼠标位置标记
function createMouseMarker() {
  if (!BMapInstance) return

  const BMapGL = (window as any).BMapGL
  const MouseMarkerOverlay = createMouseMarkerOverlay()

  mouseMarker = new MouseMarkerOverlay(new BMapGL.Point(0, 0))
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

  const BMapGL = (window as any).BMapGL
  const point = new BMapGL.Point(lng, lat)
  const pixel = BMapInstance.pointToOverlayPixel(point)

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

  const BMapGL = (window as any).BMapGL

  // 检查点是否在视野内，如果不在则平移地图到该点
  const bounds = BMapInstance.getBounds()
  const pointBMapPoint = new BMapGL.Point(position.lng, position.lat)
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
  mouseMarker = new MouseMarkerOverlay(new BMapGL.Point(position.lng, position.lat))
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
  if (!mapContainer.value) return

  try {
    await loadBMapScript()

    const BMapGL = (window as any).BMapGL

    // 创建地图实例
    BMapInstance = new BMapGL.Map(mapContainer.value, {
      enableDblclickZoom: true,
      enableMapClick: false,
      enableRotate: false,
      enableTilt: false,
    })

    const point = new BMapGL.Point(116.404, 39.915)
    BMapInstance.centerAndZoom(point, 12)

    // 启用鼠标滚轮缩放
    BMapInstance.enableScrollWheelZoom(true)

    // 添加缩放控件
    const zoomCtrl = new BMapGL.ZoomControl()
    BMapInstance.addControl(zoomCtrl)

    // 添加比例尺
    const scaleCtrl = new BMapGL.ScaleControl()
    BMapInstance.addControl(scaleCtrl)

    // 创建标记和自定义 tooltip
    createMouseMarker()
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
        mouseMarker = new MouseMarkerOverlay(new BMapGL.Point(nearestPosition.lng, nearestPosition.lat))
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

        const BMapGL = (window as any).BMapGL

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
        mouseMarker = new MouseMarkerOverlay(new BMapGL.Point(nearestPosition.lng, nearestPosition.lat))
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

    // 移动端：点击地图显示轨迹信息
    const isMobile = window.innerWidth <= 1366
    if (isMobile) {
      BMapInstance.addEventListener('click', (e: any) => {
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
            mouseMarker = new MouseMarkerOverlay(new BMapGL.Point(nearestPosition.lng, nearestPosition.lat))
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
            mouseMarker = new MouseMarkerOverlay(new BMapGL.Point(nearestPosition.lng, nearestPosition.lat))
            BMapInstance.addOverlay(mouseMarker)

            // 显示 tooltip（每次创建新实例）
            showTooltip(nearestIndex, point, nearestPosition)

            lastHoverIndex = nearestIndex
            emit('point-hover', point, nearestIndex)
          } else {
            hideMarker()
          }
        }
      })
    }

    // 绘制轨迹
    drawTracks()
  } catch (error) {
    console.error('[BMap] Failed to initialize:', error)
  }
}

// 根据坐标系获取经纬度（BD09）
function getBD09Coords(point: Point): { lng: number; lat: number } | null {
  const lat = point.latitude_bd09 ?? point.latitude_wgs84 ?? point.latitude
  const lng = point.longitude_bd09 ?? point.longitude_wgs84 ?? point.longitude
  if (lat !== undefined && lng !== undefined && !isNaN(lat) && !isNaN(lng)) {
    return { lng, lat }
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

  const BMapGL = (window as any).BMapGL
  const bounds: any[] = []

  for (const track of props.tracks) {
    if (!track.points || track.points.length === 0) continue

    const points: any[] = []
    const trackPathData: { lng: number; lat: number }[] = []
    const trackPointsData: Point[] = []

    for (const point of track.points) {
      const coords = getBD09Coords(point)
      if (!coords) continue

      const { lng, lat } = coords
      points.push(new BMapGL.Point(lng, lat))
      bounds.push(new BMapGL.Point(lng, lat))

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
    const polyline = new BMapGL.Polyline(points, {
      strokeColor: '#FF0000',
      strokeWeight: isHighlighted ? 5 : 3,
      strokeOpacity: 0.8,
    })

    // 桌面端：点击轨迹直接跳转
    polyline.addEventListener('click', () => {
      const isMobile = window.innerWidth <= 1366
      if (!isMobile) {
        emit('track-click', track.id)
      }
    })

    BMapInstance.addOverlay(polyline)
    polylines.push(polyline)
  }

  // 绘制路径段高亮（detail 模式）
  if (props.mode === 'detail' && props.highlightSegment && trackPath.length > 0) {
    const { start, end } = props.highlightSegment
    // 确保索引在有效范围内
    if (start >= 0 && end < trackPath.length && start <= end) {
      const segmentPath = trackPath.slice(start, end + 1)
      // 转换为 BMapGL.Point 对象数组
      const pointPath = segmentPath.map(p => new BMapGL.Point(p.lng, p.lat))
      if (pointPath.length > 0) {
        highlightPolyline = new BMapGL.Polyline(pointPath, {
          strokeColor: '#409eff',  // 蓝色高亮
          strokeWeight: 7,
          strokeOpacity: 0.9,
        })
        BMapInstance.addOverlay(highlightPolyline)
      }
    }
  }

  // 自动适应视图
  if (bounds.length > 0) {
    try {
      BMapInstance.setViewport(bounds)
    } catch (e) {
      if (bounds.length > 0) {
        BMapInstance.setCenter(bounds[0])
      }
    }
  }
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
}

// 更新轨迹
function updateTracks() {
  drawTracks()
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

// 生命周期
onMounted(async () => {
  await init()
})

onUnmounted(() => {
  if (BMapInstance) {
    try {
      BMapInstance.destroy()
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

// 将所有轨迹居中显示（四周留 5% 空间）
function fitBounds() {
  if (!BMapInstance) return

  // 计算所有轨迹的边界
  const BMapGL = (window as any).BMapGL
  const bounds: any[] = []

  for (const track of props.tracks) {
    if (!track.points || track.points.length === 0) continue
    for (const point of track.points) {
      const coords = getBD09Coords(point)
      if (!coords) continue
      const { lng, lat } = coords
      if (!isNaN(lat) && !isNaN(lng)) {
        bounds.push(new BMapGL.Point(lng, lat))
      }
    }
  }

  if (bounds.length === 0) return

  try {
    BMapInstance.setViewport(bounds)
  } catch (e) {
    console.error('[BMap] fitBounds failed:', e)
  }
}

// 暴露方法给父组件
defineExpose({
  highlightPoint,
  hideMarker,
  resize,
  fitBounds,
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
