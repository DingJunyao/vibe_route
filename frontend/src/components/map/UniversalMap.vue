<template>
  <div class="universal-map-container">
    <!-- 高德地图引擎 -->
    <AMap
      v-if="useAMapEngine"
      ref="amapRef"
      :tracks="tracks"
      :highlight-track-id="highlightTrackId"
    />
    <!-- Leaflet 地图引擎 -->
    <LeafletMap
      v-else
      ref="leafletRef"
      :tracks="tracks"
      :highlight-track-id="highlightTrackId"
      :default-layer-id="currentLayerId"
      :hide-layer-selector="true"
    />
    <!-- 通用地图选择器 -->
    <div class="map-controls">
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
import { FullScreen } from '@element-plus/icons-vue'
import LeafletMap from './LeafletMap.vue'
import AMap from './AMap.vue'
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
const amapRef = ref()
const leafletRef = ref()

// 当前选择的地图层 ID
const currentLayerId = ref<string>('')

// 已启用的地图层列表
const enabledMapLayers = computed<MapLayerConfig[]>(() => {
  const allLayers = configStore.getMapLayers()
  return allLayers.filter((l: MapLayerConfig) => l.enabled).sort((a, b) => a.order - b.order)
})

// 判断是否使用高德地图引擎
// 只有当选中高德地图且配置了 API key 时才使用 AMap 引擎，否则使用 Leaflet 引擎
const useAMapEngine = computed(() => {
  const layerId = currentLayerId.value
  if (layerId !== 'amap' && !layerId.startsWith('amap')) return false
  const amapConfig = configStore.getMapLayerById('amap')
  return !!(amapConfig?.api_key) // 只有配置了 API key 才使用 AMap 引擎
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

onMounted(async () => {
  // 等待配置加载
  if (!configStore.config) {
    await configStore.fetchConfig()
  }
  // 初始化当前图层
  currentLayerId.value = props.defaultLayerId || configStore.getMapProvider()
})

// 监听 defaultLayerId prop 变化
watch(() => props.defaultLayerId, (newVal) => {
  if (newVal) {
    currentLayerId.value = newVal
  }
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
</style>
