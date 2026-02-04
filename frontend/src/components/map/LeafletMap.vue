<template>
  <div class="leaflet-map-container">
    <div ref="mapContainer" class="map"></div>
    <div class="map-controls" v-if="!hideLayerSelector">
      <!-- 桌面端：按钮组 -->
      <el-button-group size="small" class="desktop-layer-selector">
        <el-button
          v-for="layer in mapLayers"
          :key="layer.id"
          :type="currentLayerId === layer.id ? 'primary' : ''"
          @click="switchLayer(layer.id)"
        >
          {{ layer.name }}
        </el-button>
      </el-button-group>
      <!-- 移动端：下拉选择器 -->
      <el-select
        v-model="currentLayerId"
        size="small"
        class="mobile-layer-selector"
        @change="switchLayer"
      >
        <el-option
          v-for="layer in mapLayers"
          :key="layer.id"
          :label="layer.name"
          :value="layer.id"
        />
      </el-select>
      <el-button-group size="small" class="fullscreen-btn">
        <el-button @click="toggleFullscreen">
          <el-icon><FullScreen /></el-icon>
        </el-button>
      </el-button-group>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, Ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import 'proj4leaflet'
import 'leaflet.chinatmsproviders'
import { useConfigStore } from '@/stores/config'
import { FullScreen } from '@element-plus/icons-vue'
import type { MapLayerConfig, CRSType } from '@/api/admin'
import { roadSignApi } from '@/api/roadSign'
import { parseRoadNumber, type ParsedRoadNumber } from '@/utils/roadSignParser'
import { formatDistance, formatDuration } from '@/utils/format'
// import { wgs84ToGcj02, wgs84ToBd09 } from '@/utils/coordTransform'

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
  hideLayerSelector?: boolean
  mode?: 'home' | 'detail'
}

const props = withDefaults(defineProps<Props>(), {
  tracks: () => [],
  highlightTrackId: undefined,
  highlightSegment: null,
  highlightPointIndex: undefined,
  latestPointIndex: null,
  defaultLayerId: undefined,
  hideLayerSelector: false,
  mode: 'detail',
})

const emit = defineEmits<{
  (e: 'point-click', point: Point, trackId: number): void
  (e: 'point-hover', point: Point | null, pointIndex: number): void
  (e: 'track-hover', trackId: number | null): void
  (e: 'track-click', trackId: number): void
}>()

const configStore = useConfigStore()

// 地图实例
const mapContainer = ref<HTMLElement>()
const map = ref<L.Map | null>(null)
const polylineLayers = ref<Map<number, L.Polyline>>(new Map())
const markers = ref<L.Marker[]>([])
const highlightPolyline = ref<L.Polyline | null>(null)  // 路径段高亮图层

// 轨迹数据 - detail 模式使用（合并所有轨迹）
const trackPoints: Ref<Point[]> = ref([])
const trackPath: Ref<[number, number][]> = ref([])

// 轨迹数据 - home 模式使用（按轨迹分开存储）
const tracksData: Ref<Map<number, { points: Point[]; path: [number, number][]; track: Track }>> = ref(new Map())

// 鼠标标记和 tooltip
const mouseMarker = ref<L.Marker | null>(null)
const latestPointMarker = ref<L.Marker | null>(null)  // 实时轨迹最新点标记（绿色）
const customTooltip = ref<HTMLElement | null>(null)  // 自定义 tooltip 元素
const lastHoverIndex = ref(-1)
const currentHighlightPoint = ref<{ index: number; position: [number, number] } | null>(null)  // 当前高亮的点（detail 模式）
const currentHoverTrack = ref<{ trackId: number; position: [number, number]; track: Track } | null>(null)  // 当前悬停的轨迹（home 模式）

// 道路标志 SVG 缓存
const roadSignSvgCache = ref<Map<string, string>>(new Map())
const loadingSigns = ref<Set<string>>(new Set())
const currentTooltipPoint = ref<Point | null>(null)  // 当前 tooltip 显示的点（用于异步更新）
const tooltipContentCache = ref<Map<number, string>>(new Map())  // 缓存每个点的 tooltip 内容

// 节流优化：requestAnimationFrame ID
let rafId: number | null = null
let pendingUpdate: { pointPixel: L.Point; containerSize: { x: number; y: number } } | null = null

// 当前底图层 ID
const currentLayerId = ref<string>(
  props.defaultLayerId || configStore.getMapProvider()
)

// 当前地图层配置
const currentLayerConfig = ref<MapLayerConfig | undefined>(undefined)

// 当前使用的 CRS
const currentCRS = ref<L.CRS>(L.CRS.EPSG3857)

// 可用的地图层列表
const mapLayers = ref<MapLayerConfig[]>([])

// 初始化地图层列表
function initMapLayers() {
  mapLayers.value = configStore.getMapLayers()
  // 如果当前层不在列表中，使用第一个或默认
  const defaultId = props.defaultLayerId || configStore.getMapProvider()
  const exists = mapLayers.value.find((l: MapLayerConfig) => l.id === defaultId)
  if (exists) {
    currentLayerId.value = defaultId
  } else if (mapLayers.value.length > 0) {
    currentLayerId.value = mapLayers.value[0].id
  }
  updateCurrentLayerConfig()
}

// 更新当前地图层配置
function updateCurrentLayerConfig() {
  currentLayerConfig.value = configStore.getMapLayerById(currentLayerId.value)
}

// 根据坐标系类型获取 CRS
// leaflet.chinatmsproviders 会注册 L.CRS.Baidu
function getCRS(crsType: CRSType): L.CRS {
  if (crsType === 'bd09') {
    // 百度地图使用专门的 CRS
    return (L.CRS as any).Baidu || L.CRS.EPSG3857
  }
  // 天地图和高德地图都使用 GCJ02，但天地图不需要特殊的 CRS
  return L.CRS.EPSG3857
}

