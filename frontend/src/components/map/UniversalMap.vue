<template>
  <div class="universal-map-container">
    <!-- 腾讯地图引擎 -->
    <TencentMap
      v-if="useTencentEngine"
      ref="tencentRef"
      :tracks="tracks"
      :highlight-track-id="highlightTrackId"
      :highlight-segment="highlightSegment"
      :colored-segments="coloredSegments"
      :available-segments="availableSegments"
      :highlight-point-index="highlightPointIndex"
      :latest-point-index="latestPointIndex"
      :mode="mode"
      :map-scale="mapScale"
      :track-orientation="trackOrientation"
      :disable-point-hover="disablePointHover"
      :custom-overlays="customOverlays"
      @point-hover="handlePointHover"
      @track-hover="handleTrackHover"
      @track-click="handleTrackClick"
      @map-click="handleMapClick"
    />
    <!-- 高德地图引擎 -->
    <AMap
      v-else-if="useAMapEngine"
      ref="amapRef"
      :tracks="tracks"
      :highlight-track-id="highlightTrackId"
      :highlight-segment="highlightSegment"
      :colored-segments="coloredSegments"
      :available-segments="availableSegments"
      :highlight-point-index="highlightPointIndex"
      :latest-point-index="latestPointIndex"
      :mode="mode"
      :map-scale="mapScale"
      :track-orientation="trackOrientation"
      :disable-point-hover="disablePointHover"
      :custom-overlays="customOverlays"
      @point-hover="handlePointHover"
      @track-hover="handleTrackHover"
      @track-click="handleTrackClick"
      @map-click="handleMapClick"
    />
    <!-- 百度地图引擎 -->
    <BMap
      v-else-if="useBMapEngine"
      ref="bmapRef"
      :tracks="tracks"
      :highlight-track-id="highlightTrackId"
      :highlight-segment="highlightSegment"
      :colored-segments="coloredSegments"
      :available-segments="availableSegments"
      :highlight-point-index="highlightPointIndex"
      :latest-point-index="latestPointIndex"
      :default-layer-id="currentLayerId"
      :mode="mode"
      :map-scale="mapScale"
      :track-orientation="trackOrientation"
      :disable-point-hover="disablePointHover"
      :custom-overlays="customOverlays"
      @point-hover="handlePointHover"
      @track-hover="handleTrackHover"
      @track-click="handleTrackClick"
      @map-click="handleMapClick"
    />
    <!-- Leaflet 地图引擎 -->
    <LeafletMap
      v-else
      ref="leafletRef"
      :tracks="tracks"
      :highlight-track-id="highlightTrackId"
      :highlight-segment="highlightSegment"
      :colored-segments="coloredSegments"
      :available-segments="availableSegments"
      :highlight-point-index="highlightPointIndex"
      :latest-point-index="latestPointIndex"
      :default-layer-id="currentLayerId"
      :hide-layer-selector="true"
      :mode="mode"
      :map-scale="mapScale"
      :track-orientation="trackOrientation"
      :disable-point-hover="disablePointHover"
      :custom-overlays="customOverlays"
      @point-hover="handlePointHover"
      @track-hover="handleTrackHover"
      @track-click="handleTrackClick"
      @map-click="handleMapClick"
    />
    <!-- 通用地图选择器 -->
    <div class="map-controls">
      <!-- 查看详情按钮（嵌入模式） -->
      <el-button
        v-if="viewDetailsUrl"
        type="primary"
        size="small"
        class="view-details-btn"
      >
        <a :href="viewDetailsUrl" target="_blank" class="view-details-link">
          <el-icon><Link /></el-icon>
          <span>查看详情</span>
        </a>
      </el-button>
      <!-- 实时更新时间标识 -->
      <el-button
        v-if="formattedLiveUpdateTime"
        type="success"
        size="small"
        class="live-update-time-btn"
      >
        {{ formattedLiveUpdateTime }}
      </el-button>
      <!-- 清除高亮按钮 -->
      <el-button-group v-if="highlightSegment" size="small" class="clear-highlight-btn">
        <el-button @click="clearSegmentHighlight">
          <el-icon><Close /></el-icon>
        </el-button>
      </el-button-group>
      <!-- 桌面端：按钮组 -->
      <el-button-group size="small" class="desktop-layer-selector">
        <el-button
          v-for="layer in enabledMapLayers"
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
        @change="handleLayerChange"
      >
        <el-option
          v-for="layer in enabledMapLayers"
          :key="layer.id"
          :label="layer.name"
          :value="layer.id"
        />
      </el-select>
      <el-button-group size="small" class="fit-bounds-btn">
        <el-button @click="fitBounds" title="居中显示轨迹">
          <el-icon :size="14">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="2"/>
              <line x1="12" y1="2" x2="12" y2="8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              <line x1="12" y1="16" x2="12" y2="22" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              <line x1="2" y1="12" x2="8" y2="12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              <line x1="16" y1="12" x2="22" y2="12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
          </el-icon>
        </el-button>
      </el-button-group>
      <el-button-group size="small" class="fullscreen-btn">
        <el-button @click="toggleFullscreen">
          <el-icon><FullScreen /></el-icon>
        </el-button>
      </el-button-group>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useConfigStore } from '@/stores/config'
