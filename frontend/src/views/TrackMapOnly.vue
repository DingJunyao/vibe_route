<template>
  <div class="map-only-page">
    <div v-if="loading" class="map-only-loading">加载中...</div>
    <div v-else-if="error" class="map-only-error">{{ error }}</div>
    <div
      v-else
      class="map-wrapper-container"
      :style="{ transform: `scale(${mapScale / 100})`, transformOrigin: 'center center' }"
    >
      <UniversalMap
        v-if="track && points.length > 0"
        ref="mapRef"
        :key="provider"
        :tracks="trackData"
        :mode="'detail'"
        :default-layer-id="provider"
        :map-scale="mapScale"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import { type Track, type TrackPoint } from '@/api/track'
import { useConfigStore } from '@/stores/config'
import UniversalMap from '@/components/map/UniversalMap.vue'

const route = useRoute()
const configStore = useConfigStore()

const track = ref<Track | null>(null)
const points = ref<TrackPoint[]>([])
const loading = ref(true)
const error = ref('')
const mapRef = ref()

// 从 URL 参数获取配置
const provider = ref<string>((route.query.provider as string) || configStore.defaultMapLayer || 'osm')
const posterSecret = ref<string>((route.query.secret as string) || '')
const mapScale = ref<number>(parseInt(route.query.map_scale as string) || 100)

console.log('[MapOnly]', { provider: provider.value, mapScale: mapScale.value })

// 转换为 UniversalMap 需要的格式
const trackData = computed(() => {
  if (!track.value || points.value.length === 0) return []
  return [{
    ...track.value,
    points: points.value,
  }]
})

// 加载数据（使用公开 API）
async function loadData() {
  try {
    const trackId = parseInt(route.params.id as string)
    if (isNaN(trackId)) {
      throw new Error('无效的轨迹 ID')
    }

    // 如果没有提供 secret，使用默认值
    if (!posterSecret.value) {
      posterSecret.value = 'vibe-route-poster-secret'
    }

    // 使用公开 API（带 secret 验证）
    const [trackRes, pointsRes] = await Promise.all([
      axios.get(`/api/tracks/${trackId}/public?secret=${posterSecret.value}`),
      axios.get(`/api/tracks/${trackId}/points/public?secret=${posterSecret.value}`),
    ])

    track.value = trackRes.data
    points.value = pointsRes.data.points

    // 确保配置已加载，以便验证 provider 是否有效
    await nextTick()

    // 如果没有指定 provider，使用默认地图
    if (!provider.value) {
      // 检查请求的 provider 是否在已启用的地图列表中
      const enabledLayers = configStore.getMapLayers().filter((l: any) => l.enabled)
      const providerValid = enabledLayers.some((l: any) => l.id === provider.value)

      if (!providerValid && enabledLayers.length > 0) {
        // 使用第一个启用的图层
        provider.value = enabledLayers[0].id
      }
    }

    // 设置 loading 为 false，让地图组件渲染
    loading.value = false

    await nextTick()

    // 等待地图组件完全挂载和渲染
    await new Promise(resolve => setTimeout(resolve, 2000))

    // 调用地图的 fitBounds 方法，使轨迹居中显示（四周留空间）
    if (mapRef.value?.fitBounds) {
      mapRef.value.fitBounds()
    }

    // 再等待地图调整完成
    await new Promise(resolve => setTimeout(resolve, 2000))

    // 通知 Playwright 地图已准备就绪
    ;(window as any).mapReady = true
    console.log('[MapOnly] 就绪', { provider: provider.value, mapScale: mapScale.value })
  } catch (err: any) {
    console.error('[MapOnly] 加载轨迹失败:', err)
    error.value = err.response?.data?.detail || err.message || '加载失败'
    loading.value = false
  }
}

onMounted(async () => {
  // 确保配置已加载
  if (!configStore.configLoaded) {
    await configStore.fetchConfig()
  }

  await loadData()
})
</script>

<style scoped>
.map-only-page {
  width: 100vw;
  height: 100vh;
  margin: 0;
  padding: 0;
  overflow: hidden;
  background: #e5e5e5;
  display: flex;
  align-items: center;
  justify-content: center;
}

.map-wrapper-container {
  /* 容器大小设置为原始视口大小 */
  width: 100vw;
  height: 100vh;
  /* 缩放将通过 transform: scale() 应用 */
  transition: transform 0.3s ease;
}

.map-only-loading,
.map-only-error {
  width: 100vw;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  color: #666;
}

.map-only-error {
  color: #f56c6c;
}

/* 隐藏地图控制按钮，仅用于截图 */
:deep(.map-controls) {
  display: none !important;
}

/* 隐藏地图原生缩放控件 */
:deep(.amap-controls),
:deep(.amap-control),
:deep(.BML_SCALE),
:deep(.BMap_zl),
:deep(.BMapBtn),
:deep(.BMap_noprint),
:deep(.leaflet-control-zoom),
:deep(.leaflet-control-attribution),
:deep(.tdt-zoom),
:deep(.tdt-control),
:deep(.tmap-zoom-control) {
  display: none !important;
}

/* 确保地图填满容器 */
:deep(.map-wrapper),
:deep(.map-container) {
  width: 100vw;
  height: 100vh;
}
</style>
