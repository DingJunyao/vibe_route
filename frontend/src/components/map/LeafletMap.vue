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
import { ref, Ref, onMounted, onUnmounted, watch } from 'vue'
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
}

interface Props {
  tracks?: Track[]
  highlightTrackId?: number
  defaultLayerId?: string
  hideLayerSelector?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  tracks: () => [],
  highlightTrackId: undefined,
  defaultLayerId: undefined,
  hideLayerSelector: false,
})

const emit = defineEmits<{
  (e: 'point-click', point: Point, trackId: number): void
  (e: 'point-hover', point: Point | null, pointIndex: number): void
}>()

const configStore = useConfigStore()

// 地图实例
const mapContainer = ref<HTMLElement>()
const map = ref<L.Map | null>(null)
const polylineLayers = ref<Map<number, L.Polyline>>(new Map())
const markers = ref<L.Marker[]>([])

// 轨迹数据
const trackPoints: Ref<Point[]> = ref([])
const trackPath: Ref<[number, number][]> = ref([])

// 鼠标标记和 tooltip
const mouseMarker = ref<L.Marker | null>(null)
const tooltip = ref<L.Popup | null>(null)
const lastHoverIndex = ref(-1)

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

  // 添加默认底图（使用当前提供商）
  addTileLayer(currentLayerId.value)

  // 添加比例尺
  L.control.scale({
    position: 'bottomleft',
    imperial: false, // 不使用英制单位
  }).addTo(map.value as L.Map)

  // 创建标记和提示框
  createMouseMarker()
  createTooltip()

  // 统一的鼠标处理函数
  const handleMouseMove = (lng: number, lat: number) => {
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
      // 如果是同一个点，跳过更新
      if (nearestIndex !== lastHoverIndex.value) {
        lastHoverIndex.value = nearestIndex

        // 更新标记位置并显示
        if (mouseMarker.value) {
          mouseMarker.value.setLatLng([nearestPosition[1], nearestPosition[0]])
          mouseMarker.value.addTo(map.value!)
        }

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

        if (tooltip.value) {
          tooltip.value.setContent(content)
          tooltip.value.setLatLng([nearestPosition[1], nearestPosition[0]])
          tooltip.value.openOn(map.value!)
        }

        // 发射事件
        emit('point-hover', point, nearestIndex)
      }
    } else {
      hideMarker()
    }
  }

  // Leaflet mousemove 监听
  map.value.on('mousemove', (e: L.LeafletMouseEvent) => {
    handleMouseMove(e.latlng.lng, e.latlng.lat)
  })

  // 移动端：点击地图显示轨迹信息
  const isMobile = window.innerWidth <= 768
  if (isMobile) {
    map.value.on('click', (e: L.LeafletMouseEvent) => {
      const lng = e.latlng.lng
      const lat = e.latlng.lat

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

        if (tooltip.value) {
          tooltip.value.setContent(content)
          tooltip.value.setLatLng([nearestPosition[1], nearestPosition[0]])
          tooltip.value.openOn(map.value!)
        }

        lastHoverIndex.value = nearestIndex
        emit('point-hover', point, nearestIndex)
      } else {
        hideMarker()
      }
    })
  }
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
  createTooltip()

  // 统一的鼠标处理函数
  const handleMouseMove = (lng: number, lat: number) => {
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
      // 如果是同一个点，跳过更新
      if (nearestIndex !== lastHoverIndex.value) {
        lastHoverIndex.value = nearestIndex

        // 更新标记位置并显示
        if (mouseMarker.value) {
          mouseMarker.value.setLatLng([nearestPosition[1], nearestPosition[0]])
          mouseMarker.value.addTo(map.value!)
        }

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

        if (tooltip.value) {
          tooltip.value.setContent(content)
          tooltip.value.setLatLng([nearestPosition[1], nearestPosition[0]])
          tooltip.value.openOn(map.value!)
        }

        // 发射事件
        emit('point-hover', point, nearestIndex)
      }
    } else {
      hideMarker()
    }
  }

  // Leaflet mousemove 监听
  map.value.on('mousemove', (e: L.LeafletMouseEvent) => {
    handleMouseMove(e.latlng.lng, e.latlng.lat)
  })

  // 移动端：点击地图显示轨迹信息
  const isMobile = window.innerWidth <= 768
  if (isMobile) {
    map.value.on('click', (e: L.LeafletMouseEvent) => {
      const lng = e.latlng.lng
      const lat = e.latlng.lat

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

        if (tooltip.value) {
          tooltip.value.setContent(content)
          tooltip.value.setLatLng([nearestPosition[1], nearestPosition[0]])
          tooltip.value.openOn(map.value!)
        }

        lastHoverIndex.value = nearestIndex
        emit('point-hover', point, nearestIndex)
      } else {
        hideMarker()
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
// 注意：天地图使用 chinaProvider 时，瓦片数据已经是 GCJ02 偏移过的，所以应该传入 WGS84 坐标
function getCoordsByCRS(point: Point, crs: CRSType, mapId?: string): [number, number] | null {
  if (crs === 'wgs84') {
    const lat = point.latitude_wgs84 ?? point.latitude
    const lng = point.longitude_wgs84 ?? point.longitude
    if (lat !== undefined && lng !== undefined) {
      return [lat, lng]
    }
  } else if (crs === 'gcj02') {
    // 天地图使用 chinaProvider，瓦片数据已经是 GCJ02 的，所以传入 WGS84 坐标
    if (mapId === 'tianditu') {
      const lat = point.latitude_wgs84 ?? point.latitude
      const lng = point.longitude_wgs84 ?? point.longitude
      if (lat !== undefined && lng !== undefined) {
        return [lat, lng]
      }
    } else {
      // 其他 GCJ02 地图（如高德）使用 GCJ02 坐标
      const lat = point.latitude_gcj02 ?? point.latitude_wgs84 ?? point.latitude
      const lng = point.longitude_gcj02 ?? point.longitude_wgs84 ?? point.longitude
      if (lat !== undefined && lng !== undefined) {
        return [lat, lng]
      }
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

  if (!map.value || !mouseMarker.value || !tooltip.value || !point || !position) return

  // 更新标记位置
  mouseMarker.value.setLatLng([position[1], position[0]])
  mouseMarker.value.addTo(map.value)

  // 创建 tooltip 内容
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

  tooltip.value.setContent(content)
  tooltip.value.setLatLng([position[1], position[0]])
  tooltip.value.openOn(map.value)
}

// 隐藏标记
function hideMarker() {
  if (mouseMarker.value) {
    map.value?.removeLayer(mouseMarker.value)
  }
  if (tooltip.value) {
    map.value?.closePopup()
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

// 创建 tooltip
function createTooltip() {
  if (!map.value) return

  tooltip.value = L.popup({
    closeButton: false,
    closeOnClick: false,
    autoClose: false,
    className: 'leaflet-mouse-tooltip',
    offset: [0, -10],
  })
}

// 绘制轨迹
function drawTracks() {
  if (!map.value || !props.tracks.length) return

  const crs = currentLayerConfig.value?.crs || 'wgs84'
  const mapId = currentLayerConfig.value?.id

  // 清除现有轨迹
  clearTracks()

  // 重置轨迹数据
  trackPoints.value = []
  trackPath.value = []

  const bounds = L.latLngBounds([])

  for (const track of props.tracks) {
    if (!track.points || track.points.length === 0) continue

    const latLngs: L.LatLngExpression[] = []

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
      // 保存轨迹点和路径用于鼠标悬停
      trackPoints.value.push(point)
      trackPath.value.push([lng, lat])  // Leaflet 使用 [lng, lat]
    }

    // 如果没有有效点，跳过
    if (latLngs.length === 0) continue

    // 绘制轨迹线
    const isHighlighted = track.id === props.highlightTrackId
    const polyline = L.polyline(latLngs, {
      color: '#ff0000',
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

// 监听 defaultLayerId 变化（从 UniversalMap 传入）
watch(() => props.defaultLayerId, (newId) => {
  if (newId && newId !== currentLayerId.value) {
    switchLayer(newId)
  }
})

// 暴露方法给父组件
defineExpose({
  highlightPoint,
  hideMarker,
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
@media (max-width: 768px) {
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
}

:deep(.leaflet-control-attribution) {
  font-size: 10px;
}

/* 鼠标标记样式 */
:deep(.leaflet-mouse-marker) {
  background: #409eff;
  border: 2px solid #fff;
  border-radius: 50%;
  box-shadow: 0 0 4px rgba(0, 0, 0, 0.3);
}

/* Tooltip 样式 - 移除白边 */
:deep(.leaflet-mouse-tooltip) {
  background: transparent;
  border: none;
  box-shadow: none;
}

:deep(.leaflet-mouse-tooltip .leaflet-popup-content-wrapper) {
  background: transparent;
  border: none;
  box-shadow: none;
  padding: 0;
}

:deep(.leaflet-mouse-tooltip .leaflet-popup-tip) {
  display: none;
}

:deep(.leaflet-mouse-tooltip .leaflet-popup-content) {
  margin: 0;
}
</style>
