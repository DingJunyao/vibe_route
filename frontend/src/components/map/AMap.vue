<template>
  <div class="amap-container">
    <div ref="mapContainer" class="amap"></div>
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

// 格式化地理信息显示，返回空字符串表示无位置信息
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
}>()

interface Track {
  id: number
  points: Point[]
}

interface Props {
  tracks?: Track[]
  highlightTrackId?: number
  defaultLayerId?: string
}

const props = withDefaults(defineProps<Props>(), {
  tracks: () => [],
  highlightTrackId: undefined,
  defaultLayerId: undefined,
})

const configStore = useConfigStore()

// 高德地图实例
const mapContainer = ref<HTMLElement>()
let AMapInstance: any = null
let polylines: any[] = []
let mouseMarker: any = null  // 鼠标位置标记
let tooltip: any = null  // 信息提示框

// 存储轨迹点数据用于查询
let trackPoints: Point[] = []
let trackPath: any[] = []  // 高德地图坐标路径

// 节流和缓存
let lastHoverIndex = -1  // 上次悬停的点索引
let throttleTimer: number | null = null  // 节流定时器
const THROTTLE_DELAY = 30  // 节流延迟（毫秒）

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
    "></div>
  `

  mouseMarker = new AMap.Marker({
    position: new AMap.LngLat(0, 0),
    content: markerContent,
    offset: new AMap.Pixel(-6, -6),
    zIndex: 100,
    map: null,  // 初始不添加到地图
  })
}

// 创建信息提示框
function createTooltip() {
  if (!AMapInstance) return

  const AMap = (window as any).AMap

  tooltip = new AMap.InfoWindow({
    isCustom: true,
    content: '',
    offset: new AMap.Pixel(0, -40),
    closeWhenClickMap: false,
    showShadow: false,
  })
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
    <div style="padding: 8px 12px; background: rgba(255, 255, 255, 0.95); border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-size: 12px; line-height: 1.6;">
      <div style="font-weight: bold; color: #333; margin-bottom: 4px;">点 #${index}</div>
      <div style="color: #666;">时间: ${timeStr}</div>
      <div style="color: #666;">速度: ${speed}</div>
      <div style="color: #666;">海拔: ${elevation}</div>
    </div>
  `

  if (tooltip) {
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
  if (mouseMarker) mouseMarker.setMap(null)
  if (tooltip) tooltip.close()
  emit('point-hover', null, -1)
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

  mouseMarker.setPosition(new AMap.LngLat(position.lng, position.lat))
  mouseMarker.setMap(AMapInstance)

  const timeStr = point.time ? new Date(point.time).toLocaleTimeString('zh-CN') : '-'
  const elevation = point.elevation != null ? `${point.elevation.toFixed(1)} m` : '-'
  const speed = point.speed != null ? `${(point.speed * 3.6).toFixed(1)} km/h` : '-'
  const location = formatLocationInfo(point)

  const content = `
    <div style="padding: 8px 12px; background: rgba(255, 255, 255, 0.95); border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-size: 12px; line-height: 1.6;">
      <div style="font-weight: bold; color: #333; margin-bottom: 4px;">点 #${index}</div>
      ${location ? `<div style="color: #666;">${location}</div>` : ''}
      <div style="color: #666;">时间: ${timeStr}</div>
      <div style="color: #666;">速度: ${speed}</div>
      <div style="color: #666;">海拔: ${elevation}</div>
    </div>
  `

  tooltip.setContent(content)
  tooltip.setPosition(new AMap.LngLat(position.lng, position.lat))
  tooltip.open(AMapInstance)
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
        // 如果是同一个点，跳过更新
        if (nearestIndex !== lastHoverIndex) {
          lastHoverIndex = nearestIndex

          const AMap = (window as any).AMap

          // 更新标记位置并显示
          mouseMarker.setPosition(new AMap.LngLat(nearestPosition[0], nearestPosition[1]))
          mouseMarker.setMap(AMapInstance)

          // 更新提示框内容
          const timeStr = point.time ? new Date(point.time).toLocaleTimeString('zh-CN') : '-'
          const elevation = point.elevation != null ? `${point.elevation.toFixed(1)} m` : '-'
          const speed = point.speed != null ? `${(point.speed * 3.6).toFixed(1)} km/h` : '-'
          const location = formatLocationInfo(point)

          const content = `
            <div style="padding: 8px 12px; background: rgba(255, 255, 255, 0.95); border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-size: 12px; line-height: 1.6;">
              <div style="font-weight: bold; color: #333; margin-bottom: 4px;">点 #${nearestIndex}</div>
              ${location ? `<div style="color: #666;">${location}</div>` : ''}
              <div style="color: #666;">时间: ${timeStr}</div>
              <div style="color: #666;">速度: ${speed}</div>
              <div style="color: #666;">海拔: ${elevation}</div>
            </div>
          `

          tooltip.setContent(content)
          tooltip.setPosition(new AMap.LngLat(nearestPosition[0], nearestPosition[1]))
          tooltip.open(AMapInstance)

          // 发射事件
          emit('point-hover', point, nearestIndex)
        }
      } else {
        hideMarker()
      }
    }

    // 高德地图 mousemove 监听（作为主要事件源）
    AMapInstance.on('mousemove', (e: any) => {
      const lngLat = e.lnglat
      const mouseLngLat: [number, number] = [lngLat.lng, lngLat.lat]
      handleMouseMove(mouseLngLat)
    })

    // 备用方案：在 DOM 容器级别监听鼠标移动（捕获阶段）
    // 这样即使 polyline 阻止了事件冒泡，也能捕获到鼠标移动
    if (mapContainer.value) {
      mapContainer.value.addEventListener('mousemove', (e: MouseEvent) => {
        if (!AMapInstance) return
        // 将容器坐标转换为地图坐标
        const lngLat = AMapInstance.containerToLngLat(new AMap.Pixel(e.offsetX, e.offsetY))
        if (!lngLat) return
        const mouseLngLat: [number, number] = [lngLat.lng, lngLat.lat]
        handleMouseMove(mouseLngLat)
      }, true)  // 使用捕获阶段

      // 监听鼠标离开
      mapContainer.value.addEventListener('mouseleave', () => {
        hideMarker()
      }, true)
    }

    // 移动端：点击地图显示轨迹信息
    const isMobile = window.innerWidth <= 768
    if (isMobile) {
      AMapInstance.on('click', (e: any) => {
        const lngLat = e.lnglat
        const mouseLngLat: [number, number] = [lngLat.lng, lngLat.lat]

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
          const AMap = (window as any).AMap

          mouseMarker.setPosition(new AMap.LngLat(nearestPosition[0], nearestPosition[1]))
          mouseMarker.setMap(AMapInstance)

          const timeStr = point.time ? new Date(point.time).toLocaleTimeString('zh-CN') : '-'
          const elevation = point.elevation != null ? `${point.elevation.toFixed(1)} m` : '-'
          const speed = point.speed != null ? `${(point.speed * 3.6).toFixed(1)} km/h` : '-'
          const location = formatLocationInfo(point)

          const content = `
            <div style="padding: 8px 12px; background: rgba(255, 255, 255, 0.95); border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-size: 12px; line-height: 1.6;">
              <div style="font-weight: bold; color: #333; margin-bottom: 4px;">点 #${nearestIndex}</div>
              ${location ? `<div style="color: #666;">${location}</div>` : ''}
              <div style="color: #666;">时间: ${timeStr}</div>
              <div style="color: #666;">速度: ${speed}</div>
              <div style="color: #666;">海拔: ${elevation}</div>
            </div>
          `

          tooltip.setContent(content)
          tooltip.setPosition(new AMap.LngLat(nearestPosition[0], nearestPosition[1]))
          tooltip.open(AMapInstance)

          lastHoverIndex = nearestIndex
          emit('point-hover', point, nearestIndex)
        } else {
          hideMarker()
        }
      })
    }

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

  const AMap = (window as any).AMap
  const bounds: any[] = []

  for (const track of props.tracks) {
    if (!track.points || track.points.length === 0) continue

    const path: any[] = []

    for (const point of track.points) {
      const coords = getGCJ02Coords(point)
      if (!coords) continue

      const [lng, lat] = coords
      path.push(new AMap.LngLat(lng, lat))
      bounds.push(new AMap.LngLat(lng, lat))

      // 保存轨迹点数据（用于查询）
      trackPoints.push(point)
      trackPath.push({ lng, lat })
    }

    if (path.length === 0) continue

    // 绘制轨迹线
    const isHighlighted = track.id === props.highlightTrackId
    const polyline = new AMap.Polyline({
      path: path,
      borderWeight: 1,
      strokeColor: '#FF0000',
      strokeOpacity: 0.8,
      strokeWeight: isHighlighted ? 5 : 3,
      lineJoin: 'round',
      bubble: true,  // 允许鼠标事件冒泡，以便地图能够捕获 mousemove
    })

    AMapInstance.add(polyline)
    polylines.push(polyline)
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

// 生命周期
onMounted(async () => {
  await init()
})

onUnmounted(() => {
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

// 暴露方法给父组件
defineExpose({
  highlightPoint,
  hideMarker,
  resize,
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
</style>
