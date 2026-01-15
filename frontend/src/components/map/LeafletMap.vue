<template>
  <div class="leaflet-map-container">
    <div ref="mapContainer" class="map"></div>
    <div class="map-controls">
      <el-button-group size="small">
        <el-button
          v-for="provider in mapProviders"
          :key="provider.value"
          :type="currentProvider === provider.value ? 'primary' : ''"
          @click="switchProvider(provider.value)"
        >
          {{ provider.label }}
        </el-button>
      </el-button-group>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useConfigStore, type MapProvider } from '@/stores/config'

// 类型定义
type CRS = 'wgs84' | 'gcj02' | 'bd09'

interface Point {
  latitude?: number
  longitude?: number
  latitude_wgs84?: number
  longitude_wgs84?: number
  latitude_gcj02?: number | null
  longitude_gcj02?: number | null
  latitude_bd09?: number | null
  longitude_bd09?: number | null
  elevation?: number
  time?: string
  province?: string
  city?: string
  district?: string
  road_name?: string
  road_number?: string
}

interface Track {
  id: number
  points: Point[]
}

interface Props {
  tracks?: Track[]
  highlightTrackId?: number
  defaultProvider?: MapProvider
}

const props = withDefaults(defineProps<Props>(), {
  tracks: () => [],
  highlightTrackId: undefined,
  defaultProvider: undefined,
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

// 当前底图提供商 - 从配置或 prop 获取
const currentProvider = ref<MapProvider>(
  props.defaultProvider || configStore.getMapProvider()
)

// 底图配置
const mapProviders = [
  { value: 'osm' as MapProvider, label: 'OSM' },
  { value: 'amap' as MapProvider, label: '高德' },
  { value: 'baidu' as MapProvider, label: '百度' },
]

// 底图 URL
const tileUrls = {
  osm: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
  amap: 'https://webrd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
  baidu: 'https://online1.map.bdimg.com/tile/?qt=tile&x={x}&y={y}&z={z}&styles=pl',
}

// 根据底图提供商获取对应的坐标系
function getCRSForProvider(provider: MapProvider): CRS {
  const crsMap: Record<MapProvider, CRS> = {
    osm: 'wgs84',
    amap: 'gcj02',
    baidu: 'bd09',
  }
  return crsMap[provider]
}

// 初始化地图
function initMap() {
  console.log('[LeafletMap] initMap, mapContainer:', mapContainer.value)
  if (!mapContainer.value) {
    console.error('[LeafletMap] mapContainer is null!')
    return
  }

  // 创建地图
  map.value = L.map(mapContainer.value, {
    center: [39.9, 116.4],
    zoom: 10,
    zoomControl: true,
  })

  console.log('[LeafletMap] map created:', map.value)

  // 添加默认底图（使用当前提供商）
  addTileLayer(currentProvider.value)
}

// 添加底图
function addTileLayer(provider: MapProvider) {
  if (!map.value) return

  // 移除现有底图
  map.value.eachLayer((layer) => {
    if (layer instanceof L.TileLayer) {
      map.value!.removeLayer(layer)
    }
  })

  // 添加新底图
  L.tileLayer(tileUrls[provider], {
    maxZoom: 19,
    attribution: getAttribution(provider),
  }).addTo(map.value!)
}

// 获取版权信息
function getAttribution(provider: MapProvider): string {
  const attributions = {
    osm: '&copy; OpenStreetMap contributors',
    amap: '&copy; 高德地图',
    baidu: '&copy; 百度地图',
  }
  return attributions[provider]
}

// 切换底图
function switchProvider(provider: MapProvider) {
  currentProvider.value = provider
  addTileLayer(provider)

  // 重新绘制轨迹（使用正确的坐标系）
  updateTracks()
}

// 根据坐标系获取经纬度字段
function getCoords(point: Point, crs: CRS): [number, number] {
  if (crs === 'wgs84') {
    return [point.latitude, point.longitude]
  } else if (crs === 'gcj02') {
    // 需要后端提供 gcj02 坐标，这里暂时假设有对应的字段
    return [point.latitude || 0, point.longitude || 0]
  } else if (crs === 'bd09') {
    return [point.latitude || 0, point.longitude || 0]
  }
  return [point.latitude, point.longitude]
}

// 绘制轨迹
function drawTracks() {
  if (!map.value || !props.tracks.length) return

  const crs = getCRSForProvider(currentProvider.value)

  // 清除现有轨迹
  clearTracks()

  const bounds = L.latLngBounds([])

  for (const track of props.tracks) {
    if (!track.points || track.points.length === 0) continue

    const latLngs: L.LatLngExpression[] = []

    for (const point of track.points) {
      let lat: number | undefined, lng: number | undefined

      // 根据底图选择对应的坐标
      if (currentProvider.value === 'osm') {
        lat = (point as any).latitude_wgs84 ?? point.latitude
        lng = (point as any).longitude_wgs84 ?? point.longitude
      } else if (currentProvider.value === 'amap') {
        lat = (point as any).latitude_gcj02 ?? (point as any).latitude_wgs84 ?? point.latitude
        lng = (point as any).longitude_gcj02 ?? (point as any).longitude_wgs84 ?? point.longitude
      } else {
        lat = (point as any).latitude_bd09 ?? (point as any).latitude_wgs84 ?? point.latitude
        lng = (point as any).longitude_bd09 ?? (point as any).longitude_wgs84 ?? point.longitude
      }

      // 跳过无效坐标
      if (lat === undefined || lng === undefined || isNaN(lat) || isNaN(lng)) {
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

    polyline.addTo(map.value)
    polylineLayers.value.set(track.id, polyline)
  }

  // 自动适应视图
  if (bounds.isValid()) {
    const mapSize = map.value.getSize()
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

  // 更新当前提供商（从配置或 prop 获取）
  currentProvider.value = props.defaultProvider || configStore.getMapProvider()
  console.log('[LeafletMap] Using provider:', currentProvider.value)

  initMap()
  drawTracks()
})

onUnmounted(() => {
  if (map.value) {
    map.value.remove()
  }
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
