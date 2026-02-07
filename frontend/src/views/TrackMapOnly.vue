<template>
  <div
    class="map-only-page"
    :style="useExplicitSize ? { width: `${targetWidth}px`, height: `${targetHeight}px` } : {}"
  >
    <div v-if="loading" class="map-only-loading">加载中...</div>
    <div v-else-if="error" class="map-only-error">{{ error }}</div>
    <div
      v-else
      class="map-wrapper-container"
      :style="{
        transform: `scale(${mapScale / 100})`,
        transformOrigin: 'center center',
        ...(useExplicitSize ? { width: `${targetWidth}px`, height: `${targetHeight}px` } : {})
      }"
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
// 获取显式指定的尺寸（用于 iframe 预览/导出）
const targetWidth = ref<number>(parseInt(route.query.width as string) || 0)
const targetHeight = ref<number>(parseInt(route.query.height as string) || 0)

// 是否使用显式尺寸（iframe 模式）
const useExplicitSize = computed(() => targetWidth.value > 0 && targetHeight.value > 0)

console.log('[MapOnly]', {
  provider: provider.value,
  mapScale: mapScale.value,
  targetSize: useExplicitSize.value ? `${targetWidth.value}x${targetHeight.value}` : 'auto'
})

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

    // 等待缩放动画完成
    // 基础等待时间 + 根据缩放比例增加额外时间
    const baseWait = 2000
    const scaleWait = (mapScale.value - 100) * 30  // 每 1% 缩放增加 30ms
    const totalWait = baseWait + scaleWait

    console.log(`[MapOnly] 等待缩放完成: ${totalWait}ms (scale: ${mapScale.value}%)`)
    await new Promise(resolve => setTimeout(resolve, totalWait))

    // 额外等待，确保所有动画和瓦片加载完成
    await new Promise(resolve => setTimeout(resolve, 1000))

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

  // 设置标志：海报生成模式，使用 Canvas 渲染（html2canvas 兼容性更好）
  ;(window as any).__posterMode = true

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
  /* 确保没有额外的样式干扰 */
  box-sizing: border-box;
  position: relative;
}

/* 全局重置，确保 body 没有默认 margin */
:deep(body) {
  margin: 0;
  padding: 0;
  overflow: hidden;
}

:deep(html) {
  margin: 0;
  padding: 0;
  overflow: hidden;
}

.map-wrapper-container {
  /* 容器大小设置为原始视口大小 */
  width: 100vw;
  height: 100vh;
  /* 缩放将通过 transform: scale() 应用 */
  transition: transform 0.3s ease;
}

/* 显式尺寸模式（iframe 预览/导出）：使用固定尺寸而非 vw/vh */
.use-explicit-size .map-wrapper-container {
  width: 100%;
  height: 100%;
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

/* 隐藏百度地图 logo（避免 CORS 问题） */
:deep(.BMap_cpyCtrl),
:deep(.anchorBL),
:deep(.BMap_scaleCtrl),
:deep(.BMap_cpyCtrl) {
  display: none !important;
}

/* 隐藏高德地图 logo（可选） */
:deep(.amap-logo) {
  display: none !important;
}

/* 确保地图填满容器 */
:deep(.map-wrapper),
:deep(.map-container) {
  width: 100vw;
  height: 100vh;
}
</style>
