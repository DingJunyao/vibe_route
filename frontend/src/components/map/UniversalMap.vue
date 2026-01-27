<template>
  <div class="universal-map-container">
    <!-- 腾讯地图引擎 -->
    <TencentMap
      v-if="useTencentEngine"
      ref="tencentRef"
      :tracks="tracks"
      :highlight-track-id="highlightTrackId"
      :highlight-segment="highlightSegment"
      :mode="mode"
      @point-hover="handlePointHover"
      @track-hover="handleTrackHover"
      @track-click="handleTrackClick"
    />
    <!-- 高德地图引擎 -->
    <AMap
      v-else-if="useAMapEngine"
      ref="amapRef"
      :tracks="tracks"
      :highlight-track-id="highlightTrackId"
      :highlight-segment="highlightSegment"
      :mode="mode"
      @point-hover="handlePointHover"
      @track-hover="handleTrackHover"
      @track-click="handleTrackClick"
    />
    <!-- 百度地图引擎 -->
    <BMap
      v-else-if="useBMapEngine"
      ref="bmapRef"
      :tracks="tracks"
      :highlight-track-id="highlightTrackId"
      :highlight-segment="highlightSegment"
      :mode="mode"
      @point-hover="handlePointHover"
      @track-hover="handleTrackHover"
      @track-click="handleTrackClick"
    />
    <!-- Leaflet 地图引擎 -->
    <LeafletMap
      v-else
      ref="leafletRef"
      :tracks="tracks"
      :highlight-track-id="highlightTrackId"
      :highlight-segment="highlightSegment"
      :default-layer-id="currentLayerId"
      :hide-layer-selector="true"
      :mode="mode"
      @point-hover="handlePointHover"
      @track-hover="handleTrackHover"
      @track-click="handleTrackClick"
    />
    <!-- 通用地图选择器 -->
    <div class="map-controls">
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
import { computed, onMounted, ref, watch } from 'vue'
import { useConfigStore } from '@/stores/config'
import { Close, FullScreen } from '@element-plus/icons-vue'
import LeafletMap from './LeafletMap.vue'
import AMap from './AMap.vue'
import BMap from './BMap.vue'
import TencentMap from './TencentMap.vue'
import type { MapLayerConfig } from '@/api/admin'

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

// 定义 emit 事件
const emit = defineEmits<{
  (e: 'point-hover', point: Point | null, pointIndex: number): void
  (e: 'track-hover', trackId: number | null): void
  (e: 'track-click', trackId: number): void
  (e: 'clear-segment-highlight'): void
}>()

const configStore = useConfigStore()
const amapRef = ref()
const bmapRef = ref()
const tencentRef = ref()
const leafletRef = ref()

// 当前选择的地图层 ID
const currentLayerId = ref<string>('')

// 判断是否使用高德地图引擎
const useAMapEngine = computed(() => {
  const layerId = currentLayerId.value
  if (layerId !== 'amap' && !layerId.startsWith('amap')) return false
  const amapConfig = configStore.getMapLayerById('amap')
  return !!(amapConfig?.api_key)
})

// 判断是否使用百度地图引擎
const useBMapEngine = computed(() => {
  const layerId = currentLayerId.value
  if (layerId !== 'baidu' && !layerId.startsWith('baidu')) return false
  const baiduConfig = configStore.getMapLayerById('baidu')
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

// 切换地图层
function switchLayer(layerId: string) {
  currentLayerId.value = layerId
  // 注意：我们不需要更新 configStore，因为 map_layers 是存储在数据库中的配置
  // 我们只需要在本地切换即可
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
function fitBounds() {
  if (useAMapEngine.value && amapRef.value?.fitBounds) {
    amapRef.value.fitBounds()
  } else if (useBMapEngine.value && bmapRef.value?.fitBounds) {
    bmapRef.value.fitBounds()
  } else if (useTencentEngine.value && tencentRef.value?.fitBounds) {
    tencentRef.value.fitBounds()
  } else if (leafletRef.value?.fitBounds) {
    leafletRef.value.fitBounds()
  }
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
  // 初始化当前图层
  currentLayerId.value = props.defaultLayerId || configStore.getMapProvider()
})

// 监听 currentLayerId 变化
watch(currentLayerId, () => {
  // 图层切换时重新渲染
})

// 监听 defaultLayerId prop 变化
watch(() => props.defaultLayerId, (newVal) => {
  if (newVal) {
    currentLayerId.value = newVal
  }
})

// 暴露方法给父组件
defineExpose({
  highlightPoint,
  hideMarker,
  resize,
  fitBounds,
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