import { Close, FullScreen, Link } from '@element-plus/icons-vue'
import LeafletMap from './LeafletMap.vue'
import AMap from './AMap.vue'
import BMap from './BMap.vue'
import TencentMap from './TencentMap.vue'
import type { MapLayerConfig } from '@/api/admin'
import { formatTimeShort } from '@/utils/relativeTime'
import { getEffectiveMapLayer, saveLocalMapPreference } from '@/utils/mapLocalPreference'

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
  id: number | string
  points: Point[]
  opacity?: number  // 轨迹透明度（0-1）
  color?: string   // 轨迹颜色
}

// 自定义覆盖层类型（用于绘制路径模式的控制点和曲线）
interface CustomOverlay {
  type: 'marker' | 'polyline'
  position?: [number, number]  // [lat, lng] for marker (默认 WGS84，优先使用下面的多坐标系字段)
  positions?: [number, number][]  // [[lat, lng], ...] for polyline
  // 多坐标系支持（优先使用这些字段）
  latitude_wgs84?: number
  longitude_wgs84?: number
  latitude_gcj02?: number | null
  longitude_gcj02?: number | null
  latitude_bd09?: number | null
  longitude_bd09?: number | null
  icon?: {
    type: 'circle'
    radius: number
    fillColor: string
    fillOpacity: number
    strokeColor: string
    strokeWidth: number
  }
  label?: string  // marker label
  color?: string  // polyline color
  weight?: number  // polyline weight
  opacity?: number  // polyline opacity
  dashArray?: string  // polyline dashArray
}

interface Props {
  tracks?: Track[]
  highlightTrackId?: number
  highlightSegments?: Array<{ start: number; end: number; color?: string }> | null
  highlightPointIndex?: number  // 新增：高亮指定索引的点
  latestPointIndex?: number | null  // 实时轨迹最新点索引（显示绿色标记）
  defaultLayerId?: string
  mode?: 'home' | 'detail'
  liveStatusText?: string  // 实时更新状态文字（已废弃，使用 liveUpdateTime）
  liveUpdateTime?: string | null  // 实时更新时间
  mapScale?: number  // 地图缩放百分比（100-200），用于海报生成时调整视野
  viewDetailsUrl?: string  // 嵌入模式：查看详情链接
  availableSegments?: Array<{ start: number; end: number; key: string }> | null  // 可用区段列表（用于插值页面）
  disablePointHover?: boolean  // 禁用轨迹点悬停显示（用于绘制路径模式）
  customOverlays?: CustomOverlay[]  // 自定义覆盖层（用于绘制路径模式的控制点和曲线）
}

const props = withDefaults(defineProps<Props>(), {
  tracks: () => [],
  highlightTrackId: undefined,
  highlightSegments: null,
  highlightPointIndex: undefined,
  latestPointIndex: null,
  defaultLayerId: undefined,
  mode: 'detail',
  liveStatusText: '',
  liveUpdateTime: null,
  mapScale: 100,
  viewDetailsUrl: '',
  availableSegments: null,
  disablePointHover: false,
  customOverlays: () => [],
})

