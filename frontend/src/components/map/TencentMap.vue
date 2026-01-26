<template>
  <div class="tencent-map-container">
    <div ref="mapContainer" class="tencent-map"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useConfigStore } from '@/stores/config'

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
function formatLocationInfo(point: Point): string {
  const parts: string[] = []

  // 行政区划
  if (point.province) parts.push(point.province)
  if (point.city && point.city !== point.province) parts.push(point.city)
  if (point.district) parts.push(point.district)

  // 道路信息
  const roadParts: string[] = []
  if (point.road_number) {
    // 数据库中道路编号是逗号分隔，显示时改为斜杠分隔
    roadParts.push(point.road_number.replace(/,/g, ' / '))
  }
  if (point.road_name) {
    roadParts.push(point.road_name)
  }

  if (roadParts.length > 0) {
    parts.push(roadParts.join(' '))
  }

  return parts.join(' ')
}

// 定义 emit 事件
const emit = defineEmits<{
  (e: 'point-hover', point: Point | null, pointIndex: number): void
  (e: 'track-hover', trackId: number | null): void
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

// 腾讯地图实例
const mapContainer = ref<HTMLElement>()
let TMapInstance: any = null
let polylineLayer: any = null
let highlightPolylineLayer: any = null  // 路径段高亮图层
let mouseMarker: any = null  // 腾讯地图 Marker 实例
let infoWindow: any = null  // 信息提示框

// 存储轨迹点数据用于查询
let trackPoints: Point[] = []
let trackPath: any[] = []  // 腾讯地图坐标路径
// home 模式：按轨迹分开存储
const tracksData = new Map<number, { points: Point[]; path: any[]; track: Track }>()

// 节流和缓存
let lastHoverIndex = -1  // 上次悬停的点索引
let isClickProcessing = false  // 防止移动端 touchend 和 click 重复触发

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

// 查找鼠标位置对应的轨迹点
function findNearestPoint(mouseLngLat: [number, number]): { point: Point; index: number; position: any } | null {
  if (trackPath.length < 2 || !TMapInstance) return null

  const TMap = (window as any).TMap

  // 根据地图缩放级别动态计算触发距离
  const zoom = TMapInstance.getZoom()
  const dynamicDistance = Math.pow(2, 12 - zoom) * 0.008

  let minDistance = Infinity
  let nearestPoint: Point | null = null
  let nearestIndex = -1
  let nearestPosition: any = null

  // 遍历所有线段，找到距离鼠标最近的点
  for (let i = 0; i < trackPath.length - 1; i++) {
    const p1 = [trackPath[i].lng, trackPath[i].lat] as [number, number]
    const p2 = [trackPath[i + 1].lng, trackPath[i + 1].lat] as [number, number]

    const closest = closestPointOnSegment(mouseLngLat, p1, p2)
    const dist = distance(mouseLngLat, closest)

    if (dist < minDistance) {
      minDistance = dist
      nearestPosition = new TMap.LatLng(closest[1], closest[0])

      // 找到对应的轨迹点索引
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

// 创建鼠标位置标记（使用腾讯地图 Marker）
function createMouseMarker() {
  if (!TMapInstance) return

  const TMap = (window as any).TMap

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

  // 创建标记样式
  mouseMarker = new TMap.MultiMarker({
    map: null,  // 初始不添加到地图
    styles: {
      'blue-dot': new TMap.MarkerStyle({
        width: 16,
        height: 16,
        anchor: { x: 8, y: 8 },
        src: dataUrl,
      }),
    },
    geometries: [],
  })
}

// 更新标记位置
function updateMarkerPosition(position: any) {
  if (!TMapInstance || !mouseMarker) return

  // 更新标记位置
  mouseMarker.setGeometries([{
    id: 'hover-marker',
    styleId: 'blue-dot',
    position: position,
  }])
  mouseMarker.setMap(TMapInstance)
}

// 创建信息提示框
function createTooltip() {
  // 腾讯地图的 InfoWindow 需要时创建
}

// 更新标记和提示框
function updateMarker(nearest: { point: Point; index: number; position: any }) {
  // 如果是同一个点，跳过更新
  if (nearest.index === lastHoverIndex) return

  lastHoverIndex = nearest.index

  if (!TMapInstance) return

  const TMap = (window as any).TMap

  // 更新标记位置并显示
  updateMarkerPosition(nearest.position)

  // 更新提示框内容
  const { point, index } = nearest
  const timeStr = point.time ? new Date(point.time).toLocaleTimeString('zh-CN') : '-'
  const elevation = point.elevation != null ? `${point.elevation.toFixed(1)} m` : '-'
  const speed = point.speed != null ? `${(point.speed * 3.6).toFixed(1)} km/h` : '-'
  const location = formatLocationInfo(point)

  const content = `
    <div style="padding: 8px 12px; margin: 0; background: #fff; border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-size: 12px; line-height: 1.6;">
      <div style="font-weight: bold; color: #333; margin-bottom: 4px;">点 #${index}</div>
      ${location ? `<div style="color: #666;">${location}</div>` : ''}
      <div style="color: #666;">时间: ${timeStr}</div>
      <div style="color: #666;">速度: ${speed}</div>
      <div style="color: #666;">海拔: ${elevation}</div>
    </div>
  `

  // 关闭旧的 InfoWindow
  if (infoWindow) {
    infoWindow.close()
    infoWindow = null
  }

  // 创建新的 InfoWindow
  infoWindow = new TMap.InfoWindow({
    map: TMapInstance,
    position: nearest.position,
    content: content,
    offset: { x: 0, y: -40 },
    enableCustom: true,
  })
  infoWindow.open()

  // 发射事件
  emit('point-hover', point, index)
}

// 隐藏标记和提示框
function hideMarker() {
  if (lastHoverIndex === -1) return  // 已经隐藏了

  lastHoverIndex = -1

  if (mouseMarker) {
    mouseMarker.setMap(null)
  }

  if (infoWindow) {
    infoWindow.close()
    infoWindow = null
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

  if (!TMapInstance || !point || !position) return

  const TMap = (window as any).TMap

  // 移动地图到指定点（如果点在视野外）
  const bounds = TMapInstance.getBounds()
  if (bounds && !bounds.contains(position)) {
    TMapInstance.panTo(position)
  }

  // 更新标记位置
  updateMarkerPosition(position)

  const timeStr = point.time ? new Date(point.time).toLocaleTimeString('zh-CN') : '-'
  const elevation = point.elevation != null ? `${point.elevation.toFixed(1)} m` : '-'
  const speed = point.speed != null ? `${(point.speed * 3.6).toFixed(1)} km/h` : '-'
  const location = formatLocationInfo(point)

  const content = `
    <div style="padding: 8px 12px; margin: 0; background: #fff; border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-size: 12px; line-height: 1.6;">
      <div style="font-weight: bold; color: #333; margin-bottom: 4px;">点 #${index}</div>
      ${location ? `<div style="color: #666;">${location}</div>` : ''}
      <div style="color: #666;">时间: ${timeStr}</div>
      <div style="color: #666;">速度: ${speed}</div>
      <div style="color: #666;">海拔: ${elevation}</div>
    </div>
  `

  if (infoWindow) {
    infoWindow.close()
    infoWindow = null
  }

  infoWindow = new TMap.InfoWindow({
    map: TMapInstance,
    position: position,
    content: content,
    offset: { x: 0, y: -40 },
    enableCustom: true,
  })
  infoWindow.open()
}

// 初始化
async function init() {
  // 等待配置加载
  if (!configStore.config) {
    await configStore.fetchConfig()
  }

  await initMap()
}

// 加载腾讯地图 JS API GL
async function loadTMapScript(): Promise<void> {
  return new Promise((resolve, reject) => {
    if ((window as any).TMap) {
      resolve()
      return
    }

    const layerConfig = configStore.getMapLayerById('tencent')
    const apiKey = layerConfig?.api_key || ''

    if (!apiKey) {
      reject(new Error('Tencent Map API Key is required'))
      return
    }

    // 设置全局回调函数
    const callbackName = 'tmapInitCallback'
    ;(window as any)[callbackName] = () => {
      resolve()
      delete (window as any)[callbackName]
    }

    const script = document.createElement('script')
    script.type = 'text/javascript'
    script.src = `https://map.qq.com/api/gljs?v=1.exp&key=${apiKey}&callback=${callbackName}`
    script.onerror = () => {
      reject(new Error('Failed to load Tencent Map API'))
      delete (window as any)[callbackName]
    }
    document.head.appendChild(script)
  })
}

// 初始化地图
async function initMap() {
  if (!mapContainer.value) return

  try {
    await loadTMapScript()

    const TMap = (window as any).TMap

    // 创建地图实例
    TMapInstance = new TMap.Map(mapContainer.value, {
      center: new TMap.LatLng(39.984104, 116.307428),
      zoom: 12,
      viewMode: '2D',
      // 控件配置
      control: {
        scale: {
          position: 'bottomLeft',
        },
        zoom: {
          position: 'topLeft',
        },
        rotation: false,  // 隐藏指南针
      },
    })

    // 创建标记和提示框
    createMouseMarker()
    createTooltip()

    // 统一的鼠标处理函数
    const handleMouseMove = (lat: number, lng: number) => {
      if (props.mode === 'home') {
        handleHomeModeMouseMove(lat, lng)
      } else {
        handleDetailModeMouseMove(lat, lng)
      }
    }

    // detail 模式：显示最近的点信息
    const handleDetailModeMouseMove = (lat: number, lng: number) => {
      if (trackPath.length < 2) return

      const TMap = (window as any).TMap
      const zoom = TMapInstance.getZoom()
      const dynamicDistance = Math.pow(2, 12 - zoom) * 0.008

      let minDistance = Infinity
      let nearestIndex = -1
      let nearestPosition: any = null

      // 快速查找最近的点
      for (let i = 0; i < trackPath.length - 1; i++) {
        const p1 = [trackPath[i].lng, trackPath[i].lat] as [number, number]
        const p2 = [trackPath[i + 1].lng, trackPath[i + 1].lat] as [number, number]
        const closest = closestPointOnSegment([lng, lat], p1, p2)
        const dist = distance([lng, lat], closest)

        if (dist < minDistance) {
          minDistance = dist
          nearestPosition = new TMap.LatLng(closest[1], closest[0])
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
          updateMarker({ point, index: nearestIndex, position: nearestPosition })
        }
      } else {
        hideMarker()
      }
    }

    // home 模式：显示最近的轨迹信息
    const handleHomeModeMouseMove = (lat: number, lng: number) => {
      const TMap = (window as any).TMap
      const zoom = TMapInstance.getZoom()
      const dynamicDistance = Math.pow(2, 12 - zoom) * 0.008

      let minDistance = Infinity
      let nearestTrackId: number | null = null
      let nearestPosition: any = null

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
            nearestPosition = new TMap.LatLng(closest[1], closest[0])
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

        // 更新标记位置并显示
        if (mouseMarker) {
          mouseMarker.setGeometries([
            {
              id: 'hover-marker',
              styleId: 'blue-dot',
              position: nearestPosition,
            },
          ])
          mouseMarker.setMap(TMapInstance)
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
          <div style="padding: 8px 12px; background: rgba(255, 255, 255, 0.95); border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-size: 12px; line-height: 1.6;">
            <div style="font-weight: bold; color: #333; margin-bottom: 4px;">${track.name || '未命名轨迹'}</div>
            <div style="color: #666;">时间: ${formatTimeRange()}</div>
            <div style="color: #666;">里程: ${formatDistance(track.distance)}</div>
            <div style="color: #666;">历时: ${formatDuration(track.duration)}</div>
          </div>
        `

        if (infoWindow) {
          infoWindow.close()
        }

        infoWindow = new TMap.InfoWindow({
          map: TMapInstance,
          position: nearestPosition,
          content: content,
          offset: { x: 0, y: -40 },
          enableCustom: true,
        })

        infoWindow.open()

        // 发射事件
        emit('track-hover', nearestTrackId)
      } else {
        hideMarker()
      }
    }

    // 桌面端：鼠标移动监听
    TMapInstance.on('mousemove', (evt: any) => {
      const lat = evt.latLng?.lat
      const lng = evt.latLng?.lng
      if (lat !== undefined && lng !== undefined) {
        handleMouseMove(lat, lng)
      }
    })

    // 鼠标离开地图时隐藏标记（仅桌面端）
    // 移动端不需要此监听器，因为 touchend 后会触发 mouseout 导致提示框被关闭
    const isMobile = window.innerWidth <= 1366
    if (!isMobile) {
      TMapInstance.on('mouseout', () => {
        hideMarker()
      })
    }

    // 点击地图显示轨迹信息（同时支持桌面端和移动端）
    // 使用 DOM 容器监听，确保事件能被捕获
    if (mapContainer.value) {
      const clickHandler = (e: Event) => {
        if (!TMapInstance) return

        const TMap = (window as any).TMap

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

        // 获取容器的位置信息
        const rect = mapContainer.value!.getBoundingClientRect()
        const x = clientX - rect.left
        const y = clientY - rect.top

        // 使用地图边界手动计算经纬度（腾讯地图 API 的坐标转换方法不可用）
        const bounds = TMapInstance.getBounds()
        if (!bounds) return

        const ne = bounds.getNorthEast()
        const sw = bounds.getSouthWest()

        const lngRange = ne.lng - sw.lng
        const latRange = ne.lat - sw.lat

        // 计算点击位置在容器中的比例
        const xRatio = x / rect.width
        const yRatio = y / rect.height

        // 根据比例计算经纬度
        const lng = sw.lng + lngRange * xRatio
        const lat = ne.lat - latRange * yRatio

        const zoom = TMapInstance.getZoom()
        const dynamicDistance = Math.pow(2, 12 - zoom) * 0.008

        if (props.mode === 'home') {
          // home 模式：显示轨迹信息
          if (tracksData.size === 0) {
            hideMarker()
            return
          }

          let minDistance = Infinity
          let nearestTrackId: number | null = null
          let nearestPosition: any = null

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
                nearestPosition = new TMap.LatLng(closest[1], closest[0])
                nearestTrackId = trackId
              }
            }
          }

          const triggered = minDistance < dynamicDistance

          if (triggered && nearestTrackId !== null) {
            const trackData = tracksData.get(nearestTrackId)
            if (!trackData) return

            const track = trackData.track
            lastHoverIndex = nearestTrackId

            // 更新标记位置并显示
            if (mouseMarker) {
              mouseMarker.setGeometries([
                {
                  id: 'hover-marker',
                  styleId: 'blue-dot',
                  position: nearestPosition,
                },
              ])
              mouseMarker.setMap(TMapInstance)
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
              <div style="padding: 8px 12px; background: rgba(255, 255, 255, 0.95); border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-size: 12px; line-height: 1.6;">
                <div style="font-weight: bold; color: #333; margin-bottom: 4px;">${track.name || '未命名轨迹'}</div>
                <div style="color: #666;">时间: ${formatTimeRange()}</div>
                <div style="color: #666;">里程: ${formatDistance(track.distance)}</div>
                <div style="color: #666;">历时: ${formatDuration(track.duration)}</div>
              </div>
            `

            if (infoWindow) {
              infoWindow.close()
            }

            infoWindow = new TMap.InfoWindow({
              map: TMapInstance,
              position: nearestPosition,
              content: content,
              offset: { x: 0, y: -40 },
              enableCustom: true,
            })

            infoWindow.open()

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
          let nearestPosition: any = null

          // 查找最近的点
          for (let i = 0; i < trackPath.length - 1; i++) {
            const p1 = [trackPath[i].lng, trackPath[i].lat] as [number, number]
            const p2 = [trackPath[i + 1].lng, trackPath[i + 1].lat] as [number, number]
            const closest = closestPointOnSegment([lng, lat], p1, p2)
            const dist = distance([lng, lat], closest)

            if (dist < minDistance) {
              minDistance = dist
              nearestPosition = new TMap.LatLng(closest[1], closest[0])
              const distToP1 = distance(closest, p1)
              const distToP2 = distance(closest, p2)
              nearestIndex = distToP1 < distToP2 ? i : i + 1
            }
          }

          const triggered = minDistance < dynamicDistance

          if (triggered && nearestIndex >= 0 && nearestIndex < trackPoints.length) {
            const point = trackPoints[nearestIndex]
            updateMarker({ point, index: nearestIndex, position: nearestPosition })
          } else {
            hideMarker()
          }
        }
      }

      // 监听点击事件（桌面端）
      mapContainer.value.addEventListener('click', (e: Event) => {
        // 移动端：如果刚处理完 touchend，跳过 click 事件
        if (isClickProcessing) return
        clickHandler(e)
      }, true)

      // 同时监听触摸事件（移动端）
      mapContainer.value.addEventListener('touchend', (e: Event) => {
        // 防止 touchend 后立即触发 click 导致重复处理
        e.preventDefault()
        isClickProcessing = true
        clickHandler(e)
        // 300ms 后清除标志（防止影响后续点击）
        setTimeout(() => {
          isClickProcessing = false
        }, 300)
      }, true)
    }

    // 绘制轨迹
    drawTracks()
  } catch (error) {
    // 静默处理初始化错误
  }
}

// 根据坐标系获取经纬度（GCJ02）
function getGCJ02Coords(point: Point): { lat: number; lng: number } | null {
  const lat = point.latitude_gcj02 ?? point.latitude_wgs84 ?? point.latitude
  const lng = point.longitude_gcj02 ?? point.longitude_wgs84 ?? point.longitude
  if (lat !== undefined && lng !== undefined && !isNaN(lat) && !isNaN(lng)) {
    return { lat, lng }
  }
  return null
}

// 绘制轨迹
function drawTracks() {
  if (!TMapInstance || !props.tracks || props.tracks.length === 0) return

  const TMap = (window as any).TMap

  // 清除现有轨迹图层
  if (polylineLayer) {
    polylineLayer.setMap(null)
    polylineLayer = null
  }

  // 清除路径段高亮图层
  if (highlightPolylineLayer) {
    highlightPolylineLayer.setMap(null)
    highlightPolylineLayer = null
  }

  // 重置轨迹点数据
  trackPoints = []
  trackPath = []
  tracksData.clear()

  // 准备轨迹数据
  const geometries: any[] = []
  const bounds: any[] = []

  for (const track of props.tracks) {
    if (!track.points || track.points.length === 0) continue

    const paths: any[] = []
    const trackPathData: any[] = []
    const trackPointsData: Point[] = []

    for (const point of track.points) {
      const coords = getGCJ02Coords(point)
      if (!coords) continue

      const { lat, lng } = coords
      const latLng = new TMap.LatLng(lat, lng)
      paths.push(latLng)
      bounds.push(latLng)

      // detail 模式：合并所有轨迹
      trackPoints.push(point)
      trackPath.push(latLng)

      // home 模式：按轨迹分开存储
      trackPointsData.push(point)
      trackPathData.push(latLng)
    }

    if (paths.length === 0) continue

    // 保存轨迹数据用于 home 模式
    tracksData.set(track.id, {
      points: trackPointsData,
      path: trackPathData,
      track,
    })

    const isHighlighted = track.id === props.highlightTrackId

    geometries.push({
      id: `track_${track.id}`,
      styleId: isHighlighted ? 'style_highlight' : 'style_normal',
      paths: paths,
    })
  }

  if (geometries.length === 0) return

  // 创建折线图层
  polylineLayer = new TMap.MultiPolyline({
    id: 'polyline-layer',
    map: TMapInstance,
    styles: {
      style_normal: new TMap.PolylineStyle({
        color: '#FF0000',
        width: 4,
        borderWidth: 0,
      }),
      style_highlight: new TMap.PolylineStyle({
        color: '#FF0000',
        width: 6,
        borderWidth: 0,
      }),
    },
    geometries: geometries,
  })

  // 绘制路径段高亮（detail 模式）
  if (props.mode === 'detail' && props.highlightSegment && trackPath.length > 0) {
    const { start, end } = props.highlightSegment
    // 确保索引在有效范围内
    if (start >= 0 && end < trackPath.length && start <= end) {
      const segmentPath = trackPath.slice(start, end + 1)
      if (segmentPath.length > 0) {
        highlightPolylineLayer = new TMap.MultiPolyline({
          id: 'highlight-segment-layer',
          map: TMapInstance,
          styles: {
            style_highlight: new TMap.PolylineStyle({
              color: '#409eff',  // 蓝色高亮
              width: 8,
              borderWidth: 0,
            }),
          },
          geometries: [{
            id: 'highlight-segment',
            styleId: 'style_highlight',
            paths: segmentPath,
          }],
        })
      }
    }
  }

  // 自动适应视图
  if (bounds.length > 0) {
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

      const sw = new TMap.LatLng(minLat, minLng)
      const ne = new TMap.LatLng(maxLat, maxLng)
      const boundsObj = new TMap.LatLngBounds(sw, ne)
      // 轨迹四周留出 100px 边距
      TMapInstance.fitBounds(boundsObj, { padding: 100 })
    } catch (e) {
      // ignore
    }
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
  // 清理标记和提示框
  if (mouseMarker) {
    mouseMarker.setMap(null)
    mouseMarker = null
  }
  if (infoWindow) {
    infoWindow.close()
    infoWindow = null
  }
  if (polylineLayer) {
    polylineLayer.setMap(null)
    polylineLayer = null
  }
  if (TMapInstance) {
    TMapInstance.destroy()
    TMapInstance = null
  }
})

// 调整地图大小（用于响应式布局）
function resize() {
  if (TMapInstance) {
    // 腾讯地图会自动调整大小
  }
}

// 将所有轨迹居中显示（四周留 5% 空间）
function fitBounds() {
  if (!TMapInstance) return

  // 计算所有轨迹的边界
  const TMap = (window as any).TMap
  const bounds: { lat: number; lng: number }[] = []

  for (const track of props.tracks) {
    if (!track.points || track.points.length === 0) continue
    for (const point of track.points) {
      const coords = getGCJ02Coords(point)
      if (!coords) continue
      // getGCJ02Coords 返回 { lat, lng } 对象，不是数组
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

    const sw = new TMap.LatLng(minLat, minLng)
    const ne = new TMap.LatLng(maxLat, maxLng)
    const boundsObj = new TMap.LatLngBounds(sw, ne)

    // 获取容器尺寸
    const container = mapContainer.value
    if (!container) return
    const width = container.clientWidth || 800
    const height = container.clientHeight || 600
    const padding = Math.round(Math.max(width, height) * 0.05)

    TMapInstance.fitBounds(boundsObj, { padding })
  } catch (e) {
    console.error('[TencentMap] fitBounds failed:', e)
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
.tencent-map-container {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
}

.tencent-map {
  width: 100%;
  height: 100%;
}

/* 隐藏指南针控件 */
:deep(.rotate-circle) {
  display: none !important;
}

/* 隐藏旋转面板 */
:deep(.rotate-panel) {
  display: none !important;
}

/* 缩放控件移到左上角 - 覆盖外层 div 的 inset 样式 */
:deep(div[style*="inset: 0px 0px auto auto"]) {
  inset: 0px auto auto 0px !important;
}

/* 腾讯地图比例尺样式改为黑色 */
:deep(.tmap-control-scale) {
  color: #000 !important;
}

:deep(.tmap-control-scale span) {
  color: #000 !important;
  border-color: #000 !important;
}

:deep(.tmap-scale-control .tmap-scale-line) {
  color: #000 !important;
  border-color: #000 !important;
}

:deep(.tmap-zoom-control) {
  margin: 10px 0px 0px 10px;
}

/* 移除腾讯地图 InfoWindow 的白边 */
:deep(.tmap-infowindow-content) {
  padding: 0 !important;
  margin: 0 !important;
}

:deep(.tmap-infowindow) {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15) !important;
}
</style>