// 初始化地图
function initMap() {
  if (!mapContainer.value) {
    return
  }

  // 获取当前层配置
  const layerConfig = currentLayerConfig.value
  const crs = layerConfig ? getCRS(layerConfig.crs) : L.CRS.EPSG3857
  currentCRS.value = crs

  // 创建地图
  map.value = L.map(mapContainer.value, {
    center: [39.9, 116.4],
    zoom: 10,
    zoomControl: true,
    crs: crs,
  })

  // 添加默认底图（使用当前提供商）
  addTileLayer(currentLayerId.value)

  // 添加比例尺
  L.control.scale({
    position: 'bottomleft',
    imperial: false, // 不使用英制单位
  }).addTo(map.value as L.Map)

  // 创建标记和提示框
  createMouseMarker()
  createLatestPointMarker()
  createCustomTooltip()

  // 统一的鼠标处理函数
  const handleMouseMove = (lng: number, lat: number) => {
    if (props.mode === 'home') {
      // home 模式：显示轨迹信息
      handleHomeModeMouseMove(lng, lat)
    } else {
      // detail 模式：显示点信息
      handleDetailModeMouseMove(lng, lat)
    }
  }

  // detail 模式：显示最近的点信息
  const handleDetailModeMouseMove = (lng: number, lat: number) => {
    if (trackPath.value.length < 2) return

    const mouseLngLat: [number, number] = [lng, lat]
    const zoom = map.value!.getZoom()
    const dynamicDistance = Math.pow(2, 12 - zoom) * 0.008

    let minDistance = Infinity
    let nearestIndex = -1
    let nearestPosition: [number, number] = [0, 0]

    // 快速查找最近的点
    for (let i = 0; i < trackPath.value.length - 1; i++) {
      const p1 = trackPath.value[i]
      const p2 = trackPath.value[i + 1]
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
    if (triggered && nearestIndex >= 0 && nearestIndex < trackPoints.value.length) {
      const point = trackPoints.value[nearestIndex]

      // 检查点索引是否变化
      const indexChanged = nearestIndex !== lastHoverIndex.value

      if (indexChanged) {
        lastHoverIndex.value = nearestIndex

        // 生成或获取缓存的 tooltip 内容
        let content = tooltipContentCache.value.get(nearestIndex)
        if (!content) {
          const timeStr = point.time ? new Date(point.time).toLocaleTimeString('zh-CN') : '-'
          const elevation = point.elevation != null ? `${point.elevation.toFixed(1)} m` : '-'
          const speed = point.speed != null ? `${(point.speed * 3.6).toFixed(1)} km/h` : '-'
          const locationResult = formatLocationInfo(point)
          const locationHtml = locationResult.html || ''

          content = `
            <div style="padding: 8px 12px; background: rgba(255, 255, 255, 0.95); border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-size: 12px; line-height: 1.6;">
              <div style="font-weight: bold; color: #333; margin-bottom: 4px;">点 #${nearestIndex}</div>
              ${locationHtml ? `<div style="color: #666;">${locationHtml}</div>` : ''}
              <div style="color: #666;">时间: ${timeStr}</div>
              <div style="color: #666;">速度: ${speed}</div>
              <div style="color: #666;">海拔: ${elevation}</div>
            </div>
          `
          tooltipContentCache.value.set(nearestIndex, content)

          // 异步加载道路标志 SVG
          if (locationResult.needLoad.length > 0) {
            nextTick(async () => {
              const loaded = await loadRoadSignsForTooltip(locationResult.needLoad)
              if (loaded) {
                // 清除缓存，下次会重新生成
                tooltipContentCache.value.delete(nearestIndex)
                // 如果当前还在显示同一个点，更新 tooltip
                if (lastHoverIndex.value === nearestIndex) {
                  // 强制下次鼠标移动时重新生成内容
                  lastHoverIndex.value = -1
                }
              }
            })
          }
        }

        // 更新 tooltip 内容（只在索引变化时）
        if (customTooltip.value && mapContainer) {
          customTooltip.value.innerHTML = content
          customTooltip.value.style.display = 'block'
        }

        // 发射事件
        emit('point-hover', point, nearestIndex)
      }

      // 每次鼠标移动都更新标记位置（轻量级操作）
      if (mouseMarker.value) {
        mouseMarker.value.setLatLng([nearestPosition[1], nearestPosition[0]])
        mouseMarker.value.addTo(map.value!)
      }

      // 每次鼠标移动都更新 tooltip 位置（轻量级操作）
      if (customTooltip.value && mapContainer) {
        const pointPixel = map.value!.latLngToContainerPoint([nearestPosition[1], nearestPosition[0]])
        const containerSize = { x: mapContainer.value?.clientWidth || map.value?.getContainer()?.clientWidth || 800, y: mapContainer.value?.clientHeight || map.value?.getContainer()?.clientHeight || 600 }
        updateCustomTooltipPosition(pointPixel, containerSize)
      }
    } else {
      hideMarker()
    }
  }

  // home 模式：显示最近的轨迹信息
  const handleHomeModeMouseMove = (lng: number, lat: number) => {
    const mouseLngLat: [number, number] = [lng, lat]
    const zoom = map.value!.getZoom()
    const dynamicDistance = Math.pow(2, 12 - zoom) * 0.008

    let minDistance = Infinity
    let nearestTrackId: number | null = null
    let nearestPosition: [number, number] = [0, 0]

    // 遍历所有轨迹，找到最近的轨迹
    for (const [trackId, data] of tracksData.value) {
      if (data.path.length < 2) continue

      for (let i = 0; i < data.path.length - 1; i++) {
        const p1 = data.path[i]
        const p2 = data.path[i + 1]
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
      const trackData = tracksData.value.get(nearestTrackId)
      if (!trackData) return

      const track = trackData.track

      // 检查位置是否发生了显著变化（用于地图移动时更新 tooltip）
      const positionChanged = !currentHoverTrack.value ||
        currentHoverTrack.value.trackId !== nearestTrackId ||
        distance(currentHoverTrack.value.position, nearestPosition) > 0.0001

      // 如果是同一条轨迹且位置没有变化，跳过更新
      if (!positionChanged && nearestTrackId === lastHoverIndex.value) return

      lastHoverIndex.value = nearestTrackId

      // 保存当前悬停的轨迹信息（用于地图移动时更新）
      currentHoverTrack.value = { trackId: nearestTrackId, position: nearestPosition, track }

      // 更新标记位置并显示
      if (mouseMarker.value) {
        mouseMarker.value.setLatLng([nearestPosition[1], nearestPosition[0]])
        mouseMarker.value.addTo(map.value!)
      }

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
        <div class="track-tooltip" data-track-id="${track.id}" style="padding: 8px 12px; background: rgba(255, 255, 255, 0.95); border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-size: 12px; line-height: 1.6; cursor: pointer;">
          <div style="font-weight: bold; color: #333; margin-bottom: 4px;">${track.name || '未命名轨迹'}</div>
          <div style="color: #666;">时间: ${formatTimeRange()}</div>
          <div style="color: #666;">里程: ${formatDistance(track.distance)}</div>
          <div style="color: #666;">历时: ${formatDuration(track.duration)}</div>
          ${isMobile ? '<div style="font-size: 10px; color: #409eff; margin-top: 4px;">点击查看详情</div>' : ''}
        </div>
      `

      // 使用自定义 tooltip
      if (customTooltip.value && mapContainer) {
        const pointPixel = map.value!.latLngToContainerPoint([nearestPosition[1], nearestPosition[0]])
        const containerSize = { x: mapContainer.value?.clientWidth || map.value?.getContainer()?.clientWidth || 800, y: mapContainer.value?.clientHeight || map.value?.getContainer()?.clientHeight || 600 }
        updateCustomTooltip(content, pointPixel, containerSize)
      }

      // 发射事件
      emit('track-hover', nearestTrackId)
    } else {
      hideMarker()
      emit('track-hover', null)
    }
  }

  // Leaflet mousemove 监听
  map.value.on('mousemove', (e: L.LeafletMouseEvent) => {
    handleMouseMove(e.latlng.lng, e.latlng.lat)
  })

  // 地图移动时更新 tooltip 位置（保持 tooltip 与点同步）
  map.value.on('move', () => {
    if (props.mode === 'home') {
      // home 模式：更新轨迹 tooltip 位置
      if (currentHoverTrack.value && customTooltip.value && mapContainer) {
        const { track, position } = currentHoverTrack.value
        const pointPixel = map.value!.latLngToContainerPoint([position[1], position[0]])
        const containerSize = { x: mapContainer.value?.clientWidth || map.value?.getContainer()?.clientWidth || 800, y: mapContainer.value?.clientHeight || map.value?.getContainer()?.clientHeight || 600 }

        // 重新生成内容
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
          <div style="padding: 8px 12px; background: rgba(255, 255, 255, 0.95); border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-size: 12px; line-height: 1.6;">
            <div style="font-weight: bold; color: #333; margin-bottom: 4px;">${track.name || '未命名轨迹'}</div>
            <div style="color: #666;">时间: ${formatTimeRange()}</div>
            <div style="color: #666;">里程: ${formatDistance(track.distance)}</div>
            <div style="color: #666;">历时: ${formatDuration(track.duration)}</div>
          </div>
        `

        updateCustomTooltip(content, pointPixel, containerSize)
      }
    } else {
      // detail 模式：更新点 tooltip 位置
      if (currentHighlightPoint.value && currentHighlightPoint.value.index >= 0 && currentHighlightPoint.value.index < trackPoints.value.length) {
        const point = trackPoints.value[currentHighlightPoint.value.index]
        updateTooltipForPoint(currentHighlightPoint.value.index, point)
      }
    }
  })

  // 移动端：点击地图显示轨迹信息
  const isMobile = window.innerWidth <= 1366
  if (isMobile) {
    map.value.on('click', (e: L.LeafletMouseEvent) => {
      const lng = e.latlng.lng
      const lat = e.latlng.lat

      if (props.mode === 'home') {
        // home 模式：显示轨迹信息
        if (tracksData.value.size === 0) {
          hideMarker()
          return
        }

        const zoom = map.value!.getZoom()
        const dynamicDistance = Math.pow(2, 12 - zoom) * 0.008

        let minDistance = Infinity
        let nearestTrackId: number | null = null
        let nearestPosition: [number, number] = [0, 0]

        // 遍历所有轨迹，找到最近的轨迹
        for (const [trackId, data] of tracksData.value) {
          if (data.path.length < 2) continue

          for (let i = 0; i < data.path.length - 1; i++) {
            const p1 = data.path[i]
            const p2 = data.path[i + 1]
            const closest = closestPointOnSegment([lng, lat], p1, p2)
            const dist = distance([lng, lat], closest)

            if (dist < minDistance) {
              minDistance = dist
              nearestPosition = closest
              nearestTrackId = trackId
            }
          }
        }

        const triggered = minDistance < dynamicDistance

        if (triggered && nearestTrackId !== null) {
          const trackData = tracksData.value.get(nearestTrackId)
          if (!trackData) return

          const track = trackData.track
          lastHoverIndex.value = nearestTrackId

          // 更新标记位置并显示
          if (mouseMarker.value) {
            mouseMarker.value.setLatLng([nearestPosition[1], nearestPosition[0]])
            mouseMarker.value.addTo(map.value!)
          }

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
            <div class="track-tooltip" data-track-id="${track.id}" style="padding: 8px 12px; background: rgba(255, 255, 255, 0.95); border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-size: 12px; line-height: 1.6; cursor: pointer;">
              <div style="font-weight: bold; color: #333; margin-bottom: 4px;">${track.name || '未命名轨迹'}</div>
              <div style="color: #666;">时间: ${formatTimeRange()}</div>
              <div style="color: #666;">里程: ${formatDistance(track.distance)}</div>
              <div style="color: #666;">历时: ${formatDuration(track.duration)}</div>
              <div style="font-size: 10px; color: #409eff; margin-top: 4px;">点击查看详情</div>
            </div>
          `

          if (customTooltip.value && mapContainer) {
            const pointPixel = map.value!.latLngToContainerPoint([nearestPosition[1], nearestPosition[0]])
            const containerSize = { x: mapContainer.value?.clientWidth || map.value?.getContainer()?.clientWidth || 800, y: mapContainer.value?.clientHeight || map.value?.getContainer()?.clientHeight || 600 }
            updateCustomTooltip(content, pointPixel, containerSize)
          }

          emit('track-hover', nearestTrackId)
        } else {
          hideMarker()
        }
      } else {
        // detail 模式：显示点信息
        if (trackPath.value.length < 2) {
          hideMarker()
          return
        }

        const zoom = map.value!.getZoom()
        const dynamicDistance = Math.pow(2, 12 - zoom) * 0.008

        let minDistance = Infinity
        let nearestIndex = -1
        let nearestPosition: [number, number] = [0, 0]

        // 查找最近的点
        for (let i = 0; i < trackPath.value.length - 1; i++) {
          const p1 = trackPath.value[i]
          const p2 = trackPath.value[i + 1]
          const closest = closestPointOnSegment([lng, lat], p1, p2)
          const dist = distance([lng, lat], closest)

          if (dist < minDistance) {
            minDistance = dist
            nearestPosition = closest
            const distToP1 = distance(closest, p1)
            const distToP2 = distance(closest, p2)
            nearestIndex = distToP1 < distToP2 ? i : i + 1
          }
        }

        const triggered = minDistance < dynamicDistance

        if (triggered && nearestIndex >= 0 && nearestIndex < trackPoints.value.length) {
          const point = trackPoints.value[nearestIndex]

          if (mouseMarker.value) {
            mouseMarker.value.setLatLng([nearestPosition[1], nearestPosition[0]])
            mouseMarker.value.addTo(map.value!)
          }

          const timeStr = point.time ? new Date(point.time).toLocaleTimeString('zh-CN') : '-'
          const elevation = point.elevation != null ? `${point.elevation.toFixed(1)} m` : '-'
          const speed = point.speed != null ? `${(point.speed * 3.6).toFixed(1)} km/h` : '-'
          const locationResult = formatLocationInfo(point)
          const locationHtml = locationResult.html || ''

          const content = `
            <div style="padding: 8px 12px; background: rgba(255, 255, 255, 0.95); border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-size: 12px; line-height: 1.6;">
              <div style="font-weight: bold; color: #333; margin-bottom: 4px;">点 #${nearestIndex}</div>
              ${locationHtml ? `<div style="color: #666;">${locationHtml}</div>` : ''}
              <div style="color: #666;">时间: ${timeStr}</div>
              <div style="color: #666;">速度: ${speed}</div>
              <div style="color: #666;">海拔: ${elevation}</div>
            </div>
          `

          if (customTooltip.value && mapContainer) {
            const pointPixel = map.value!.latLngToContainerPoint([nearestPosition[1], nearestPosition[0]])
            const containerSize = { x: mapContainer.value?.clientWidth || map.value?.getContainer()?.clientWidth || 800, y: mapContainer.value?.clientHeight || map.value?.getContainer()?.clientHeight || 600 }
            updateCustomTooltip(content, pointPixel, containerSize)
          }

          lastHoverIndex.value = nearestIndex
          emit('point-hover', point, nearestIndex)
        } else {
          hideMarker()
        }
      }
    })
  }
}

// 添加底图
function addTileLayer(layerId: string) {
  if (!map.value) return

  // 切换底图时清除提示框和标记
  hideMarker()

  const layerConfig = configStore.getMapLayerById(layerId)
  if (!layerConfig) {
    console.error('[LeafletMap] Layer not found:', layerId)
    return
  }

  // 移除现有底图
  map.value.eachLayer((layer: L.Layer) => {
    if (layer instanceof L.TileLayer) {
      map.value!.removeLayer(layer)
    }
  })

  // 添加新底图
  // 使用 leaflet.chinatmsproviders 提供的中国地图瓦片
  if (layerConfig.crs === 'bd09') {
    // 百度地图
    const chinaProvider = (L.tileLayer as any).chinaProvider
    if (chinaProvider) {
      chinaProvider('Baidu.Normal.Map', {
        maxZoom: layerConfig.max_zoom,
        minZoom: layerConfig.min_zoom,
        attribution: layerConfig.attribution,
      }).addTo(map.value)
    } else if (layerConfig.url) {
      // 降级方案：使用配置的 URL
      L.tileLayer(layerConfig.url, {
        maxZoom: layerConfig.max_zoom,
        minZoom: layerConfig.min_zoom,
        attribution: layerConfig.attribution,
        subdomains: layerConfig.subdomains || undefined,
      }).addTo(map.value as L.Map)
    }
  } else if (layerConfig.crs === 'gcj02') {
    // 高德地图、腾讯地图、智图和天地图都使用 GCJ02 坐标系
    const chinaProvider = (L.tileLayer as any).chinaProvider
    if (chinaProvider) {
      // 根据地图 ID 使用不同的 provider
      if (layerConfig.id === 'tianditu') {
        // 天地图需要同时添加底图层和标注层
        const tk = layerConfig.tk || ''
        chinaProvider('TianDiTu.Normal.Map', {
          maxZoom: layerConfig.max_zoom,
          minZoom: layerConfig.min_zoom,
          key: tk,
          attribution: layerConfig.attribution,
        }).addTo(map.value)
        chinaProvider('TianDiTu.Normal.Annotion', {
          maxZoom: layerConfig.max_zoom,
          minZoom: layerConfig.min_zoom,
          key: tk,
        }).addTo(map.value)
      } else if (layerConfig.id === 'tencent') {
        // 腾讯地图（矢量）
        chinaProvider('Tencent.Normal.Map', {
          maxZoom: layerConfig.max_zoom,
          minZoom: layerConfig.min_zoom,
          attribution: layerConfig.attribution,
        }).addTo(map.value)
      } else if (layerConfig.id === 'google') {
        // Google 地图
        chinaProvider('Google.Normal.Map', {
          maxZoom: layerConfig.max_zoom,
          minZoom: layerConfig.min_zoom,
          attribution: layerConfig.attribution,
        }).addTo(map.value)
      } else if (layerConfig.id === 'amap_satellite') {
        // 高德卫星图 + 注记
        chinaProvider('GaoDe.Satellite.Map', {
          maxZoom: layerConfig.max_zoom,
          minZoom: layerConfig.min_zoom,
          attribution: layerConfig.attribution,
        }).addTo(map.value)
        chinaProvider('GaoDe.Satellite.Annot', {
          maxZoom: layerConfig.max_zoom,
          minZoom: layerConfig.min_zoom,
        }).addTo(map.value)
      } else if (layerConfig.id === 'baidu_satellite') {
        // 百度卫星图 + 注记
        chinaProvider('Baidu.Satellite.Map', {
          maxZoom: layerConfig.max_zoom,
          minZoom: layerConfig.min_zoom,
          attribution: layerConfig.attribution,
        }).addTo(map.value)
        chinaProvider('Baidu.Satellite.Annot', {
          maxZoom: layerConfig.max_zoom,
          minZoom: layerConfig.min_zoom,
        }).addTo(map.value)
      } else if (layerConfig.id === 'google_satellite') {
        // Google 卫星图 + 注记
        chinaProvider('Google.Satellite.Map', {
          maxZoom: layerConfig.max_zoom,
          minZoom: layerConfig.min_zoom,
          attribution: layerConfig.attribution,
        }).addTo(map.value)
        chinaProvider('Google.Satellite.Annot', {
          maxZoom: layerConfig.max_zoom,
          minZoom: layerConfig.min_zoom,
        }).addTo(map.value)
      } else if (layerConfig.id === 'tencent_satellite') {
        // 腾讯卫星图
        chinaProvider('Tencent.Satellite.Map', {
          maxZoom: layerConfig.max_zoom,
          minZoom: layerConfig.min_zoom,
          attribution: layerConfig.attribution,
        }).addTo(map.value)
      } else if (layerConfig.id === 'tianditu_satellite') {
        // 天地图卫星 + 注记
        const tk = layerConfig.tk || ''
        chinaProvider('TianDiTu.Satellite.Map', {
          maxZoom: layerConfig.max_zoom,
          minZoom: layerConfig.min_zoom,
          key: tk,
          attribution: layerConfig.attribution,
        }).addTo(map.value)
        chinaProvider('TianDiTu.Satellite.Annot', {
          maxZoom: layerConfig.max_zoom,
          minZoom: layerConfig.min_zoom,
          key: tk,
        }).addTo(map.value)
      } else if (layerConfig.id === 'tianditu_terrain') {
        // 天地图地形 + 注记
        const tk = layerConfig.tk || ''
        chinaProvider('TianDiTu.Terrain.Map', {
          maxZoom: layerConfig.max_zoom,
          minZoom: layerConfig.min_zoom,
          key: tk,
          attribution: layerConfig.attribution,
        }).addTo(map.value)
        chinaProvider('TianDiTu.Terrain.Annot', {
          maxZoom: layerConfig.max_zoom,
          minZoom: layerConfig.min_zoom,
          key: tk,
        }).addTo(map.value)
      } else if (layerConfig.id === 'tencent_terrain') {
        // 腾讯地形图
        chinaProvider('Tencent.Terrain.Map', {
          maxZoom: layerConfig.max_zoom,
          minZoom: layerConfig.min_zoom,
          attribution: layerConfig.attribution,
        }).addTo(map.value)
      } else {
        // 高德地图
        chinaProvider('GaoDe.Normal.Map', {
          maxZoom: layerConfig.max_zoom,
          minZoom: layerConfig.min_zoom,
          attribution: layerConfig.attribution,
        }).addTo(map.value)
      }
    } else if (layerConfig.url) {
      // 降级方案：使用配置的 URL
      L.tileLayer(layerConfig.url, {
        maxZoom: layerConfig.max_zoom,
        minZoom: layerConfig.min_zoom,
        attribution: layerConfig.attribution,
        subdomains: layerConfig.subdomains || undefined,
      }).addTo(map.value as L.Map)
    }
  } else {
    // OSM 或其他 WGS84 地图，使用配置的 URL
    if (layerConfig.url) {
      L.tileLayer(layerConfig.url, {
        maxZoom: layerConfig.max_zoom,
        minZoom: layerConfig.min_zoom,
        attribution: layerConfig.attribution,
        subdomains: layerConfig.subdomains || undefined,
      }).addTo(map.value as L.Map)
    }
  }
}

// 切换底图
function switchLayer(layerId: string) {
  const newLayerConfig = configStore.getMapLayerById(layerId)
  if (!newLayerConfig) return

  // 检查 CRS 是否需要改变
  const newCRS = getCRS(newLayerConfig.crs)
  const needsRecreate = currentLayerConfig.value?.crs !== newLayerConfig.crs

  currentLayerId.value = layerId
  updateCurrentLayerConfig()

  if (needsRecreate) {
    // CRS 不同，需要重新创建地图
    currentCRS.value = newCRS
    recreateMap()
  } else {
    // CRS 相同，只需要切换瓦片层
    addTileLayer(layerId)
  }

  // 重新绘制轨迹（使用正确的坐标系）
  updateTracks()
}

// 重新创建地图（用于切换 CRS）
function recreateMap() {
  if (!mapContainer.value) return

  // 移除旧地图
  if (map.value) {
    map.value.remove()
  }

  // 获取当前视图状态
  const layerConfig = currentLayerConfig.value
  const crs = layerConfig ? getCRS(layerConfig.crs) : L.CRS.EPSG3857

  // 创建新地图
  map.value = L.map(mapContainer.value, {
    center: [39.9, 116.4],
    zoom: 10,
    zoomControl: true,
    crs: crs,
  })

  // 添加底图
  addTileLayer(currentLayerId.value)

  // 添加比例尺
  L.control.scale({
    position: 'bottomleft',
    imperial: false,
  }).addTo(map.value as L.Map)

  // 创建标记和提示框
  createMouseMarker()
  createLatestPointMarker()
  createCustomTooltip()

  // 统一的鼠标处理函数
  const handleMouseMove = (lng: number, lat: number) => {
    if (props.mode === 'home') {
      // home 模式：显示轨迹信息
      handleHomeModeMouseMove(lng, lat)
    } else {
      // detail 模式：显示点信息
      handleDetailModeMouseMove(lng, lat)
    }
  }

  // detail 模式：显示最近的点信息
  const handleDetailModeMouseMove = (lng: number, lat: number) => {
    if (trackPath.value.length < 2) return

    const mouseLngLat: [number, number] = [lng, lat]
    const zoom = map.value!.getZoom()
    const dynamicDistance = Math.pow(2, 12 - zoom) * 0.008

    let minDistance = Infinity
    let nearestIndex = -1
    let nearestPosition: [number, number] = [0, 0]

    // 快速查找最近的点
    for (let i = 0; i < trackPath.value.length - 1; i++) {
      const p1 = trackPath.value[i]
      const p2 = trackPath.value[i + 1]
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
    if (triggered && nearestIndex >= 0 && nearestIndex < trackPoints.value.length) {
      const point = trackPoints.value[nearestIndex]

      // 检查点索引是否变化
      const indexChanged = nearestIndex !== lastHoverIndex.value

      if (indexChanged) {
        lastHoverIndex.value = nearestIndex

        // 生成或获取缓存的 tooltip 内容
        let content = tooltipContentCache.value.get(nearestIndex)
        if (!content) {
          const timeStr = point.time ? new Date(point.time).toLocaleTimeString('zh-CN') : '-'
          const elevation = point.elevation != null ? `${point.elevation.toFixed(1)} m` : '-'
          const speed = point.speed != null ? `${(point.speed * 3.6).toFixed(1)} km/h` : '-'
          const locationResult = formatLocationInfo(point)
          const locationHtml = locationResult.html || ''

          content = `
            <div style="padding: 8px 12px; background: rgba(255, 255, 255, 0.95); border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-size: 12px; line-height: 1.6;">
              <div style="font-weight: bold; color: #333; margin-bottom: 4px;">点 #${nearestIndex}</div>
              ${locationHtml ? `<div style="color: #666;">${locationHtml}</div>` : ''}
              <div style="color: #666;">时间: ${timeStr}</div>
              <div style="color: #666;">速度: ${speed}</div>
              <div style="color: #666;">海拔: ${elevation}</div>
            </div>
          `
          tooltipContentCache.value.set(nearestIndex, content)

          // 异步加载道路标志 SVG
          if (locationResult.needLoad.length > 0) {
            nextTick(async () => {
              const loaded = await loadRoadSignsForTooltip(locationResult.needLoad)
              if (loaded) {
                // 清除缓存，下次会重新生成
                tooltipContentCache.value.delete(nearestIndex)
                // 如果当前还在显示同一个点，更新 tooltip
                if (lastHoverIndex.value === nearestIndex) {
                  // 强制下次鼠标移动时重新生成内容
                  lastHoverIndex.value = -1
                }
              }
            })
          }
        }

        // 更新 tooltip 内容（只在索引变化时）
        if (customTooltip.value && mapContainer) {
          customTooltip.value.innerHTML = content
          customTooltip.value.style.display = 'block'
        }

        // 发射事件
        emit('point-hover', point, nearestIndex)
      }

      // 每次鼠标移动都更新标记位置（轻量级操作）
      if (mouseMarker.value) {
        mouseMarker.value.setLatLng([nearestPosition[1], nearestPosition[0]])
        mouseMarker.value.addTo(map.value!)
      }

      // 每次鼠标移动都更新 tooltip 位置（轻量级操作）
      if (customTooltip.value && mapContainer) {
        const pointPixel = map.value!.latLngToContainerPoint([nearestPosition[1], nearestPosition[0]])
        const containerSize = { x: mapContainer.value?.clientWidth || map.value?.getContainer()?.clientWidth || 800, y: mapContainer.value?.clientHeight || map.value?.getContainer()?.clientHeight || 600 }
        updateCustomTooltipPosition(pointPixel, containerSize)
      }
    } else {
      hideMarker()
    }
  }

  // home 模式：显示最近的轨迹信息
  const handleHomeModeMouseMove = (lng: number, lat: number) => {
    const mouseLngLat: [number, number] = [lng, lat]
    const zoom = map.value!.getZoom()
    const dynamicDistance = Math.pow(2, 12 - zoom) * 0.008

    let minDistance = Infinity
    let nearestTrackId: number | null = null
    let nearestPosition: [number, number] = [0, 0]

    // 遍历所有轨迹，找到最近的轨迹
    for (const [trackId, data] of tracksData.value) {
      if (data.path.length < 2) continue

      for (let i = 0; i < data.path.length - 1; i++) {
        const p1 = data.path[i]
        const p2 = data.path[i + 1]
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
      const trackData = tracksData.value.get(nearestTrackId)
      if (!trackData) return

      const track = trackData.track

      // 检查位置是否发生了显著变化（用于地图移动时更新 tooltip）
      const positionChanged = !currentHoverTrack.value ||
        currentHoverTrack.value.trackId !== nearestTrackId ||
        distance(currentHoverTrack.value.position, nearestPosition) > 0.0001

      // 如果是同一条轨迹且位置没有变化，跳过更新
      if (!positionChanged && nearestTrackId === lastHoverIndex.value) return

      lastHoverIndex.value = nearestTrackId

      // 保存当前悬停的轨迹信息（用于地图移动时更新）
      currentHoverTrack.value = { trackId: nearestTrackId, position: nearestPosition, track }

      // 更新标记位置并显示
      if (mouseMarker.value) {
        mouseMarker.value.setLatLng([nearestPosition[1], nearestPosition[0]])
        mouseMarker.value.addTo(map.value!)
      }

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
        <div class="track-tooltip" data-track-id="${track.id}" style="padding: 8px 12px; background: rgba(255, 255, 255, 0.95); border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-size: 12px; line-height: 1.6; cursor: pointer;">
          <div style="font-weight: bold; color: #333; margin-bottom: 4px;">${track.name || '未命名轨迹'}</div>
          <div style="color: #666;">时间: ${formatTimeRange()}</div>
          <div style="color: #666;">里程: ${formatDistance(track.distance)}</div>
          <div style="color: #666;">历时: ${formatDuration(track.duration)}</div>
          ${isMobile ? '<div style="font-size: 10px; color: #409eff; margin-top: 4px;">点击查看详情</div>' : ''}
        </div>
      `

      // 使用自定义 tooltip
      if (customTooltip.value && mapContainer) {
        const pointPixel = map.value!.latLngToContainerPoint([nearestPosition[1], nearestPosition[0]])
        const containerSize = { x: mapContainer.value?.clientWidth || map.value?.getContainer()?.clientWidth || 800, y: mapContainer.value?.clientHeight || map.value?.getContainer()?.clientHeight || 600 }
        updateCustomTooltip(content, pointPixel, containerSize)
      }

      // 发射事件
      emit('track-hover', nearestTrackId)
    } else {
      hideMarker()
      emit('track-hover', null)
    }
  }

  // Leaflet mousemove 监听
  map.value.on('mousemove', (e: L.LeafletMouseEvent) => {
    handleMouseMove(e.latlng.lng, e.latlng.lat)
  })

  // 地图移动时更新 tooltip 位置（保持 tooltip 与点同步）
  map.value.on('move', () => {
    if (props.mode === 'home') {
      // home 模式：更新轨迹 tooltip 位置
      if (currentHoverTrack.value && customTooltip.value && mapContainer) {
        const { track, position } = currentHoverTrack.value
        const pointPixel = map.value!.latLngToContainerPoint([position[1], position[0]])
        const containerSize = { x: mapContainer.value?.clientWidth || map.value?.getContainer()?.clientWidth || 800, y: mapContainer.value?.clientHeight || map.value?.getContainer()?.clientHeight || 600 }

        // 重新生成内容
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
          <div style="padding: 8px 12px; background: rgba(255, 255, 255, 0.95); border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-size: 12px; line-height: 1.6;">
            <div style="font-weight: bold; color: #333; margin-bottom: 4px;">${track.name || '未命名轨迹'}</div>
            <div style="color: #666;">时间: ${formatTimeRange()}</div>
            <div style="color: #666;">里程: ${formatDistance(track.distance)}</div>
            <div style="color: #666;">历时: ${formatDuration(track.duration)}</div>
          </div>
        `

        updateCustomTooltip(content, pointPixel, containerSize)
      }
    } else {
      // detail 模式：更新点 tooltip 位置
      if (currentHighlightPoint.value && currentHighlightPoint.value.index >= 0 && currentHighlightPoint.value.index < trackPoints.value.length) {
        const point = trackPoints.value[currentHighlightPoint.value.index]
        updateTooltipForPoint(currentHighlightPoint.value.index, point)
      }
    }
  })

  // 移动端：点击地图显示轨迹信息
  const isMobile = window.innerWidth <= 1366
  if (isMobile) {
    map.value.on('click', (e: L.LeafletMouseEvent) => {
      const lng = e.latlng.lng
      const lat = e.latlng.lat

      if (props.mode === 'home') {
        // home 模式：显示轨迹信息
        if (tracksData.value.size === 0) {
          hideMarker()
          return
        }

        const zoom = map.value!.getZoom()
        const dynamicDistance = Math.pow(2, 12 - zoom) * 0.008

        let minDistance = Infinity
        let nearestTrackId: number | null = null
        let nearestPosition: [number, number] = [0, 0]

        // 遍历所有轨迹，找到最近的轨迹
        for (const [trackId, data] of tracksData.value) {
          if (data.path.length < 2) continue

          for (let i = 0; i < data.path.length - 1; i++) {
            const p1 = data.path[i]
            const p2 = data.path[i + 1]
            const closest = closestPointOnSegment([lng, lat], p1, p2)
            const dist = distance([lng, lat], closest)

            if (dist < minDistance) {
              minDistance = dist
              nearestPosition = closest
              nearestTrackId = trackId
            }
          }
        }

        const triggered = minDistance < dynamicDistance

        if (triggered && nearestTrackId !== null) {
          const trackData = tracksData.value.get(nearestTrackId)
          if (!trackData) return

          const track = trackData.track
          lastHoverIndex.value = nearestTrackId

          // 更新标记位置并显示
          if (mouseMarker.value) {
            mouseMarker.value.setLatLng([nearestPosition[1], nearestPosition[0]])
            mouseMarker.value.addTo(map.value!)
          }

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
            <div class="track-tooltip" data-track-id="${track.id}" style="padding: 8px 12px; background: rgba(255, 255, 255, 0.95); border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-size: 12px; line-height: 1.6; cursor: pointer;">
              <div style="font-weight: bold; color: #333; margin-bottom: 4px;">${track.name || '未命名轨迹'}</div>
              <div style="color: #666;">时间: ${formatTimeRange()}</div>
              <div style="color: #666;">里程: ${formatDistance(track.distance)}</div>
              <div style="color: #666;">历时: ${formatDuration(track.duration)}</div>
              <div style="font-size: 10px; color: #409eff; margin-top: 4px;">点击查看详情</div>
            </div>
          `

          if (customTooltip.value && mapContainer) {
            const pointPixel = map.value!.latLngToContainerPoint([nearestPosition[1], nearestPosition[0]])
            const containerSize = { x: mapContainer.value?.clientWidth || map.value?.getContainer()?.clientWidth || 800, y: mapContainer.value?.clientHeight || map.value?.getContainer()?.clientHeight || 600 }
            updateCustomTooltip(content, pointPixel, containerSize)
          }

          emit('track-hover', nearestTrackId)
        } else {
          hideMarker()
        }
      } else {
        // detail 模式：显示点信息
        if (trackPath.value.length < 2) {
          hideMarker()
          return
        }

        const zoom = map.value!.getZoom()
        const dynamicDistance = Math.pow(2, 12 - zoom) * 0.008

        let minDistance = Infinity
        let nearestIndex = -1
        let nearestPosition: [number, number] = [0, 0]

        // 查找最近的点
        for (let i = 0; i < trackPath.value.length - 1; i++) {
          const p1 = trackPath.value[i]
          const p2 = trackPath.value[i + 1]
          const closest = closestPointOnSegment([lng, lat], p1, p2)
          const dist = distance([lng, lat], closest)

          if (dist < minDistance) {
            minDistance = dist
            nearestPosition = closest
            const distToP1 = distance(closest, p1)
            const distToP2 = distance(closest, p2)
            nearestIndex = distToP1 < distToP2 ? i : i + 1
          }
        }

        const triggered = minDistance < dynamicDistance

        if (triggered && nearestIndex >= 0 && nearestIndex < trackPoints.value.length) {
          const point = trackPoints.value[nearestIndex]

          if (mouseMarker.value) {
            mouseMarker.value.setLatLng([nearestPosition[1], nearestPosition[0]])
            mouseMarker.value.addTo(map.value!)
          }

          const timeStr = point.time ? new Date(point.time).toLocaleTimeString('zh-CN') : '-'
          const elevation = point.elevation != null ? `${point.elevation.toFixed(1)} m` : '-'
          const speed = point.speed != null ? `${(point.speed * 3.6).toFixed(1)} km/h` : '-'
          const locationResult = formatLocationInfo(point)
          const locationHtml = locationResult.html || ''

          const content = `
            <div style="padding: 8px 12px; background: rgba(255, 255, 255, 0.95); border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-size: 12px; line-height: 1.6;">
              <div style="font-weight: bold; color: #333; margin-bottom: 4px;">点 #${nearestIndex}</div>
              ${locationHtml ? `<div style="color: #666;">${locationHtml}</div>` : ''}
              <div style="color: #666;">时间: ${timeStr}</div>
              <div style="color: #666;">速度: ${speed}</div>
              <div style="color: #666;">海拔: ${elevation}</div>
            </div>
          `

          if (customTooltip.value && mapContainer) {
            const pointPixel = map.value!.latLngToContainerPoint([nearestPosition[1], nearestPosition[0]])
            const containerSize = { x: mapContainer.value?.clientWidth || map.value?.getContainer()?.clientWidth || 800, y: mapContainer.value?.clientHeight || map.value?.getContainer()?.clientHeight || 600 }
            updateCustomTooltip(content, pointPixel, containerSize)
          }

          lastHoverIndex.value = nearestIndex
          emit('point-hover', point, nearestIndex)
        } else {
          hideMarker()
        }
      }
    })
  }

  // 重新绘制轨迹
  drawTracks()
}

// 切换全屏
function toggleFullscreen() {
  const container = document.querySelector('.leaflet-map-container') as HTMLElement
  if (!document.fullscreenElement) {
    container?.requestFullscreen()
  } else {
    document.exitFullscreen()
  }
}

// 处理全屏变化，更新地图尺寸
function handleFullscreenChange() {
  // 延迟一点等待 DOM 更新完成
  setTimeout(() => {
    if (map.value) {
      map.value.invalidateSize()
    }
  }, 100)
}

// 根据坐标系获取经纬度字段
// 天地图使用 WGS84 坐标（leaflet.chinatmsproviders 会自动转换）
// 高德/腾讯 (GCJ02) → latitude_gcj02/longitude_gcj02
// OSM (WGS84) → latitude_wgs84/longitude_wgs84
// 百度 (BD09) → latitude_bd09/longitude_bd09
function getCoordsByCRS(point: Point, crs: CRSType, mapId?: string): [number, number] | null {
  let lat: number | undefined
  let lng: number | undefined

  if (crs === 'wgs84' || mapId === 'tianditu' || mapId?.startsWith('tianditu')) {
    // 天地图、OSM 都使用 WGS84 坐标（天地图的插件会自动处理转换）
    lat = point.latitude_wgs84 ?? point.latitude
    lng = point.longitude_wgs84 ?? point.longitude
  } else if (crs === 'gcj02') {
    lat = point.latitude_gcj02 ?? undefined
    lng = point.longitude_gcj02 ?? undefined
    // 如果 GCJ02 为空，回退到 WGS84
    if (lat === undefined || lng === undefined) {
      lat = point.latitude_wgs84 ?? point.latitude
      lng = point.longitude_wgs84 ?? point.longitude
    }
  } else if (crs === 'bd09') {
    lat = point.latitude_bd09 ?? undefined
    lng = point.longitude_bd09 ?? undefined
    // 如果 BD09 为空，回退到 WGS84
    if (lat === undefined || lng === undefined) {
      lat = point.latitude_wgs84 ?? point.latitude
      lng = point.longitude_wgs84 ?? point.longitude
    }
  }

  if (lat === undefined || lng === undefined || isNaN(lat) || isNaN(lng)) {
    return null
  }

  return [lat, lng]
}

// 清理 SVG 字符串
function sanitizeSvg(svg: string): string {
  // 只清理空白字符，不修改 SVG 结构
  // SVG 的显示样式由外层 span 的内联样式控制
  return svg.replace(/\s+/g, ' ').trim()
}

// 异步获取道路标志 SVG
async function getRoadSignSvg(code: string, signType: 'way' | 'expwy', province?: string): Promise<string | null> {
  const cacheKey = province ? `${signType}:${code}:${province}` : `${signType}:${code}`
  const cached = roadSignSvgCache.value.get(cacheKey)
  if (cached) {
    // 确保缓存的值是字符串
    return typeof cached === 'string' ? cached : null
  }

  try {
    const response = await roadSignApi.generate({
      sign_type: signType,
      code: code,
      ...(province && { province }),
    })
    const svg = response.svg
    // 确保 svg 是字符串类型并清理
    if (typeof svg === 'string') {
      const cleanSvg = sanitizeSvg(svg)
      roadSignSvgCache.value.set(cacheKey, cleanSvg)
      return cleanSvg
    } else {
      return null
    }
  } catch {
    return null
  }
}

// 格式化地理信息显示
function formatLocationInfo(point: Point): { html: string; needLoad: ParsedRoadNumber[] } {
  const parts: string[] = []
  const needLoad: ParsedRoadNumber[] = []  // 需要异步加载的道路编号

  // 行政区划 - 确保是字符串
  const province = point.province ? String(point.province) : ''
  const city = point.city ? String(point.city) : ''
  const district = point.district ? String(point.district) : ''

  if (province) parts.push(province)
  if (city && city !== province) parts.push(city)
  if (district) parts.push(district)

  // 道路信息
  const roadParts: string[] = []
  if (point.road_number) {
    const roadNumberStr = String(point.road_number)
    const roadNumbers = roadNumberStr.split(',').map(s => s.trim())
    const signContents: string[] = []

    for (const num of roadNumbers) {
      const parsed = parseRoadNumber(num)
      if (parsed) {
        const cacheKey = parsed.province ? `${parsed.sign_type}:${parsed.code}:${parsed.province}` : `${parsed.sign_type}:${parsed.code}`
        const svg = roadSignSvgCache.value.get(cacheKey)

        if (svg && typeof svg === 'string') {
          // 使用 span 包装 SVG，添加内联样式用于 ECharts tooltip
          signContents.push(`<span class="road-sign-inline" style="display: inline-flex; align-items: center; vertical-align: middle; line-height: 1; margin: 0 1px;">${svg}</span>`)
        } else {
          // 显示文本并记录需要加载
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
    roadParts.push(String(point.road_name))
  }

  if (roadParts.length > 0) {
    parts.push(roadParts.join(' '))
  }

  // 确保返回的 html 是字符串
  const html = parts.join(' ')
  return { html: html || '', needLoad }
}

// 异步加载道路编号的 SVG
async function loadRoadSignsForTooltip(parsedList: ParsedRoadNumber[]): Promise<boolean> {
  const config = configStore.config
  const showSigns = config?.show_road_sign_in_region_tree ?? true
  if (!showSigns || parsedList.length === 0) return false

  let loaded = false
  for (const parsed of parsedList) {
    const key = parsed.province ? `${parsed.sign_type}:${parsed.code}:${parsed.province}` : `${parsed.sign_type}:${parsed.code}`
    if (loadingSigns.value.has(key)) continue

    loadingSigns.value.add(key)
    try {
      const svg = await getRoadSignSvg(parsed.code, parsed.sign_type, parsed.province)
      if (svg) {
        // 存入缓存（getRoadSignSvg 内部已经存了，但这里确保一下）
        if (!roadSignSvgCache.value.has(key)) {
          roadSignSvgCache.value.set(key, svg)
        }
        loaded = true
      }
    } finally {
      loadingSigns.value.delete(key)
    }
  }

  return loaded
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

// 从外部高亮指定点（由图表触发）
function highlightPoint(index: number) {
  if (index < 0 || index >= trackPoints.value.length) {
    hideMarker()
    return
  }

  if (index === lastHoverIndex.value) return

  lastHoverIndex.value = index

  const point = trackPoints.value[index]
  const position = trackPath.value[index]

  if (!map.value || !mouseMarker.value || !point || !position) return

  const pointLatLng: L.LatLngExpression = [position[1], position[0]]
  const mapInstance = map.value
  const mapContainer = mapInstance.getContainer()

  if (!mapContainer) return

  // 保存当前高亮的点（用于地图移动时更新 tooltip）
  currentHighlightPoint.value = { index, position }

  // 检查点是否在视野内，如果不在则平移地图到该点
  const bounds = mapInstance.getBounds()
  if (!bounds.contains(pointLatLng)) {
    mapInstance.panTo(pointLatLng, { animate: true, duration: 0.25 })
  }

  // 更新标记位置
  mouseMarker.value.setLatLng([position[1], position[0]])
  mouseMarker.value.addTo(mapInstance)

  // 更新 tooltip
  updateTooltipForPoint(index, point)
}

// 更新 tooltip 位置和内容的辅助函数
function updateTooltipForPoint(index: number, point: Point) {
  if (!currentHighlightPoint.value || !customTooltip.value || !map.value) return

  const mapInstance = map.value
  const mapContainer = mapInstance.getContainer()
  if (!mapContainer) return

  const position = currentHighlightPoint.value.position
  const pointLatLng: L.LatLngExpression = [position[1], position[0]]

  // 保存当前显示的点（用于异步更新）
  currentTooltipPoint.value = point

  // 创建 tooltip 内容
  const timeStr = point.time ? new Date(point.time).toLocaleTimeString('zh-CN') : '-'
  const elevation = point.elevation != null ? `${point.elevation.toFixed(1)} m` : '-'
  const speed = point.speed != null ? `${(point.speed * 3.6).toFixed(1)} km/h` : '-'
  const locationResult = formatLocationInfo(point)
  const locationHtml = locationResult.html || ''

  const content = `
    <div style="padding: 8px 12px; background: rgba(255, 255, 255, 0.95); border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-size: 12px; line-height: 1.6;">
      <div style="font-weight: bold; color: #333; margin-bottom: 4px;">点 #${index}</div>
      ${locationHtml ? `<div style="color: #666;">${locationHtml}</div>` : ''}
      <div style="color: #666;">时间: ${timeStr}</div>
      <div style="color: #666;">速度: ${speed}</div>
      <div style="color: #666;">海拔: ${elevation}</div>
    </div>
  `

  // 获取点的像素位置和容器尺寸
  const pointPixel = mapInstance.latLngToContainerPoint(pointLatLng)
  const containerSize = { x: mapContainer.value?.clientWidth || map.value?.getContainer()?.clientWidth || 800, y: mapContainer.value?.clientHeight || map.value?.getContainer()?.clientHeight || 600 }

  // 更新自定义 tooltip
  updateCustomTooltip(content, pointPixel, containerSize)

  // 异步加载道路标志 SVG
  if (locationResult.needLoad.length > 0) {
    nextTick(async () => {
      const loaded = await loadRoadSignsForTooltip(locationResult.needLoad)
      // 如果加载成功且当前还在显示同一个点，则更新 tooltip
      if (loaded && currentTooltipPoint.value === point) {
        updateTooltipForPoint(index, point)
      }
    })
  }
}

// 隐藏标记
function hideMarker() {
  currentHighlightPoint.value = null
  currentTooltipPoint.value = null
  currentHoverTrack.value = null
  if (mouseMarker.value) {
    map.value?.removeLayer(mouseMarker.value)
  }
  if (customTooltip.value) {
    customTooltip.value.style.display = 'none'
  }
  if (props.mode === 'home') {
    emit('track-hover', null)
  }
}

// 创建鼠标标记
function createMouseMarker() {
  if (!map.value) return

  const icon = L.divIcon({
    className: 'leaflet-mouse-marker',
    iconSize: [12, 12],
    iconAnchor: [6, 6],
  })

  mouseMarker.value = L.marker([0, 0], { icon, interactive: false })
}

// 创建最新点标记（绿色）
function createLatestPointMarker() {
  if (!map.value) return

  const icon = L.divIcon({
    className: 'leaflet-latest-point-marker',
    iconSize: [12, 12],
    iconAnchor: [6, 6],
  })

  latestPointMarker.value = L.marker([0, 0], { icon, interactive: false })
}

// 创建自定义 tooltip
function createCustomTooltip() {
  if (!mapContainer.value) return

  // 创建 tooltip 元素（只负责定位，样式由 content 决定）
  const tooltipDiv = document.createElement('div')
  tooltipDiv.className = 'custom-map-tooltip'
  tooltipDiv.style.cssText = `
    position: absolute;
    z-index: 1000;
    pointer-events: none;
    display: none;
    min-width: 150px;
  `

  mapContainer.value.appendChild(tooltipDiv)
  customTooltip.value = tooltipDiv

  // 监听 tooltip 点击事件（用于点击跳转）
  tooltipDiv.addEventListener('click', (e) => {
    const trackId = (e.target as HTMLElement).closest('.track-tooltip')?.getAttribute('data-track-id')
    if (trackId) {
      emit('track-click', parseInt(trackId))
    }
  })
}

// 缓存 tooltip 尺寸，避免频繁调用 getBoundingClientRect 引起 reflow
let cachedTooltipWidth = 0
let cachedTooltipHeight = 0

// 只更新自定义 tooltip 的位置（不更新内容，用于频繁调用）
// 使用 CSS transform 进行位移，避免频繁计算
function updateCustomTooltipPosition(pointPixel: L.Point, containerSize: { x: number; y: number }) {
  if (!customTooltip.value || customTooltip.value.style.display === 'none') return

  // 取消之前的 RAF
  if (rafId !== null) {
    cancelAnimationFrame(rafId)
  }

  // 保存待处理的更新
  pendingUpdate = { pointPixel, containerSize }

  // 使用 RAF 节流
  rafId = requestAnimationFrame(() => {
    if (!pendingUpdate || !customTooltip.value) return

    const tooltip = customTooltip.value
    const px = pendingUpdate.pointPixel.x
    const py = pendingUpdate.pointPixel.y
    const cw = pendingUpdate.containerSize.x
    const ch = pendingUpdate.containerSize.y

    // 获取实际的 tooltip 尺寸
    const rect = tooltip.getBoundingClientRect()
    const tooltipWidth = rect.width || 150
    const tooltipHeight = rect.height || 100
    const padding = 60

    // 计算水平偏移
    let offsetX = 0

    if (px - tooltipWidth / 2 < padding) {
      offsetX = padding - (px - tooltipWidth / 2)
    } else if (px + tooltipWidth / 2 > cw - padding) {
      offsetX = -(px + tooltipWidth / 2 - (cw - padding))
    }

    // 顶部区域：tooltip 显示在点下方，避免被遮住
    let offsetY = -10
    let translateY = '-100%'
    if (py < 180) {
      translateY = '0'
      offsetY = 15
    }

    console.log('[Leaflet] updateCustomTooltipPosition:', {
      px, py, cw, ch, tooltipWidth, tooltipHeight, offsetX, offsetY, padding,
      tooltipLeft: px - tooltipWidth / 2 + offsetX,
      tooltipRight: px + tooltipWidth / 2 + offsetX,
      containerLeft: padding,
      containerRight: cw - padding
    })

    // 设置位置和 transform
    tooltip.style.left = `${px}px`
    tooltip.style.top = `${py}px`
    tooltip.style.transform = `translate(calc(-50% + ${offsetX}px), ${translateY}) translateY(${offsetY}px)`

    rafId = null
    pendingUpdate = null
  })
}

// 更新自定义 tooltip 位置和内容
function updateCustomTooltip(content: string, pointPixel: L.Point, containerSize: { x: number; y: number }) {
  if (!customTooltip.value) return

  // 取消之前的 RAF
  if (rafId !== null) {
    cancelAnimationFrame(rafId)
    rafId = null
  }
  pendingUpdate = null

  const tooltip = customTooltip.value
  tooltip.innerHTML = content
  tooltip.style.display = 'block'

  // 内容更新后，获取并缓存尺寸
  const rect = tooltip.getBoundingClientRect()
  cachedTooltipWidth = rect.width
  cachedTooltipHeight = rect.height

  const px = pointPixel.x
  const py = pointPixel.y
  const cw = containerSize.x
  const ch = containerSize.y
  const tooltipWidth = rect.width
  const tooltipHeight = rect.height
  const padding = 60

  // 计算水平偏移
  let offsetX = 0

  if (px - tooltipWidth / 2 < padding) {
    offsetX = padding - (px - tooltipWidth / 2)
  } else if (px + tooltipWidth / 2 > cw - padding) {
    offsetX = -(px + tooltipWidth / 2 - (cw - padding))
  }

  // 顶部区域：tooltip 显示在点下方，避免被遮住
  let offsetY = -10
  let translateY = '-100%'
  if (py < 100) {
    translateY = '0'
    offsetY = 15
  }

  console.log('[Leaflet] updateCustomTooltip:', {
    px, py, cw, ch, tooltipWidth, tooltipHeight, offsetX, offsetY, padding,
    tooltipLeft: px - tooltipWidth / 2 + offsetX,
    tooltipRight: px + tooltipWidth / 2 + offsetX,
    containerLeft: padding,
    containerRight: cw - padding
  })

  // 设置位置和 transform
  tooltip.style.left = `${px}px`
  tooltip.style.top = `${py}px`
  tooltip.style.transform = `translate(calc(-50% + ${offsetX}px), ${translateY}) translateY(${offsetY}px)`
}

// 绘制轨迹
function drawTracks() {
  if (!map.value || !props.tracks.length) return

  const crs = currentLayerConfig.value?.crs || 'wgs84'
  const mapId = currentLayerConfig.value?.id

  // 调试：打印地图配置
  console.log('[LeafletMap] drawTracks:', {
    mapId,
    crs,
    layerConfig: currentLayerConfig.value,
    firstPoint: props.tracks[0]?.points[0],
  })

  // 重置日志标志
  ;(getCoordsByCRS as any).logged = false

  // 清除现有轨迹
  clearTracks()

  // 重置轨迹数据
  trackPoints.value = []
  trackPath.value = []
  tracksData.value.clear()

  const bounds = L.latLngBounds([])

  for (const track of props.tracks) {
    if (!track.points || track.points.length === 0) continue

    const latLngs: L.LatLngExpression[] = []
    const trackPathData: [number, number][] = []
    const trackPointsData: Point[] = []

    for (const point of track.points) {
      const coords = getCoordsByCRS(point, crs, mapId)
      if (!coords) continue

      const [lat, lng] = coords
      // 跳过无效坐标
      if (isNaN(lat) || isNaN(lng)) {
        continue
      }

      latLngs.push([lat, lng])
      bounds.extend([lat, lng])

      // detail 模式：合并所有轨迹
      trackPoints.value.push(point)
      trackPath.value.push([lng, lat])

      // home 模式：按轨迹分开存储
      trackPointsData.push(point)
      trackPathData.push([lng, lat])
    }

    // 如果没有有效点，跳过
    if (latLngs.length === 0) continue

    // 保存轨迹数据用于 home 模式
    tracksData.value.set(track.id, {
      points: trackPointsData,
      path: trackPathData,
      track,
    })

    // 绘制轨迹线
    const isHighlighted = track.id === props.highlightTrackId
    const polyline = L.polyline(latLngs, {
      color: '#ff0000',
      weight: isHighlighted ? 5 : 3,
      opacity: 0.8,
    })

    polyline.on('click', () => {
      // 轨迹点击事件：桌面端点击轨迹直接跳转
      const isMobile = window.innerWidth <= 1366
      if (!isMobile) {
        emit('track-click', track.id)
      }
    })

    polyline.addTo(map.value as L.Map)
    polylineLayers.value.set(track.id, polyline)
  }

  // 绘制路径段高亮（detail 模式）
  if (props.mode === 'detail' && props.highlightSegment && trackPoints.value.length > 0) {
    const { start, end } = props.highlightSegment
    // 确保索引在有效范围内
    if (start >= 0 && end < trackPath.value.length && start <= end) {
      const segmentPath = trackPath.value.slice(start, end + 1)
      if (segmentPath.length > 0) {
        const segmentLatLngs: L.LatLngExpression[] = segmentPath.map(([lng, lat]) => [lat, lng])
        highlightPolyline.value = L.polyline(segmentLatLngs, {
          color: '#409eff',  // 蓝色高亮
          weight: 7,
          opacity: 0.9,
        })
        highlightPolyline.value.addTo(map.value as L.Map)
      }
    }
  }

  // 自动适应视图
  if (bounds.isValid()) {
    map.value.fitBounds(bounds, { padding: [0, 0] })
  }

  // 更新最新点标记
  updateLatestPointMarker()
}

// 清除轨迹
function clearTracks() {
  polylineLayers.value.forEach((polyline) => {
    map.value!.removeLayer(polyline)
  })
  polylineLayers.value.clear()

  // 清除路径段高亮
  if (highlightPolyline.value) {
    map.value!.removeLayer(highlightPolyline.value)
    highlightPolyline.value = null
  }

  markers.value.forEach((marker) => {
    map.value!.removeLayer(marker)
  })
  markers.value = []
}

// 更新轨迹（当底图切换或数据变化时）
function updateTracks() {
  drawTracks()
}

// 监听变化
watch(() => props.tracks, () => {
  updateTracks()
})

watch(() => props.highlightTrackId, () => {
  updateTracks()
})

watch(() => props.highlightSegment, () => {
  updateTracks()
})

// 更新实时轨迹最新点标记
function updateLatestPointMarker() {
  if (!latestPointMarker.value) return

  if (props.latestPointIndex === null || props.latestPointIndex === undefined) {
    try {
      if (map.value?.hasLayer(latestPointMarker.value)) {
        map.value.removeLayer(latestPointMarker.value)
      }
    } catch (e) {
      // ignore
    }
    return
  }

  // 如果还没绘制轨迹（trackPoints 为空），等待绘制完成
  if (!trackPoints.value.length) {
    nextTick(() => updateLatestPointMarker())
    return
  }

  const index = props.latestPointIndex
  if (index < 0 || index >= trackPoints.value.length) {
    try {
      if (map.value?.hasLayer(latestPointMarker.value)) {
        map.value.removeLayer(latestPointMarker.value)
      }
    } catch (e) {
      // ignore
    }
    return
  }

  const point = trackPoints.value[index]
  const position = trackPath.value[index]
  if (!point || !position || !map.value) {
    try {
      if (map.value?.hasLayer(latestPointMarker.value)) {
        map.value.removeLayer(latestPointMarker.value)
      }
    } catch (e) {
      // ignore
    }
    return
  }

  // trackPath 格式是 [lng, lat]，需要交换为 [lat, lng]
  latestPointMarker.value.setLatLng([position[1], position[0]])
  // 先移除再添加，避免重复
  if (map.value.hasLayer(latestPointMarker.value)) {
    map.value.removeLayer(latestPointMarker.value)
  }
  latestPointMarker.value.addTo(map.value)
}

// 监听最新点索引变化
watch(() => props.latestPointIndex, () => {
  updateLatestPointMarker()
})

// 监听 defaultLayerId 变化（从 UniversalMap 传入）
watch(() => props.defaultLayerId, (newId) => {
  if (newId && newId !== currentLayerId.value) {
    switchLayer(newId)
  }
})

// 调整地图大小（用于响应式布局）
function resize() {
  if (map.value) {
    map.value.invalidateSize()
  }
}

// 将所有轨迹居中显示（四周留 5% 空间）
function fitBounds() {
  if (!map.value) return

  // 计算所有轨迹的边界
  const bounds = L.latLngBounds([])
  const crs = currentLayerConfig.value?.crs || 'wgs84'
  const mapId = currentLayerConfig.value?.id

  for (const track of props.tracks) {
    if (!track.points || track.points.length === 0) continue
    for (const point of track.points) {
      const coords = getCoordsByCRS(point, crs, mapId)
      if (!coords) continue
      const [lat, lng] = coords
      // 更严格的检查：确保是有效数字
      if (typeof lat === 'number' && typeof lng === 'number' && !isNaN(lat) && !isNaN(lng)) {
        bounds.extend([lat, lng])
      }
    }
  }

  if (!bounds.isValid()) return

  // 获取地图容器尺寸，计算 5% 的 padding
  const mapContainer = map.value.getContainer()
  const width = mapContainer.value?.clientWidth || map.value?.getContainer()?.clientWidth || 800
  const height = mapContainer.value?.clientHeight || map.value?.getContainer()?.clientHeight || 600
  const padding = Math.round(Math.max(width, height) * 0.05)

  // 使用 L.point() 创建 padding 对象
  map.value.fitBounds(bounds, { padding: L.point(padding, padding) })
}

// 暴露方法给父组件
defineExpose({
  highlightPoint,
  hideMarker,
  resize,
  fitBounds,
})

// 生命周期
onMounted(async () => {
  // 等待配置加载完成（如果还没有加载）
  await configStore.fetchConfig()

  // 初始化地图层列表
  initMapLayers()

  // 更新当前层（从 prop 或配置获取）
  const defaultId = props.defaultLayerId || configStore.getMapProvider()
  const exists = mapLayers.value.find((l: MapLayerConfig) => l.id === defaultId)
  currentLayerId.value = exists ? defaultId : (mapLayers.value[0]?.id || 'osm')
  updateCurrentLayerConfig()

  initMap()
  drawTracks()

  // 监听全屏变化，更新地图尺寸
  document.addEventListener('fullscreenchange', handleFullscreenChange)
})

onUnmounted(() => {
  if (map.value) {
    map.value.remove()
  }
  // 清理全屏事件监听器
  document.removeEventListener('fullscreenchange', handleFullscreenChange)
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
</script>

<style scoped>
.leaflet-map-container {
  width: 100%;
  height: 100%;
  position: relative;
}

.map {
  width: 100%;
  height: 100%;
}

.map-controls {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 1000;
  display: flex;
  gap: 8px;
  align-items: center;
}

/* 桌面端：显示按钮组 */
.desktop-layer-selector {
  display: flex;
}

/* 移动端：显示下拉选择器，隐藏按钮组 */
.mobile-layer-selector {
  display: none;
  width: 100px;
}

/* 移动端响应式 */
@media (max-width: 1366px) {
  .desktop-layer-selector {
    display: none;
  }

  .mobile-layer-selector {
    display: block;
  }

  .fullscreen-btn {
    flex-shrink: 0;
  }
}

:deep(.leaflet-container) {
  background: #e5e5e5;
  outline: none;
}

:deep(.leaflet-container:focus) {
  outline: none;
}

:deep(.leaflet-control-attribution) {
  font-size: 10px;
}

/* 鼠标标记样式（蓝色） */
:deep(.leaflet-mouse-marker) {
  width: 12px !important;
  height: 12px !important;
  background: #409eff !important;
  border: 2px solid #fff !important;
  border-radius: 50% !important;
  box-shadow: 0 0 4px rgba(0, 0, 0, 0.3) !important;
}

/* 最新点标记样式（绿色） */
:deep(.leaflet-latest-point-marker) {
  width: 12px !important;
  height: 12px !important;
  background: #67c23a !important;
  border: 2px solid #fff !important;
  border-radius: 50% !important;
  box-shadow: 0 0 4px rgba(0, 0, 0, 0.3) !important;
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

<!-- 全局样式：用于动态插入的 tooltip 内容 -->
<style>
.road-sign-inline {
  display: inline-flex;
  align-items: center;
  vertical-align: middle;
  line-height: 1;
  margin: 0 1px;
}

.road-sign-inline svg {
  display: block;
  height: 1.4em;
  width: auto;
}
</style>