// 定义 emit 事件
const emit = defineEmits<{
  (e: 'point-hover', point: Point | null, pointIndex: number): void
  (e: 'track-hover', trackId: number | null): void
  (e: 'track-click', trackId: number): void
  (e: 'clear-segment-highlight'): void
  (e: 'map-click', lng: number, lat: number): void  // 地图点击事件（用于添加控制点）
}>()

const configStore = useConfigStore()
const amapRef = ref()
const bmapRef = ref()
const tencentRef = ref()
const leafletRef = ref()

// 实时更新时间刷新
const timeRefreshKey = ref(0)
const UPDATE_INTERVAL = 1000 // 1 秒刷新一次
let updateTimer: number | null = null

// 格式化实时更新时间
const formattedLiveUpdateTime = computed(() => {
  // 依赖 timeRefreshKey 以触发刷新
  void timeRefreshKey.value
  if (!props.liveUpdateTime) return ''
  return formatTimeShort(props.liveUpdateTime)
})

// 合并多段高亮为一个区域（兼容现有实现）
const highlightSegment = computed(() => {
  const segments = props.highlightSegments

  // 如果是旧格式（单个对象 { start, end }），直接返回
  if (segments && !Array.isArray(segments)) {
    return segments as { start: number; end: number }
  }

  if (!segments || segments.length === 0) return null

  const first = segments[0]

  // 新格式：支持颜色
  if (first && 'color' in first) {
    // 只有蓝色才返回 highlightSegment（用于旧的单色高亮逻辑）
    // 橙色（已插值）、黄色（已插值选中）、绿色（可选）都由 coloredSegments 处理
    const blueSegment = segments.find(s => s.color === '#409eff')
    if (blueSegment) {
      return { start: blueSegment.start, end: blueSegment.end }
    }
    // 其他颜色不返回 highlightSegment（让 coloredSegments 处理）
    return null
  }

  // 旧格式兼容（数组格式）
  if (Array.isArray(segments)) {
    const minStart = Math.min(...segments.map((s: any) => s.start))
    const maxEnd = Math.max(...segments.map((s: any) => s.end))
    return { start: minStart, end: maxEnd }
  }

  return null
})

// 用于地图的多段高亮（带颜色）
const coloredSegments = computed(() => {
  const segments = props.highlightSegments
  if (!segments || segments.length === 0) return null

  // 检查是否是新格式（带颜色）
  const first = segments[0]
  if (first && 'color' in first) {
    return segments as Array<{ start: number; end: number; color: string }>
  }
  return null
})

// 计算轨迹方向（用于海报生成时的 zoom 调整）
// 返回 'horizontal'（横向）或 'vertical'（竖向）
const trackOrientation = computed(() => {
  if (!props.tracks || props.tracks.length === 0) return 'horizontal'

  // 收集所有轨迹点
  let minLat = Infinity, maxLat = -Infinity
  let minLon = Infinity, maxLon = -Infinity
  let pointCount = 0

  for (const track of props.tracks) {
    if (!track.points || track.points.length === 0) continue

    for (const point of track.points) {
      // 使用 WGS84 坐标（如果没有则回退）
      const lat = point.latitude_wgs84 ?? point.latitude ?? 0
      const lon = point.longitude_wgs84 ?? point.longitude ?? 0

      if (isNaN(lat) || isNaN(lon)) continue

      minLat = Math.min(minLat, lat)
      maxLat = Math.max(maxLat, lat)
      minLon = Math.min(minLon, lon)
      maxLon = Math.max(maxLon, lon)
      pointCount++
    }
  }

  if (pointCount === 0) return 'horizontal'

  // 计算边界框的宽高比
  const latDiff = maxLat - minLat
  const lonDiff = maxLon - minLon

  // 在中纬度地区，1 度纬度约 111km，1 度经度约 111km * cos(纬度)
  // 取平均纬度计算
  const avgLat = (minLat + maxLat) / 2
  const latToKm = 111
  const lonToKm = 111 * Math.cos(avgLat * Math.PI / 180)

  const heightKm = latDiff * latToKm
  const widthKm = lonDiff * lonToKm

  // 使用 1.5 作为阈值：宽高比 > 1.5 为横向，< 1/1.5 为竖向，中间为横向
  const ratio = widthKm / (heightKm || 1) // 避免除以 0

  const orientation = ratio > 1.5 ? 'horizontal' : 'vertical'

  console.log('[UniversalMap] 轨迹方向:', orientation === 'horizontal' ? '横' : '竖', `宽高比${ratio.toFixed(2)}`)

  return orientation
})

