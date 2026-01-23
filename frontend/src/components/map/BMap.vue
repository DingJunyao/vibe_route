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
}

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
      // 清理回调函数
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
      enableRotate: false,  // 禁用旋转
      enableTilt: false,     // 禁用倾斜（3D视角）
    })

    const point = new BMapGL.Point(116.404, 39.915)
    BMapInstance.centerAndZoom(point, 12)

    // 启用鼠标滚轮缩放
    BMapInstance.enableScrollWheelZoom(true)

    // 添加缩放控件（位置通过 CSS 设置）
    const zoomCtrl = new BMapGL.ZoomControl()
    BMapInstance.addControl(zoomCtrl)

    // 添加比例尺（位置通过 CSS 设置）
    const scaleCtrl = new BMapGL.ScaleControl()
    BMapInstance.addControl(scaleCtrl)

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
      // 如果 setViewport 失败，手动设置中心
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
</style>
