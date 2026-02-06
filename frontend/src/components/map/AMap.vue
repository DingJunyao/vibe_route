<template>
  <div class="amap-container">
    <div ref="mapContainer" class="amap"></div>
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

// 格式化地理信息显示，返回 HTML 和需要加载的道路编号列表
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
  highlightPointIndex?: number
  latestPointIndex?: number | null  // 实时轨迹最新点索引（显示绿色标记）
  defaultLayerId?: string
  mode?: 'home' | 'detail'
}

const props = withDefaults(defineProps<Props>(), {
  tracks: () => [],
  highlightTrackId: undefined,
  highlightSegment: null,
  highlightPointIndex: undefined,
  latestPointIndex: null,
  defaultLayerId: undefined,
  mode: 'detail',
})

const configStore = useConfigStore()

// 高德地图实例
const mapContainer = ref<HTMLElement>()
let AMapInstance: any = null
let polylines: any[] = []
let highlightPolyline: any = null  // 路径段高亮图层
let mouseMarker: any = null  // 鼠标位置标记
let tooltip: any = null  // 信息提示框
let documentMouseMoveHandler: ((e: MouseEvent) => void) | null = null  // document 鼠标移动处理函数
let latestPointMarker: any = null  // 实时轨迹最新点标记（绿色）

// 存储轨迹点数据用于查询
let trackPoints: Point[] = []
let trackPath: any[] = []  // 高德地图坐标路径
// home 模式：按轨迹分开存储
const tracksData = new Map<number, { points: Point[]; path: any[]; track: Track }>()

// 节流和缓存
let lastHoverIndex = -1  // 上次悬停的点索引
let throttleTimer: number | null = null  // 节流定时器
const THROTTLE_DELAY = 30  // 节流延迟（毫秒）

// 道路标志 SVG 缓存
const roadSignSvgCache = new Map<string, string>()
const loadingSigns = new Set<string>()
let currentTooltipPoint: Point | null = null  // 当前 tooltip 显示的点（用于异步更新）
let currentTooltipTrackId: number | null = null  // 当前 InfoWindow 显示的轨迹 ID（用于点击跳转）

// 创建鼠标位置标记
function createMouseMarker() {
  if (!AMapInstance) return

  const AMap = (window as any).AMap

  // 使用 HTML 内容创建蓝色圆点标记（与 Leaflet 样式一致）
  const markerContent = `
    <div style="
      width: 12px;
      height: 12px;
      background: #409eff;
      border: 2px solid #fff;
      border-radius: 50%;
      box-shadow: 0 0 4px rgba(0, 0, 0, 0.3);
      cursor: pointer;
    "></div>
  `

  mouseMarker = new AMap.Marker({
    position: new AMap.LngLat(0, 0),
    content: markerContent,
    offset: new AMap.Pixel(-6, -6),
    zIndex: 100,
    map: null,  // 初始不添加到地图
  })

  // 桌面端：点击标记时跳转到当前轨迹
  mouseMarker.on('click', () => {
    const isMobile = window.innerWidth <= 1366
    if (!isMobile && props.mode === 'home' && currentTooltipTrackId !== null) {
      emit('track-click', currentTooltipTrackId)
    }
  })

  // 创建绿色标记用于显示实时轨迹最新点
  const latestMarkerContent = `
    <div style="
      width: 12px;
      height: 12px;
      background: #67c23a;
      border: 2px solid #fff;
      border-radius: 50%;
      box-shadow: 0 0 4px rgba(0, 0, 0, 0.3);
      cursor: pointer;
    "></div>
  `

  latestPointMarker = new AMap.Marker({
    position: new AMap.LngLat(0, 0),
    content: latestMarkerContent,
    offset: new AMap.Pixel(-6, -6),
    zIndex: 99,
    map: null,  // 初始不添加到地图
  })
}

// 计算智能偏移量，避免 InfoWindow 超出地图边界
// 返回 offset 和 anchor，anchor 是 InfoWindow 的锚点位置
function calculateSmartOffset(position: [number, number]): { x: number; y: number; anchor: 'bottom-center' | 'top-center' } {
  if (!AMapInstance || !mapContainer.value) {
    return { x: 0, y: -20, anchor: 'bottom-center' }
  }

  const AMap = (window as any).AMap

  // 将地图坐标转换为容器像素坐标
  const pixel = AMapInstance.lngLatToContainer(new AMap.LngLat(position[0], position[1]))
  if (!pixel) {
    return { x: 0, y: -20, anchor: 'bottom-center' }
  }

  const containerWidth = mapContainer.value.clientWidth
  const containerHeight = mapContainer.value.clientHeight

  // InfoWindow 的固定尺寸
  const tooltipWidth = 200
  const tooltipHeight = 120  // 估计高度
  const padding = 60

  const pixelX = pixel.getX()
  const pixelY = pixel.getY()

  // 如果点在容器外很远，使用默认值
  if (pixelX < -50 || pixelX > containerWidth + 50 || pixelY < -50 || pixelY > containerHeight + 50) {
    return { x: 0, y: -20, anchor: 'bottom-center' }
  }

  let offsetX = 0
  let offsetY = -10  // 默认小偏移
  let anchor: 'bottom-center' | 'top-center' = 'bottom-center'

  // 垂直方向：检查上方是否有足够空间
  const spaceAbove = pixelY
  const spaceBelow = containerHeight - pixelY

  // 如果上方空间不足，但下方有足够空间，使用 top-center 锚点
  // top-center 锚点表示 tooltip 的顶部中心附着在点上，tooltip 会向下延伸
  if (spaceAbove < tooltipHeight + 20 && spaceBelow > tooltipHeight + 20) {
    anchor = 'top-center'
    offsetY = 10  // 小偏移，tooltip 会在点下方
  } else {
    // 默认使用 bottom-center 锚点，tooltip 会在点上方
    anchor = 'bottom-center'
    offsetY = -10
  }

  // 水平方向：计算偏移避免超出边界
  const tooltipRight = pixelX + tooltipWidth / 2
  const tooltipLeft = pixelX - tooltipWidth / 2

  if (tooltipRight > containerWidth - padding) {
    // 靠右边界：向左偏移
    offsetX = -(tooltipRight - (containerWidth - padding))
  } else if (tooltipLeft < padding) {
    // 靠左边界：向右偏移
    offsetX = padding - tooltipLeft
  }

  return { x: offsetX, y: offsetY, anchor }
}