// 调试：检查 customOverlays
const customOverlaysDebug = computed(() => {
  const overlays = props.customOverlays || []
  console.log('[UniversalMap] customOverlays computed - 数量:', overlays.length)
  return overlays
})

// 当前选择的地图层 ID
const currentLayerId = ref<string>('')

// 保存的地图视角（用于切换地图时保持视角）
const savedViewState = ref<{
  center: { lat: number; lng: number } | null
  zoom: number | null
}>({ center: null, zoom: null })

// 判断是否使用高德地图引擎
const useAMapEngine = computed(() => {
  const layerId = currentLayerId.value
  if (layerId !== 'amap' && !layerId.startsWith('amap')) return false
  const amapConfig = configStore.getMapLayerById('amap')
  return !!(amapConfig?.api_key)
})

// 判断是否使用百度地图引擎（包括 GL 版本和 Legacy 版本）
const useBMapEngine = computed(() => {
  const layerId = currentLayerId.value
  if (layerId !== 'baidu' && !layerId.startsWith('baidu')) return false
  // baidu_legacy 使用百度地图的配置（api_key）
  const configKey = layerId === 'baidu_legacy' ? 'baidu' : layerId
  const baiduConfig = configStore.getMapLayerById(configKey)
  return !!(baiduConfig?.api_key || baiduConfig?.ak)
})

// 判断是否使用腾讯地图引擎
const useTencentEngine = computed(() => {
  const layerId = currentLayerId.value
  if (layerId !== 'tencent' && !layerId.startsWith('tencent')) return false
  const tencentConfig = configStore.getMapLayerById('tencent')
  return !!(tencentConfig?.api_key)
})

// 已启用的地图层列表
const enabledMapLayers = computed<MapLayerConfig[]>(() => {
  const allLayers = configStore.getMapLayers()
  return allLayers.filter((l: MapLayerConfig) => l.enabled).sort((a, b) => a.order - b.order)
})

// 获取当前地图的视角状态
function getCurrentViewState(): { center: { lat: number; lng: number } | null; zoom: number | null } {
  let center = null
  let zoom = null

  if (useAMapEngine.value && amapRef.value) {
    const instance = (amapRef.value as any).getMapInstance?.()
    if (instance) {
      const c = instance.getCenter()
      center = { lat: c.lat, lng: c.lng }
      zoom = instance.getZoom()
    }
  } else if (useBMapEngine.value && bmapRef.value) {
    const instance = (bmapRef.value as any).getMapInstance?.()
    if (instance) {
      const c = instance.getCenter?.() || instance.getCenter()
      if (c && c.lat && c.lng) {
        center = { lat: c.lat, lng: c.lng }
      }
      zoom = instance.getZoom?.()
    }
  } else if (useTencentEngine.value && tencentRef.value) {
    const instance = (tencentRef.value as any).getMapInstance?.()
    if (instance) {
      const c = instance.getCenter()
      center = { lat: c.lat, lng: c.lng }
      zoom = instance.getZoom()
    }
  } else if (leafletRef.value) {
    const instance = (leafletRef.value as any).getMapInstance?.()
    if (instance) {
      const c = instance.getCenter()
      center = { lat: c.lat, lng: c.lng }
      zoom = instance.getZoom()
    }
  }

  return { center, zoom }
}

// 设置地图的视角状态
function setMapViewState(center: { lat: number; lng: number }, zoom: number) {
  if (useAMapEngine.value && amapRef.value) {
    const instance = (amapRef.value as any).getMapInstance?.()
    if (instance) {
      instance.setZoomAndCenter(zoom, [center.lng, center.lat])
    }
  } else if (useBMapEngine.value && bmapRef.value) {
    const instance = (bmapRef.value as any).getMapInstance?.()
    if (instance) {
      const BMap = (window as any).BMap || (window as any).BMapGL
      instance.centerAndZoom(new BMap.Point(center.lng, center.lat), zoom)
    }
  } else if (useTencentEngine.value && tencentRef.value) {
    const instance = (tencentRef.value as any).getMapInstance?.()
    if (instance) {
      const TMap = (window as any).TMap
      instance.setCenter(new TMap.LatLng(center.lat, center.lng))
      instance.setZoom(zoom)
    }
  } else if (leafletRef.value) {
    const instance = (leafletRef.value as any).getMapInstance?.()
    if (instance) {
      instance.setView([center.lat, center.lng], zoom)
    }
  }
}

