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

// 腾讯地图实例
const mapContainer = ref<HTMLElement>()
let TMapInstance: any = null
let polylineLayer: any = null

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

    // 绘制轨迹
    drawTracks()
  } catch (error) {
    console.error('[TencentMap] Failed to initialize:', error)
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

  // 准备轨迹数据
  const geometries: any[] = []
  const bounds: any[] = []

  for (const track of props.tracks) {
    if (!track.points || track.points.length === 0) continue

    const paths: any[] = []

    for (const point of track.points) {
      const coords = getGCJ02Coords(point)
      if (!coords) continue

      const { lat, lng } = coords
      paths.push(new TMap.LatLng(lat, lng))
      bounds.push(new TMap.LatLng(lat, lng))
    }

    if (paths.length === 0) continue

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

// 生命周期
onMounted(async () => {
  await init()
})

onUnmounted(() => {
  if (polylineLayer) {
    polylineLayer.setMap(null)
    polylineLayer = null
  }
  if (TMapInstance) {
    TMapInstance.destroy()
    TMapInstance = null
  }
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
</style>
