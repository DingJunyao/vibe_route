<template>
  <div class="leaflet-map-container">
    <div ref="mapContainer" class="map"></div>
    <div class="map-controls">
      <el-button-group size="small">
        <el-button
          v-for="layer in mapLayers"
          :key="layer.id"
          :type="currentLayerId === layer.id ? 'primary' : ''"
          @click="switchLayer(layer.id)"
        >
          {{ layer.name }}
        </el-button>
      </el-button-group>
      <el-button-group size="small" style="margin-left: 8px">
        <el-button @click="toggleFullscreen">
          <el-icon><FullScreen /></el-icon>
        </el-button>
      </el-button-group>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import 'proj4leaflet'
import 'leaflet.chinatmsproviders'
import { useConfigStore } from '@/stores/config'
import { FullScreen } from '@element-plus/icons-vue'
import type { MapLayerConfig, CRSType } from '@/api/admin'

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
  province?: string | null
  city?: string | null
  district?: string | null
  road_name?: string | null
  road_number?: string | null
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

const emit = defineEmits<{
  (e: 'point-click', point: Point, trackId: number): void
}>()

const configStore = useConfigStore()

// 地图实例
const mapContainer = ref<HTMLElement>()
const map = ref<L.Map | null>(null)
const polylineLayers = ref<Map<number, L.Polyline>>(new Map())
const markers = ref<L.Marker[]>([])

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
    // leaflet.chinatmsproviders 提供的百度 CRS
    return (L.CRS as any).Baidu || L.CRS.EPSG3857
  }
  return L.CRS.EPSG3857
}

// 初始化地图
function initMap() {
  console.log('[LeafletMap] initMap, mapContainer:', mapContainer.value)
  if (!mapContainer.value) {
    console.error('[LeafletMap] mapContainer is null!')
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

  console.log('[LeafletMap] map created with CRS:', crs, layerConfig)

  // 添加默认底图（使用当前提供商）
  addTileLayer(currentLayerId.value)

  // 添加比例尺
  L.control.scale({
    position: 'bottomleft',
    imperial: false, // 不使用英制单位
  }).addTo(map.value as L.Map)
}

// 添加底图
function addTileLayer(layerId: string) {
  if (!map.value) return

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
      }).addTo(map.value)
    } else {
      // 降级方案：使用标准 TileLayer
      L.tileLayer(layerConfig.url, {
        maxZoom: layerConfig.max_zoom,
        minZoom: layerConfig.min_zoom,
        attribution: layerConfig.attribution,
        subdomains: layerConfig.subdomains || undefined,
      }).addTo(map.value)
    }
  } else if (layerConfig.crs === 'gcj02') {
    // 高德地图 - 使用 GaoDe 而不是 Gaode
    const chinaProvider = (L.tileLayer as any).chinaProvider
    if (chinaProvider) {
      chinaProvider('GaoDe.Normal.Map', {
        maxZoom: layerConfig.max_zoom,
        minZoom: layerConfig.min_zoom,
      }).addTo(map.value)
    } else {
      L.tileLayer(layerConfig.url, {
        maxZoom: layerConfig.max_zoom,
        minZoom: layerConfig.min_zoom,
        attribution: layerConfig.attribution,
        subdomains: layerConfig.subdomains || undefined,
      }).addTo(map.value)
    }
  } else {
    // OSM 或其他 WGS84 地图
    let url = layerConfig.url
    L.tileLayer(url, {
      maxZoom: layerConfig.max_zoom,
      minZoom: layerConfig.min_zoom,
      attribution: layerConfig.attribution,
      subdomains: layerConfig.subdomains || undefined,
    }).addTo(map.value)
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
function getCoordsByCRS(point: Point, crs: CRSType): [number, number] | null {
  if (crs === 'wgs84') {
    const lat = point.latitude_wgs84 ?? point.latitude
    const lng = point.longitude_wgs84 ?? point.longitude
    if (lat !== undefined && lng !== undefined) {
      return [lat, lng]
    }
  } else if (crs === 'gcj02') {
    const lat = point.latitude_gcj02 ?? point.latitude_wgs84 ?? point.latitude
    const lng = point.longitude_gcj02 ?? point.longitude_wgs84 ?? point.longitude
    if (lat !== undefined && lng !== undefined) {
      return [lat, lng]
    }
  } else if (crs === 'bd09') {
    const lat = point.latitude_bd09 ?? point.latitude_wgs84 ?? point.latitude
    const lng = point.longitude_bd09 ?? point.longitude_wgs84 ?? point.longitude
    if (lat !== undefined && lng !== undefined) {
      return [lat, lng]
    }
  }
  return null
}

// 绘制轨迹
function drawTracks() {
  if (!map.value || !props.tracks.length) return

  const crs = currentLayerConfig.value?.crs || 'wgs84'

  // 清除现有轨迹
  clearTracks()

  const bounds = L.latLngBounds([])

  for (const track of props.tracks) {
    if (!track.points || track.points.length === 0) continue

    const latLngs: L.LatLngExpression[] = []

    for (const point of track.points) {
      const coords = getCoordsByCRS(point, crs)
      if (!coords) continue

      const [lat, lng] = coords
      // 跳过无效坐标
      if (isNaN(lat) || isNaN(lng)) {
        continue
      }

      latLngs.push([lat, lng])
      bounds.extend([lat, lng])
    }

    // 如果没有有效点，跳过
    if (latLngs.length === 0) continue

    // 绘制轨迹线
    const isHighlighted = track.id === props.highlightTrackId
    const polyline = L.polyline(latLngs, {
      color: isHighlighted ? '#ff0000' : '#3b82f6',
      weight: isHighlighted ? 5 : 3,
      opacity: 0.8,
    })

    polyline.on('click', () => {
      // 轨迹点击事件
    })

    polyline.addTo(map.value as L.Map)
    polylineLayers.value.set(track.id, polyline)
  }

  // 自动适应视图
  if (bounds.isValid()) {
    map.value.fitBounds(bounds, { padding: [0, 0] })
  }
}

// 清除轨迹
function clearTracks() {
  polylineLayers.value.forEach((polyline) => {
    map.value!.removeLayer(polyline)
  })
  polylineLayers.value.clear()

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

// 生命周期
onMounted(async () => {
  console.log('[LeafletMap] onMounted, props.tracks:', props.tracks)

  // 等待配置加载完成（如果还没有加载）
  if (!configStore.config) {
    await configStore.fetchConfig()
  }

  // 初始化地图层列表
  initMapLayers()

  // 更新当前层（从 prop 或配置获取）
  const defaultId = props.defaultLayerId || configStore.getMapProvider()
  const exists = mapLayers.value.find((l: MapLayerConfig) => l.id === defaultId)
  currentLayerId.value = exists ? defaultId : (mapLayers.value[0]?.id || 'osm')
  updateCurrentLayerConfig()
  console.log('[LeafletMap] Using layer:', currentLayerId.value, currentLayerConfig.value)

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
}

:deep(.leaflet-container) {
  background: #e5e5e5;
}

:deep(.leaflet-control-attribution) {
  font-size: 10px;
}
</style>