// 切换地图层
function switchLayer(layerId: string) {
  // 在切换前保存当前视角
  const currentState = getCurrentViewState()
  if (currentState.center && currentState.zoom !== null) {
    savedViewState.value = currentState
  }

  currentLayerId.value = layerId

  // 保存到本地存储
  saveLocalMapPreference(layerId)

  // 等待新地图初始化后恢复视角
  nextTick(() => {
    setTimeout(() => {
      if (savedViewState.value.center && savedViewState.value.zoom !== null) {
        setMapViewState(savedViewState.value.center, savedViewState.value.zoom)
      }
    }, 300)  // 给地图组件一些初始化时间
  })
}

// 处理下拉选择变化
function handleLayerChange(layerId: string) {
  switchLayer(layerId)
}

// 切换全屏
function toggleFullscreen() {
  const container = document.querySelector('.universal-map-container') as HTMLElement
  if (!document.fullscreenElement) {
    container?.requestFullscreen()
  } else {
    document.exitFullscreen()
  }
}

// 将所有轨迹居中显示（四周留 5% 空间）
function fitBounds(customPadding?: number) {
  // 如果提供了自定义 padding，使用它；否则根据 mapScale 计算
  const paddingPercent = customPadding ?? (props.mapScale ? calculatePaddingForScale(props.mapScale) : 5)

  if (useAMapEngine.value && amapRef.value?.fitBounds) {
    amapRef.value.fitBounds(paddingPercent)
  } else if (useBMapEngine.value && bmapRef.value?.fitBounds) {
    bmapRef.value.fitBounds(paddingPercent)
  } else if (useTencentEngine.value && tencentRef.value?.fitBounds) {
    tencentRef.value.fitBounds(paddingPercent)
  } else if (leafletRef.value?.fitBounds) {
    leafletRef.value.fitBounds(paddingPercent)
  }
}

// 根据边界框直接设置地图视野（用于聚焦到特定区段）
function fitToBounds(bounds: { minLat: number; maxLat: number; minLon: number; maxLon: number }, paddingPercent: number = 15) {
  if (useAMapEngine.value && (amapRef.value as any)?.fitToBounds) {
    (amapRef.value as any).fitToBounds(bounds, paddingPercent)
  } else if (useBMapEngine.value && (bmapRef.value as any)?.fitToBounds) {
    (bmapRef.value as any).fitToBounds(bounds, paddingPercent)
  } else if (useTencentEngine.value && (tencentRef.value as any)?.fitToBounds) {
    (tencentRef.value as any).fitToBounds(bounds, paddingPercent)
  } else if (leafletRef.value && (leafletRef.value as any)?.fitToBounds) {
    (leafletRef.value as any).fitToBounds(bounds, paddingPercent)
  }
}