// 创建信息提示框
function createTooltip() {
  if (!AMapInstance) return

  const AMap = (window as any).AMap

  tooltip = new AMap.InfoWindow({
    isCustom: true,
    content: '',
    offset: new AMap.Pixel(0, -20),
    autoMove: false,  // 禁用自动调整，使用我们的手动偏移
    closeWhenClickMap: false,
    showShadow: false,
  })

  // InfoWindow 点击事件处理函数
  const handleInfoWindowClick = (e: Event) => {
    if (currentTooltipTrackId !== null) {
      emit('track-click', currentTooltipTrackId)
      e.stopPropagation()
      e.preventDefault()
    }
  }

  // 监听 InfoWindow 内容的点击事件（使用全局事件委托）
  // 高德地图 InfoWindow 内容会被插入到 DOM 中，使用全局监听
  const handleTooltipClick = (e: Event) => {
    const target = e.target as HTMLElement
    if (target) {
      const tooltipEl = target.closest('.track-tooltip') as HTMLElement
      const trackId = tooltipEl?.getAttribute('data-track-id')

      // 如果找到了 track-tooltip，使用找到的 trackId
      if (trackId) {
        emit('track-click', parseInt(trackId))
        e.stopPropagation()
        e.preventDefault()
        return
      } else {
        // 否则检查是否点击了 InfoWindow 的内容区域
        const infoWindowContent = target.closest('.amap-info-content') as HTMLElement
        const infoWindow = target.closest('.amap-info') as HTMLElement

        if ((infoWindowContent || infoWindow) && currentTooltipTrackId !== null) {
          emit('track-click', currentTooltipTrackId)
          e.stopPropagation()
          e.preventDefault()
        }
      }
    }
  }

  // 使用捕获阶段监听，确保能捕获到 InfoWindow 内的点击
  document.addEventListener('click', handleTooltipClick, true)
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

// 计算两点距离
function distance(p1: [number, number], p2: [number, number]): number {
  const dx = p1[0] - p2[0]
  const dy = p1[1] - p2[1]
  return Math.sqrt(dx * dx + dy * dy)
}

// 查找鼠标位置对应的轨迹点
function findNearestPoint(mouseLngLat: [number, number]): { point: Point; index: number; position: [number, number] } | null {
  if (trackPath.length < 2 || !AMapInstance) return null

  // 根据地图缩放级别动态计算触发距离
  const zoom = AMapInstance.getZoom()
  const dynamicDistance = Math.pow(2, 12 - zoom) * 0.008

  let minDistance = Infinity
  let nearestPoint: Point | null = null
  let nearestIndex = -1
  let nearestPosition: [number, number] = [0, 0]

  // 遍历所有线段，找到距离鼠标最近的点
  for (let i = 0; i < trackPath.length - 1; i++) {
    const p1 = [trackPath[i].lng, trackPath[i].lat] as [number, number]
    const p2 = [trackPath[i + 1].lng, trackPath[i + 1].lat] as [number, number]

    const closest = closestPointOnSegment(mouseLngLat, p1, p2)
    const dist = distance(mouseLngLat, closest)

    if (dist < minDistance) {
      minDistance = dist
      nearestPosition = closest

      // 找到对应的轨迹点索引
      // 如果最近点更接近 p1，使用 i；否则使用 i+1
      const distToP1 = distance(closest, p1)
      const distToP2 = distance(closest, p2)
      nearestIndex = distToP1 < distToP2 ? i : i + 1
      nearestPoint = trackPoints[nearestIndex]
    }
  }

  // 使用动态触发距离
  if (minDistance < dynamicDistance) {
    return { point: nearestPoint!, index: nearestIndex, position: nearestPosition }
  }

  return null
}

// 更新标记和提示框
function updateMarker(nearest: { point: Point; index: number; position: [number, number] }) {
  // 如果是同一个点，跳过更新
  if (nearest.index === lastHoverIndex) return

  lastHoverIndex = nearest.index

  if (!AMapInstance || !mouseMarker) return

  const AMap = (window as any).AMap

  // 更新标记位置并显示
  mouseMarker.setPosition(new AMap.LngLat(nearest.position[0], nearest.position[1]))
  mouseMarker.setMap(AMapInstance)

  // 更新提示框内容
  const { point, index } = nearest
  const timeStr = point.time ? new Date(point.time).toLocaleTimeString('zh-CN') : '-'
  const elevation = point.elevation != null ? `${point.elevation.toFixed(1)} m` : '-'
  const speed = point.speed != null ? `${(point.speed * 3.6).toFixed(1)} km/h` : '-'

  const content = `
    <div style="width: 200px; padding: 8px 12px; background: rgba(255, 255, 255, 0.95); border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-size: 12px; line-height: 1.6;">
      <div style="font-weight: bold; color: #333; margin-bottom: 4px;">点 #${index}</div>
      <div style="color: #666;">时间: ${timeStr}</div>
      <div style="color: #666;">速度: ${speed}</div>
      <div style="color: #666;">海拔: ${elevation}</div>
    </div>
  `

  if (tooltip) {
    // 计算智能偏移
    const smartOffset = calculateSmartOffset(nearest.position)
    tooltip.setAnchor(smartOffset.anchor)
    tooltip.setOffset(new AMap.Pixel(smartOffset.x, smartOffset.y))
    tooltip.setContent(content)
    tooltip.setPosition(new AMap.LngLat(nearest.position[0], nearest.position[1]))
    tooltip.open(AMapInstance)
  }

  // 发射事件
  emit('point-hover', point, index)
}

// 隐藏标记和提示框
function hideMarker() {
  if (lastHoverIndex === -1) return  // 已经隐藏了

  lastHoverIndex = -1
  currentTooltipPoint = null
  currentTooltipTrackId = null  // 清除保存的轨迹 ID
  if (mouseMarker) mouseMarker.setMap(null)
  if (tooltip) tooltip.close()

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

  if (!AMapInstance || !mouseMarker || !tooltip || !point || !position) return

  const AMap = (window as any).AMap

  // 检查点是否在视野内，如果不在则平移地图到该点
  const bounds = AMapInstance.getBounds()
  const pointLngLat = new AMap.LngLat(position.lng, position.lat)
  if (bounds && !bounds.contains(pointLngLat)) {
    AMapInstance.panTo(pointLngLat)
  }

  mouseMarker.setPosition(new AMap.LngLat(position.lng, position.lat))
  mouseMarker.setMap(AMapInstance)

  // 保存当前显示的点（用于异步更新）
  currentTooltipPoint = point

  const timeStr = point.time ? new Date(point.time).toLocaleTimeString('zh-CN') : '-'
  const elevation = point.elevation != null ? `${point.elevation.toFixed(1)} m` : '-'
  const speed = point.speed != null ? `${(point.speed * 3.6).toFixed(1)} km/h` : '-'
  const locationResult = formatLocationInfo(point)

  const content = `
    <div style="width: 200px; padding: 8px 12px; background: rgba(255, 255, 255, 0.95); border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-size: 12px; line-height: 1.6;">
      <div style="font-weight: bold; color: #333; margin-bottom: 4px;">点 #${index}</div>
      ${locationResult.html ? `<div style="color: #666;">${locationResult.html}</div>` : ''}
      <div style="color: #666;">时间: ${timeStr}</div>
      <div style="color: #666;">速度: ${speed}</div>
      <div style="color: #666;">海拔: ${elevation}</div>
    </div>
  `

  // 计算智能偏移
  const smartOffset = calculateSmartOffset([position.lng, position.lat])
  tooltip.setAnchor(smartOffset.anchor)
  tooltip.setOffset(new AMap.Pixel(smartOffset.x, smartOffset.y))
  tooltip.setContent(content)
  tooltip.setPosition(new AMap.LngLat(position.lng, position.lat))
  tooltip.open(AMapInstance)

  // 异步加载道路标志 SVG
  if (locationResult.needLoad.length > 0) {
    nextTick(async () => {
      const loaded = await loadRoadSignsForTooltip(locationResult.needLoad)
      // 如果加载成功且当前还在显示同一个点，则更新 tooltip
      if (loaded && currentTooltipPoint === point) {
        highlightPoint(index)
      }
    })
  }
}

// 初始化
async function init() {
  // 等待配置加载
  if (!configStore.config) {
    await configStore.fetchConfig()
  }

  await initMap()
}

// 加载高德地图 JS API
async function loadAMapScript(): Promise<void> {
  return new Promise((resolve, reject) => {
    if ((window as any).AMap) {
      resolve()
      return
    }

    const layerConfig = configStore.getMapLayerById('amap')
    const apiKey = layerConfig?.api_key || ''
    const securityJsCode = layerConfig?.security_js_code || ''

    const script = document.createElement('script')
    script.type = 'text/javascript'

    // 如果有安全密钥，使用带有安全密钥的加载方式
    if (securityJsCode && apiKey) {
      script.src = `https://webapi.amap.com/maps?v=2.0&key=${apiKey}&securityJsCode=${securityJsCode}`
    } else if (apiKey) {
      script.src = `https://webapi.amap.com/maps?v=2.0&key=${apiKey}`
    } else {
      reject(new Error('AMap API Key is required'))
      return
    }

    script.onload = () => resolve()
    script.onerror = () => reject(new Error('Failed to load AMap API'))
    document.head.appendChild(script)
  })
}

// 等待 AMap API 加载完成
function waitForAMap(): Promise<void> {
  return new Promise((resolve) => {
    if ((window as any).AMap) {
      resolve()
      return
    }
    const checkInterval = setInterval(() => {
      if ((window as any).AMap) {
        clearInterval(checkInterval)
        resolve()
      }
    }, 50)
  })
}

// 初始化地图
async function initMap() {
  if (!mapContainer.value) return

  try {
    await loadAMapScript()
    await waitForAMap()

    const AMap = (window as any).AMap

    // 创建地图实例
    AMapInstance = new AMap.Map(mapContainer.value, {
      zoom: 10,
      center: [116.397428, 39.90923],
      viewMode: '2D',
      showLabel: true,
    })

    // 高德地图标准样式（矢量渲染）
    AMapInstance.setMapStyle('amap://styles/normal')

    // 添加控件
    AMap.plugin(['AMap.ToolBar', 'AMap.Scale'], () => {
      // 添加工具条（缩放按钮）- 左上角
      const toolBar = new AMap.ToolBar({
        position: {
          top: '10px',
          left: '10px',
        },
      })
      AMapInstance.addControl(toolBar)

      // 添加比例尺 - 左下角，向上偏移避开 logo
      const scale = new AMap.Scale({
        position: {
          bottom: '20px',
          left: '10px',
        },
      })
      AMapInstance.addControl(scale)
    })

    // 创建标记和提示框
    createMouseMarker()
    createTooltip()

    // 统一的鼠标处理函数
    const handleMouseMove = (mouseLngLat: [number, number]) => {
      if (props.mode === 'home') {
        handleHomeModeMouseMove(mouseLngLat)
      } else {
        handleDetailModeMouseMove(mouseLngLat)
      }
    }

    // detail 模式：显示最近的点信息
    const handleDetailModeMouseMove = (mouseLngLat: [number, number]) => {
      if (trackPath.length < 2) return

      const zoom = AMapInstance.getZoom()
      const dynamicDistance = Math.pow(2, 12 - zoom) * 0.008

      let minDistance = Infinity
      let nearestIndex = -1
      let nearestPosition: [number, number] = [0, 0]

      // 快速查找最近的点
      for (let i = 0; i < trackPath.length - 1; i++) {
        const p1 = [trackPath[i].lng, trackPath[i].lat] as [number, number]
        const p2 = [trackPath[i + 1].lng, trackPath[i + 1].lat] as [number, number]
        const closest = closestPointOnSegment(mouseLngLat, p1, p2)
        const dist = distance(mouseLngLat, closest)

        if (dist < minDistance) {
          minDistance = dist
          nearestPosition = closest
          const distToP1 = distance(closest, p1)
          const distToP2 = distance(closest, p2)
          nearestIndex = distToP1 < distToP2 ? i : i + 1
        }
      }

      const triggered = minDistance < dynamicDistance

      // 更新或隐藏标记
      if (triggered && nearestIndex >= 0 && nearestIndex < trackPoints.length) {
        const point = trackPoints[nearestIndex]
        const AMap = (window as any).AMap

        // 始终更新标记位置
        mouseMarker.setPosition(new AMap.LngLat(nearestPosition[0], nearestPosition[1]))
        mouseMarker.setMap(AMapInstance)

        // 如果是同一个点，只更新位置和偏移量，不更新内容
        if (nearestIndex === lastHoverIndex) {
          // 重新计算偏移量并更新 tooltip 位置
          const smartOffset = calculateSmartOffset(nearestPosition)
          tooltip.setAnchor(smartOffset.anchor)
          tooltip.setOffset(new AMap.Pixel(smartOffset.x, smartOffset.y))
          tooltip.setPosition(new AMap.LngLat(nearestPosition[0], nearestPosition[1]))
        } else {
          // 新的点，完整更新
          lastHoverIndex = nearestIndex
          currentTooltipPoint = point

          // 更新提示框内容
          const timeStr = point.time ? new Date(point.time).toLocaleTimeString('zh-CN') : '-'
          const elevation = point.elevation != null ? `${point.elevation.toFixed(1)} m` : '-'
          const speed = point.speed != null ? `${(point.speed * 3.6).toFixed(1)} km/h` : '-'
          const locationResult = formatLocationInfo(point)

          const content = `
            <div style="width: 200px; padding: 8px 12px; background: rgba(255, 255, 255, 0.95); border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-size: 12px; line-height: 1.6;">
              <div style="font-weight: bold; color: #333; margin-bottom: 4px;">点 #${nearestIndex}</div>
              ${locationResult.html ? `<div style="color: #666;">${locationResult.html}</div>` : ''}
              <div style="color: #666;">时间: ${timeStr}</div>
              <div style="color: #666;">速度: ${speed}</div>
              <div style="color: #666;">海拔: ${elevation}</div>
            </div>
          `

          // 计算智能偏移
          const smartOffset = calculateSmartOffset(nearestPosition)
          tooltip.setAnchor(smartOffset.anchor)
          tooltip.setOffset(new AMap.Pixel(smartOffset.x, smartOffset.y))
          tooltip.setContent(content)
          tooltip.setPosition(new AMap.LngLat(nearestPosition[0], nearestPosition[1]))
          tooltip.open(AMapInstance)

          // 异步加载道路标志 SVG
          if (locationResult.needLoad.length > 0) {
            nextTick(async () => {
              const loaded = await loadRoadSignsForTooltip(locationResult.needLoad)
              if (loaded && currentTooltipPoint === point) {
                // 重新触发更新（通过重新调用相同逻辑）
                lastHoverIndex = -1  // 重置索引以强制更新
              }
            })
          }

          // 发射事件
          emit('point-hover', point, nearestIndex)
        }
      } else {
        hideMarker()
      }
    }

    // home 模式：显示最近的轨迹信息
    const handleHomeModeMouseMove = (mouseLngLat: [number, number]) => {
      const isMobile = window.innerWidth <= 1366
      const zoom = AMapInstance.getZoom()
      const dynamicDistance = Math.pow(2, 12 - zoom) * 0.008

      let minDistance = Infinity
      let nearestTrackId: number | null = null
      let nearestPosition: [number, number] = [0, 0]

      // 遍历所有轨迹，找到最近的轨迹
      for (const [trackId, data] of tracksData) {
        if (data.path.length < 2) continue

        for (let i = 0; i < data.path.length - 1; i++) {
          const p1 = [data.path[i].lng, data.path[i].lat] as [number, number]
          const p2 = [data.path[i + 1].lng, data.path[i + 1].lat] as [number, number]
          const closest = closestPointOnSegment(mouseLngLat, p1, p2)
          const dist = distance(mouseLngLat, closest)

          if (dist < minDistance) {
            minDistance = dist
            nearestPosition = closest
            nearestTrackId = trackId
          }
        }
      }

      const triggered = minDistance < dynamicDistance

      if (triggered && nearestTrackId !== null) {
        const trackData = tracksData.get(nearestTrackId)
        if (!trackData) return

        const track = trackData.track
        const AMap = (window as any).AMap

        // 始终更新标记位置
        mouseMarker.setPosition(new AMap.LngLat(nearestPosition[0], nearestPosition[1]))
        mouseMarker.setMap(AMapInstance)

        // 如果是同一条轨迹，只更新位置和偏移量
        if (nearestTrackId === lastHoverIndex) {
          const smartOffset = calculateSmartOffset(nearestPosition)
          tooltip.setAnchor(smartOffset.anchor)
          tooltip.setOffset(new AMap.Pixel(smartOffset.x, smartOffset.y))
          tooltip.setPosition(new AMap.LngLat(nearestPosition[0], nearestPosition[1]))
        } else {
          // 新的轨迹，完整更新
          lastHoverIndex = nearestTrackId

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
            <div class="track-tooltip" data-track-id="${track.id}" style="width: 200px; padding: 8px 12px; background: rgba(255, 255, 255, 0.95); border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-size: 12px; line-height: 1.6; cursor: pointer;">
              <div style="font-weight: bold; color: #333; margin-bottom: 4px;">${track.name || '未命名轨迹'}</div>
              <div style="color: #666;">时间: ${formatTimeRange()}</div>
              <div style="color: #666;">里程: ${formatDistance(track.distance)}</div>
              <div style="color: #666;">历时: ${formatDuration(track.duration)}</div>
              ${isMobile ? '<div style="font-size: 10px; color: #409eff; margin-top: 4px;">点击查看详情</div>' : ''}
            </div>
          `

          // 计算智能偏移
          const smartOffset = calculateSmartOffset(nearestPosition)
          tooltip.setAnchor(smartOffset.anchor)
          tooltip.setOffset(new AMap.Pixel(smartOffset.x, smartOffset.y))
          tooltip.setContent(content)
          tooltip.setPosition(new AMap.LngLat(nearestPosition[0], nearestPosition[1]))
          tooltip.open(AMapInstance)

          // 保存当前 InfoWindow 显示的轨迹 ID（用于点击跳转）
          currentTooltipTrackId = nearestTrackId

          // 发射事件
          emit('track-hover', nearestTrackId)
        }
      } else {
        hideMarker()
      }
    }

    // 在 document 级别监听鼠标移动，避免被 AMap 内部元素阻挡
    documentMouseMoveHandler = (e: MouseEvent) => {
      if (!AMapInstance || !mapContainer.value) return

      // 检查鼠标事件是否来自图表容器，如果是则跳过处理
      const chartContainer = document.querySelector('.chart')
      if (chartContainer && chartContainer.contains(e.target as Node)) {
        return  // 鼠标在图表上，让图表的 tooltip 优先显示
      }

      // 检查鼠标是否在地图容器内
      const rect = mapContainer.value.getBoundingClientRect()
      const x = e.clientX - rect.left
      const y = e.clientY - rect.top

      // 如果鼠标在容器外，隐藏标记
      if (x < 0 || x > rect.width || y < 0 || y > rect.height) {
        hideMarker()
        return
      }

      // 将容器坐标转换为地图坐标
      const lngLat = AMapInstance.containerToLngLat(new AMap.Pixel(x, y))
      if (!lngLat) return
      const mouseLngLat: [number, number] = [lngLat.lng, lngLat.lat]
      handleMouseMove(mouseLngLat)
    }

    document.addEventListener('mousemove', documentMouseMoveHandler, true)  // 捕获阶段

    // 点击地图显示轨迹信息或跳转
    // 定义点击处理函数（桌面端和移动端共用）
    const handleMapClick = (e: any) => {
      // 检查点击是否来自 InfoWindow 内部，如果是则忽略（由 document 点击处理器处理）
      const originalEvent = e.originalEvent
      if (originalEvent && originalEvent.target) {
        const target = originalEvent.target as HTMLElement
        const isInInfoWindow = target.closest('.amap-info') || target.closest('.track-tooltip')
        if (isInInfoWindow) {
          return
        }
      }

      const lngLat = e.lnglat
      const mouseLngLat: [number, number] = [lngLat.lng, lngLat.lat]
      const AMap = (window as any).AMap
      const isMobile = window.innerWidth <= 1366

      if (props.mode === 'home') {
        // home 模式：显示轨迹信息或跳转
        if (tracksData.size === 0) {
          hideMarker()
          return
        }

        const zoom = AMapInstance.getZoom()
        const dynamicDistance = Math.pow(2, 12 - zoom) * 0.008

        let minDistance = Infinity
        let nearestTrackId: number | null = null
        let nearestPosition: [number, number] = [0, 0]

        // 遍历所有轨迹，找到最近的轨迹
        for (const [trackId, data] of tracksData) {
          if (data.path.length < 2) continue

          for (let i = 0; i < data.path.length - 1; i++) {
            const p1 = [data.path[i].lng, data.path[i].lat] as [number, number]
            const p2 = [data.path[i + 1].lng, data.path[i + 1].lat] as [number, number]
            const closest = closestPointOnSegment(mouseLngLat, p1, p2)
            const dist = distance(mouseLngLat, closest)

            if (dist < minDistance) {
              minDistance = dist
              nearestPosition = closest
              nearestTrackId = trackId
            }
          }
        }

        const triggered = minDistance < dynamicDistance

        if (triggered && nearestTrackId !== null) {
          // 桌面端：直接跳转
          if (!isMobile) {
            emit('track-click', nearestTrackId)
            return
          }

          // 移动端：显示 InfoWindow
          const trackData = tracksData.get(nearestTrackId)
          if (!trackData) return

          const track = trackData.track
          lastHoverIndex = nearestTrackId

          // 更新标记位置并显示
          mouseMarker.setPosition(new AMap.LngLat(nearestPosition[0], nearestPosition[1]))
          mouseMarker.setMap(AMapInstance)

          // 重新计算是否是移动端（响应窗口大小变化）
          const isMobileNow = window.innerWidth <= 1366

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
            <div class="track-tooltip" data-track-id="${track.id}" style="width: 200px; padding: 8px 12px; background: rgba(255, 255, 255, 0.95); border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-size: 12px; line-height: 1.6; cursor: pointer;">
              <div style="font-weight: bold; color: #333; margin-bottom: 4px;">${track.name || '未命名轨迹'}</div>
              <div style="color: #666;">时间: ${formatTimeRange()}</div>
              <div style="color: #666;">里程: ${formatDistance(track.distance)}</div>
              <div style="color: #666;">历时: ${formatDuration(track.duration)}</div>
              ${isMobileNow ? '<div style="font-size: 10px; color: #409eff; margin-top: 4px;">点击查看详情</div>' : ''}
            </div>
          `

          // 计算智能偏移
          const clickSmartOffset = calculateSmartOffset(nearestPosition)
          tooltip.setAnchor(clickSmartOffset.anchor)
          tooltip.setOffset(new AMap.Pixel(clickSmartOffset.x, clickSmartOffset.y))
          tooltip.setContent(content)
          tooltip.setPosition(new AMap.LngLat(nearestPosition[0], nearestPosition[1]))
          tooltip.open(AMapInstance)

          // 保存当前 InfoWindow 显示的轨迹 ID（用于点击跳转）
          currentTooltipTrackId = nearestTrackId

          // 在 InfoWindow 打开后，给其内容添加点击事件监听器
          // 使用 nextTick 确保 DOM 已经更新
          nextTick(() => {
            const trackTooltip = document.querySelector('.track-tooltip')
            if (trackTooltip) {
              const parent = trackTooltip.parentElement
              if (parent) {
                // 处理 InfoWindow 内的点击和触摸事件
                const handleTooltipInteraction = (e: Event) => {
                  e.stopImmediatePropagation()
                  e.stopPropagation()
                  e.preventDefault()
                  if (currentTooltipTrackId !== null) {
                    emit('track-click', currentTooltipTrackId)
                  }
                }

                // 直接给 track-tooltip 添加点击事件（优先级最高）
                trackTooltip.addEventListener('click', handleTooltipInteraction, { capture: true })

                // 添加 touchstart 监听器（移动端）
                trackTooltip.addEventListener('touchstart', handleTooltipInteraction, { capture: true })

                // 同时给父元素添加点击监听器（备用）
                parent.addEventListener('click', (e) => {
                  if (currentTooltipTrackId !== null) {
                    emit('track-click', currentTooltipTrackId)
                    e.stopPropagation()
                    e.preventDefault()
                  }
                })
              }
            }
          })

          emit('track-hover', nearestTrackId)
        }
      } else {
        // detail 模式：显示点信息
          if (trackPath.length < 2) {
            hideMarker()
            return
          }

          const zoom = AMapInstance.getZoom()
          const dynamicDistance = Math.pow(2, 12 - zoom) * 0.008

          let minDistance = Infinity
          let nearestIndex = -1
          let nearestPosition: [number, number] = [0, 0]

          // 查找最近的点
          for (let i = 0; i < trackPath.length - 1; i++) {
            const p1 = [trackPath[i].lng, trackPath[i].lat] as [number, number]
            const p2 = [trackPath[i + 1].lng, trackPath[i + 1].lat] as [number, number]
            const closest = closestPointOnSegment(mouseLngLat, p1, p2)
            const dist = distance(mouseLngLat, closest)

            if (dist < minDistance) {
              minDistance = dist
              nearestPosition = closest
              const distToP1 = distance(closest, p1)
              const distToP2 = distance(closest, p2)
              nearestIndex = distToP1 < distToP2 ? i : i + 1
            }
          }

          const triggered = minDistance < dynamicDistance

          if (triggered && nearestIndex >= 0 && nearestIndex < trackPoints.length) {
            const point = trackPoints[nearestIndex]

            mouseMarker.setPosition(new AMap.LngLat(nearestPosition[0], nearestPosition[1]))
            mouseMarker.setMap(AMapInstance)

            // 保存当前显示的点（用于异步更新）
            currentTooltipPoint = point

            const timeStr = point.time ? new Date(point.time).toLocaleTimeString('zh-CN') : '-'
            const elevation = point.elevation != null ? `${point.elevation.toFixed(1)} m` : '-'
            const speed = point.speed != null ? `${(point.speed * 3.6).toFixed(1)} km/h` : '-'
            const locationResult = formatLocationInfo(point)

            const content = `
              <div style="width: 200px; padding: 8px 12px; background: rgba(255, 255, 255, 0.95); border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-size: 12px; line-height: 1.6;">
                <div style="font-weight: bold; color: #333; margin-bottom: 4px;">点 #${nearestIndex}</div>
                ${locationResult.html ? `<div style="color: #666;">${locationResult.html}</div>` : ''}
                <div style="color: #666;">时间: ${timeStr}</div>
                <div style="color: #666;">速度: ${speed}</div>
                <div style="color: #666;">海拔: ${elevation}</div>
              </div>
            `

            // 计算智能偏移
            const clickSmartOffset = calculateSmartOffset(nearestPosition)
            tooltip.setAnchor(clickSmartOffset.anchor)
            tooltip.setOffset(new AMap.Pixel(clickSmartOffset.x, clickSmartOffset.y))
            tooltip.setContent(content)
            tooltip.setPosition(new AMap.LngLat(nearestPosition[0], nearestPosition[1]))
            tooltip.open(AMapInstance)

            // 异步加载道路标志 SVG
            if (locationResult.needLoad.length > 0) {
              nextTick(async () => {
                const loaded = await loadRoadSignsForTooltip(locationResult.needLoad)
                if (loaded && currentTooltipPoint === point) {
                  // 重新触发更新（通过重置索引）
                  lastHoverIndex = -1
                }
              })
            }

            lastHoverIndex = nearestIndex
            emit('point-hover', point, nearestIndex)
          } else {
            hideMarker()
          }
        }
      }

    // 注册点击事件监听器（桌面端和移动端都需要）
    AMapInstance.on('click', handleMapClick)

    // 绘制轨迹
    drawTracks()
  } catch (error) {
    console.error('[AMap] Failed to initialize:', error)
  }
}

// 根据坐标系获取经纬度（GCJ02）
function getGCJ02Coords(point: Point): [number, number] | null {
  const lat = point.latitude_gcj02 ?? point.latitude_wgs84 ?? point.latitude
  const lng = point.longitude_gcj02 ?? point.longitude_wgs84 ?? point.longitude
  if (lat !== undefined && lng !== undefined && !isNaN(lat) && !isNaN(lng)) {
    return [lng, lat] // AMap 使用 [lng, lat]
  }
  return null
}

// 绘制轨迹
function drawTracks() {
  if (!AMapInstance || !props.tracks || props.tracks.length === 0) return

  // 清除现有轨迹
  clearTracks()

  // 重置轨迹点数据
  trackPoints = []
  trackPath = []
  tracksData.clear()

  const AMap = (window as any).AMap
  const bounds: any[] = []

  for (const track of props.tracks) {
    if (!track.points || track.points.length === 0) continue

    const path: any[] = []
    const trackPathData: any[] = []
    const trackPointsData: Point[] = []

    for (const point of track.points) {
      const coords = getGCJ02Coords(point)
      if (!coords) continue

      const [lng, lat] = coords
      path.push(new AMap.LngLat(lng, lat))
      bounds.push(new AMap.LngLat(lng, lat))

      // detail 模式：合并所有轨迹
      trackPoints.push(point)
      trackPath.push({ lng, lat })

      // home 模式：按轨迹分开存储
      trackPointsData.push(point)
      trackPathData.push({ lng, lat })
    }

    if (path.length === 0) continue

    // 保存轨迹数据用于 home 模式
    tracksData.set(track.id, {
      points: trackPointsData,
      path: trackPathData,
      track,
    })

    // 绘制轨迹线
    const isHighlighted = track.id === props.highlightTrackId
    const polyline = new AMap.Polyline({
      path: path,
      borderWeight: 1,
      strokeColor: '#FF0000',
      strokeOpacity: 0.8,
      strokeWeight: isHighlighted ? 5 : 3,
      lineJoin: 'round',
      bubble: true,  // 允许鼠标事件冒泡，以便地图能够捕获 mousemove 和 click
      showDir: false,
    })

    AMapInstance.add(polyline)
    polylines.push(polyline)
  }

  // 绘制路径段高亮（detail 模式）
  if (props.mode === 'detail' && props.highlightSegment && trackPath.length > 0) {
    const { start, end } = props.highlightSegment
    // 确保索引在有效范围内
    if (start >= 0 && end < trackPath.length && start <= end) {
      const segmentPath = trackPath.slice(start, end + 1)
      // 转换为 AMap.LngLat 对象数组
      const lngLatPath = segmentPath.map(p => new AMap.LngLat(p.lng, p.lat))
      if (lngLatPath.length > 0) {
        highlightPolyline = new AMap.Polyline({
          path: lngLatPath,
          borderWeight: 1,
          strokeColor: '#409eff',  // 蓝色高亮
          strokeOpacity: 0.9,
          strokeWeight: 7,
          lineJoin: 'round',
          bubble: true,
        })
        AMapInstance.add(highlightPolyline)
      }
    }
  }

  // 自动适应视图
  if (polylines.length > 0) {
    try {
      AMapInstance.setFitView(polylines, false, [60, 60, 60, 60])
    } catch (e) {
      console.error('[AMap] setFitView failed:', e)
      // 如果 setFitView 失败，手动设置中心和缩放
      if (bounds.length > 0) {
        AMapInstance.setCenter(bounds[0])
        AMapInstance.setZoom(12)
      }
    }
  }

  // 更新最新点标记
  updateLatestPointMarker()
}

// 清除轨迹
function clearTracks() {
  if (!AMapInstance) return

  polylines.forEach((polyline) => {
    try {
      AMapInstance.remove(polyline)
    } catch (e) {
      // ignore
    }
  })
  polylines = []

  // 清除路径段高亮
  if (highlightPolyline) {
    try {
      AMapInstance.remove(highlightPolyline)
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

  // 计算位置
  const position: [number, number] = [
    point.longitude_wgs84 || point.longitude || 0,
    point.latitude_wgs84 || point.latitude || 0,
  ]

  updateMarker({ point, index: newIndex, position })
})

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
  if (!point || !position || !AMapInstance) {
    latestPointMarker.setMap(null)
    return
  }

  latestPointMarker.setPosition(new AMap.LngLat(position.lng, position.lat))
  latestPointMarker.setMap(AMapInstance)
}

// 监听最新点索引变化
watch(() => props.latestPointIndex, () => {
  updateLatestPointMarker()
})

// 生命周期
onMounted(async () => {
  await init()
})

onUnmounted(() => {
  // 清理 document 鼠标移动监听器
  if (documentMouseMoveHandler) {
    document.removeEventListener('mousemove', documentMouseMoveHandler, true)
    documentMouseMoveHandler = null
  }

  // 清理节流定时器
  if (throttleTimer) {
    clearTimeout(throttleTimer)
    throttleTimer = null
  }

  if (AMapInstance) {
    try {
      AMapInstance.destroy()
    } catch (e) {
      // ignore
    }
    AMapInstance = null
  }
})

// 调整地图大小（用于响应式布局）
function resize() {
  if (AMapInstance) {
    // 高德地图会自动调整大小，这里可以调用 setFitView 来确保轨迹在视野内
    // 但为了避免改变用户当前视角，我们不做额外操作
  }
}

// 将所有轨迹居中显示（四周留 5% 空间）
function fitBounds() {
  if (!AMapInstance) return

  // 计算所有轨迹的边界
  const AMap = (window as any).AMap
  const bounds: any[] = []

  for (const track of props.tracks) {
    if (!track.points || track.points.length === 0) continue
    for (const point of track.points) {
      const coords = getGCJ02Coords(point)
      if (!coords) continue
      const [lng, lat] = coords
      if (!isNaN(lat) && !isNaN(lng)) {
        bounds.push(new AMap.LngLat(lng, lat))
      }
    }
  }

  if (bounds.length === 0) return

  // 获取地图容器尺寸，计算 5% 的 padding
  const mapContainer = document.querySelector('.amap') as HTMLElement
  if (!mapContainer) return
  const width = mapContainer.clientWidth
  const height = mapContainer.clientHeight
  const padding = Math.round(Math.max(width, height) * 0.05)

  try {
    AMapInstance.setFitView(null, false, [padding, padding, padding, padding])
  } catch (e) {
    console.error('[AMap] fitBounds failed:', e)
  }
}

// 暴露方法给父组件
defineExpose({
  highlightPoint,
  hideMarker,
  resize,
  fitBounds,
  getMapElement: () => mapContainer.value || null,
})
</script>

<style scoped>
.amap-container {
  width: 100%;
  height: 100%;
  position: relative;
}

.amap {
  width: 100%;
  height: 100%;
}

/* 道路标志 SVG 行内显示 */
:deep(.road-sign-inline),
:deep(.amap-marker-content .road-sign-inline),
:deep(.amap-info-window-content .road-sign-inline) {
  display: inline-flex;
  align-items: center;
  vertical-align: middle;
  line-height: 1;
  margin: 0 1px;
}

:deep(.road-sign-inline svg),
:deep(.amap-marker-content .road-sign-inline svg),
:deep(.amap-info-window-content .road-sign-inline svg) {
  display: block;
  height: 1.4em;
  width: auto;
}
</style>
