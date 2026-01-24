<template>
  <div class="bmap-container">
    <div ref="mapContainer" class="bmap"></div>
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

// 百度地图实例
const mapContainer = ref<HTMLElement>()
let BMapInstance: any = null
let polylines: any[] = []
let mouseMarker: any = null
let trackPoints: Point[] = []
let trackPath: { lng: number; lat: number }[] = []
let lastHoverIndex = -1

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

// 创建信息提示框
function createTooltip() {
  // 百度地图的 InfoWindow 每次都创建新实例，不需要预创建
}

// 显示 tooltip（每次都创建新的 InfoWindow 实例）
function showTooltip(nearestIndex: number, point: Point, position: { lng: number; lat: number }) {
  if (!BMapInstance) return

  const BMapGL = (window as any).BMapGL

  const timeStr = point.time ? new Date(point.time).toLocaleTimeString('zh-CN') : '-'
  const elevation = point.elevation != null ? `${point.elevation.toFixed(1)} m` : '-'
  const speed = point.speed != null ? `${(point.speed * 3.6).toFixed(1)} km/h` : '-'
  const location = formatLocationInfo(point)

  // 合并为单一内容（与 Leaflet 和 AMap 保持一致）
  const title = `
  <div style="padding: 8px 12px; border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-size: 12px; line-height: 1.6;">
  <div style="font-weight: bold; color: #333; margin-bottom: 4px;">点 #${nearestIndex}</div>
  <div>
  `
  const content = `
    <div style="padding: 8px 12px; background: rgba(255, 255, 255, 0.95); border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.15); font-size: 12px; line-height: 1.6;">
      <!--div style="font-weight: bold; color: #333; margin-bottom: 4px;">点 #${nearestIndex}</div-->
      ${location ? `<div style="color: #666;">${location}</div>` : ''}
      <div style="color: #666;">时间: ${timeStr}</div>
      <div style="color: #666;">速度: ${speed}</div>
      <div style="color: #666;">海拔: ${elevation}</div>
    </div>
  `

  // 每次创建新的 InfoWindow 实例
  const newTooltip = new BMapGL.InfoWindow(content, {
    width: 200,
    height: 0,
    offset: new BMapGL.Size(0, 0),
    title: title,
  })

  const bmapPoint = new BMapGL.Point(position.lng, position.lat)

  // 先关闭当前的 InfoWindow，然后使用 setTimeout 确保关闭完成后再打开新的
  // 百度地图 InfoWindow 有状态管理问题，连续调用 openInfoWindow 可能不生效
  BMapInstance.closeInfoWindow()

  // 使用 setTimeout 确保在下一个事件循环中打开，避免状态冲突
  setTimeout(() => {
    BMapInstance.openInfoWindow(newTooltip, bmapPoint)
  }, 0)
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
  if (mouseMarker && BMapInstance) {
    try {
      BMapInstance.removeOverlay(mouseMarker)
    } catch (e) {
      // ignore
    }
  }
  if (BMapInstance) {
    BMapInstance.closeInfoWindow()
  }
  emit('point-hover', null, -1)
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

    // 创建标记和提示框
    createMouseMarker()
    createTooltip()

    // 统一的鼠标处理函数
    const handleMouseMove = (e: any) => {
      if (trackPath.length < 2 || !BMapInstance) return

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

    // 百度地图 mousemove 监听
    BMapInstance.addEventListener('mousemove', handleMouseMove)

    // 移动端：点击地图显示轨迹信息
    const isMobile = window.innerWidth <= 768
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

  const BMapGL = (window as any).BMapGL
  const bounds: any[] = []

  for (const track of props.tracks) {
    if (!track.points || track.points.length === 0) continue

    const points: any[] = []

    for (const point of track.points) {
      const coords = getBD09Coords(point)
      if (!coords) continue

      const { lng, lat } = coords
      points.push(new BMapGL.Point(lng, lat))
      bounds.push(new BMapGL.Point(lng, lat))
      // 保存轨迹点和路径用于鼠标悬停
      trackPoints.push(point)
      trackPath.push({ lng, lat })
    }

    if (points.length === 0) continue

    // 绘制轨迹线
    const isHighlighted = track.id === props.highlightTrackId
    const polyline = new BMapGL.Polyline(points, {
      strokeColor: '#FF0000',
      strokeWeight: isHighlighted ? 5 : 3,
      strokeOpacity: 0.8,
    })

    BMapInstance.addOverlay(polyline)
    polylines.push(polyline)
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

// 暴露方法给父组件
defineExpose({
  highlightPoint,
  hideMarker,
  resize,
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

</style>