// 根据缩放比例计算 padding，使缩放后四周留 10% 空间
function calculatePaddingForScale(scale: number): number {
  // scale: 100-200（即 1.0 - 2.0）
  // CSS transform: scale(scale/100) 会放大 wrapper，用户只看到 wrapper 中心的 viewport 区域
  //
  // 公式推导（不依赖 aspectRatio，横竖屏统一）：
  //   wrapper 实际尺寸 = viewportW × (scale/100) × viewportH × (scale/100)
  //   用户可见区域 = viewportW × viewportH（wrapper 的中心部分）
  //   可见区域占 wrapper 比例 = 1 / (scale/100)²
  //
  //   目标：缩放后，用户可见区域内轨迹占 80%，四周各留 10%
  //   所以：wrapper 内，轨迹应占 = 1/scale² × 80% = 80/scale² %
  //   wrapper 内，每边 padding = (100% - 80/scale²) / 2 = 50(1 - 0.8/scale²)%
  //
  // 简化公式：padding = 50 - 40/scale² × 100 = 50 - 4000/scale²
  //
  // 示例：
  //   scale=100: padding = 50 - 4000/10000 = 10%
  //   scale=150: padding = 50 - 4000/22500 = 32.2%
  //   scale=200: padding = 50 - 4000/40000 = 40%
  const viewportW = window.innerWidth || 1920
  const viewportH = window.innerHeight || 1080
  const maxDim = Math.max(viewportW, viewportH)

  // 简化公式：让 wrapper 中内容占 80/scale²，这样缩放后用户可见中内容占 80%
  // padding = (100 - 80/scale²) / 2
  // scale=100: padding = (100 - 80) / 2 = 10%
  // scale=150: padding = (100 - 80/2.25) / 2 ≈ 32%
  // scale=200: padding = (100 - 80/4) / 2 = 40%
  const scaleRatio = scale / 100
  const contentPercent = 80 / (scaleRatio * scaleRatio)
  const padding = (100 - contentPercent) / 2

  // 验证计算（wrapper 尺寸是 CSS scale 后的）
  const wrapperW = viewportW * scaleRatio
  const wrapperH = viewportH * scaleRatio
  const paddingW = Math.round(wrapperW * (padding / 100))
  const paddingH = Math.round(wrapperH * (padding / 100))
  const contentW = wrapperW - paddingW * 2
  const contentH = wrapperH - paddingH * 2
  const scaleX = viewportW / contentW
  const scaleY = viewportH / contentH

  console.log('[UniversalMap] padding:', {
    scale: scale + '%',
    viewport: `${viewportW}x${viewportH}`,
    '屏幕方向': viewportW > viewportH ? '横' : '竖',
    padding: padding.toFixed(1) + '%',
    contentW: contentW.toFixed(0),
    contentH: contentH.toFixed(0)
  })
  return padding
}

// 清除路径段高亮
function clearSegmentHighlight() {
  emit('clear-segment-highlight')
}

// 处理地图点悬浮事件
function handlePointHover(point: Point | null, pointIndex: number) {
  emit('point-hover', point, pointIndex)
}

// 处理轨迹悬浮事件
function handleTrackHover(trackId: number | null) {
  emit('track-hover', trackId)
}

// 处理轨迹点击事件（用于跳转到详情页）
function handleTrackClick(trackId: number) {
  emit('track-click', trackId)
}

// 处理地图点击事件（用于添加控制点）
function handleMapClick(lng: number, lat: number) {
  emit('map-click', lng, lat)
}

// 高亮指定点（由图表触发）
function highlightPoint(index: number) {
  if (useAMapEngine.value && amapRef.value?.highlightPoint) {
    amapRef.value.highlightPoint(index)
  } else if (useBMapEngine.value && bmapRef.value?.highlightPoint) {
    bmapRef.value.highlightPoint(index)
  } else if (useTencentEngine.value && tencentRef.value?.highlightPoint) {
    tencentRef.value.highlightPoint(index)
  } else if (leafletRef.value?.highlightPoint) {
    // Leaflet 引擎也支持
    leafletRef.value.highlightPoint(index)
  }
}

// 隐藏标记（由图表鼠标离开触发）
function hideMarker() {
  if (useAMapEngine.value && amapRef.value?.hideMarker) {
    amapRef.value.hideMarker()
  } else if (useBMapEngine.value && bmapRef.value?.hideMarker) {
    bmapRef.value.hideMarker()
  } else if (useTencentEngine.value && tencentRef.value?.hideMarker) {
    tencentRef.value.hideMarker()
  } else if (leafletRef.value?.hideMarker) {
    leafletRef.value.hideMarker()
  }
}

// 调整地图大小（用于响应式布局）
function resize() {
  if (useAMapEngine.value && amapRef.value?.resize) {
    amapRef.value.resize()
  } else if (useBMapEngine.value && bmapRef.value?.resize) {
    bmapRef.value.resize()
  } else if (useTencentEngine.value && tencentRef.value?.resize) {
    tencentRef.value.resize()
  } else if (leafletRef.value?.resize) {
    leafletRef.value.resize()
  }
}

