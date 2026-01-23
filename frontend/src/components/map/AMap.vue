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

// 高德地图实例
const mapContainer = ref<HTMLElement>()
let AMapInstance: any = null
let polylines: any[] = []

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
    })

    AMapInstance.add(polyline)
    polylines.push(polyline)
  }

  // 自动适应视图
  if (bounds.length > 0 && AMapInstance.setFitView) {
    try {
      AMapInstance.setFitView()
    } catch (e) {
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
  if (AMapInstance) {
    try {
      AMapInstance.destroy()
    } catch (e) {
      // ignore
    }
    AMapInstance = null
  }
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