onMounted(async () => {
  // 等待配置加载
  if (!configStore.config) {
    await configStore.fetchConfig()
  }

  // 获取所有可用的地图层 ID
  const availableLayerIds = configStore.getMapLayers().map(layer => layer.id)

  // 确定默认地图层（系统默认或 prop 指定的）
  const defaultLayer = props.defaultLayerId || configStore.getMapProvider()

  // 使用本地偏好（如果存在且可用），否则使用默认值
  currentLayerId.value = getEffectiveMapLayer(availableLayerIds, defaultLayer)

  // 启动时间刷新定时器
  if (props.liveUpdateTime) {
    updateTimer = window.setInterval(() => {
      timeRefreshKey.value++
    }, UPDATE_INTERVAL)
  }
})

onUnmounted(() => {
  // 清理定时器
  if (updateTimer) {
    clearInterval(updateTimer)
    updateTimer = null
  }
})

// 监听 currentLayerId 变化
watch(currentLayerId, () => {
  // 图层切换时重新渲染
})

// 监听 defaultLayerId prop 变化
watch(() => props.defaultLayerId, (newVal) => {
  if (newVal) {
    currentLayerId.value = newVal
    // 保存到本地存储
    saveLocalMapPreference(newVal)
  }
})

// 监听 liveUpdateTime 变化，启动或停止定时器
watch(() => props.liveUpdateTime, (newVal) => {
  // 清理旧定时器
  if (updateTimer) {
    clearInterval(updateTimer)
    updateTimer = null
  }
  // 如果有新的时间，启动定时器
  if (newVal) {
    updateTimer = window.setInterval(() => {
      timeRefreshKey.value++
    }, UPDATE_INTERVAL)
  }
})

// 监听 customOverlays 变化（用于调试绘制路径模式）
watch(() => props.customOverlays, (newVal) => {
  console.log('[UniversalMap] customOverlays prop 变化:', newVal?.length || 0, '个覆盖层')
}, { deep: true })

// 暴露方法给父组件
defineExpose({
  highlightPoint,
  hideMarker,
  resize,
  fitBounds,
  fitToBounds,
  getCurrentLayerId: () => currentLayerId.value,
  getMapElement: () => {
    if (useAMapEngine.value && amapRef.value) {
      return (amapRef.value as any).getMapElement?.() || null
    }
    if (useBMapEngine.value && bmapRef.value) {
      return (bmapRef.value as any).getMapElement?.() || null
    }
    if (useTencentEngine.value && tencentRef.value) {
      return (tencentRef.value as any).getMapElement?.() || null
    }
    if (leafletRef.value) {
      return (leafletRef.value as any).getMapElement?.() || null
    }
    return null
  },
  /**
   * 捕获地图截图
   * 优先使用地图 SDK 的截图 API，否则返回 null
   */
  async captureMap(): Promise<string | null> {
    if (useAMapEngine.value && amapRef.value) {
      return await (amapRef.value as any).captureMap?.() || null
    }
    if (useBMapEngine.value && bmapRef.value) {
      return await (bmapRef.value as any).captureMap?.() || null
    }
    if (useTencentEngine.value && tencentRef.value) {
      return await (tencentRef.value as any).captureMap?.() || null
    }
    // Leaflet 返回 null，需要使用 html2canvas
    return null
  },
})
</script>

<style scoped>
.universal-map-container {
  width: 100%;
  height: 100%;
  position: relative;
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

.desktop-layer-selector {
  display: flex;
}

.mobile-layer-selector {
  display: none;
  width: 100px;
}

.live-update-time-btn {
  background-color: #67c23a;
  color: white;
  border: none;
  pointer-events: none;
  font-size: 12px;
  padding: 4px 8px;
  height: auto;
  flex-shrink: 0;
}

.view-details-btn {
  flex-shrink: 0;
  padding: 0;
  height: 24px;
}

.view-details-link {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  width: 100%;
  height: 100%;
  padding: 5px 12px;
  color: inherit;
  text-decoration: none;
  box-sizing: border-box;
}

.view-details-link:hover {
  text-decoration: none;
}

@media (max-width: 1366px) {
  .desktop-layer-selector {
    display: none;
  }

  .mobile-layer-selector {
    display: block;
  }

  .fit-bounds-btn,
  .fullscreen-btn,
  .clear-highlight-btn {
    flex-shrink: 0;
  }
}
</style>
