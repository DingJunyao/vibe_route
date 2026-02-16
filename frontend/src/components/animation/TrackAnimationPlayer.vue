<!-- frontend/src/components/animation/TrackAnimationPlayer.vue -->
<template>
  <div v-if="canPlay && animationStore.showControls" class="track-animation-player">
    <!-- HUD 控制面板 -->
    <AnimationHUD
      :is-playing="animationStore.isPlaying"
      :current-time="animationStore.currentTime"
      :total-duration="duration"
      :playback-speed="animationStore.playbackSpeed"
      :camera-mode="animationStore.cameraMode"
      :orientation-mode="animationStore.orientationMode"
      :show-info-panel="animationStore.showInfoPanel"
      :marker-style="animationStore.markerStyle"
      @toggle-play="handleTogglePlay"
      @seek="handleSeek"
      @set-speed="handleSetSpeed"
      @toggle-camera-mode="handleToggleCameraMode"
      @toggle-orientation-mode="handleToggleOrientationMode"
      @toggle-info-panel="handleToggleInfoPanel"
      @cycle-marker-style="handleCycleMarkerStyle"
      @export="handleExport"
    />

    <!-- 信息浮层 -->
    <div
      v-if="animationStore.showInfoPanel && currentPosition"
      class="info-panel"
      :style="infoPanelStyle"
    >
      <div class="info-time">{{ formatTime(currentPosition.time) }}</div>
      <div class="info-speed">{{ formatSpeed(currentPosition.speed) }}</div>
      <div class="info-elevation">{{ formatElevation(currentPosition.elevation) }}</div>
    </div>

    <!-- 导出对话框 -->
    <AnimationExportDialog
      v-model="showExportDialog"
      :track-id="trackId"
      :map-provider="mapProvider"
      @export="handleExportVideo"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useAnimationStore } from '@/stores/animation'
import { useAnimationMap } from '@/composables/animation/useAnimationMap'
import AnimationHUD from './AnimationHUD.vue'
import AnimationExportDialog from './AnimationExportDialog.vue'
import {
  calculateDuration,
  findPointIndexByTime,
  interpolatePosition,
  formatAnimationTime,
  canPlayAnimation as checkCanPlay,
  type TrackPoint,
  type MarkerPosition,
} from '@/utils/animationUtils'
import { exportWithPlaywright, downloadFile, generateExportFilename, requiresBackendExport, checkExportPrerequisites } from '@/utils/animation/videoExport'
import { ElMessage } from 'element-plus'
import type { AnimationConfig, ExportConfig } from '@/types/animation'

interface Props {
  config: AnimationConfig
  trackId: number
  mapProvider: string
}

const props = defineProps<Props>()

const animationStore = useAnimationStore()
const { setMarkerPosition, setPassedSegment, setCameraToMarker, setAnimationPlaying } = useAnimationMap()

// 状态
const isInitialized = ref(false)
const animationFrameId = ref<number | null>(null)
const lastTimestamp = ref(0)
const lastUpdateTime = ref(0)  // 上次更新地图的时间
const showExportDialog = ref(false)

// 地图更新节流：每帧最多更新一次
const UPDATE_THROTTLE_MS = 33  // 约30fps

// 计算属性
const duration = computed(() => props.config.duration)
const points = computed(() => props.config.trackPoints)

const canPlay = computed(() => checkCanPlay(points.value).canPlay)

// 计算绝对时间戳（用于 findPointIndexByTime）
const absoluteCurrentTime = computed(() => {
  const startTimeMs = new Date(props.config.startTime).getTime()
  return startTimeMs + animationStore.currentTime
})

// 获取当前地图提供商的坐标类型
const isGCJ02Provider = computed(() => {
  // AMap 引擎、Tencent 引擎、高德 Leaflet、腾讯 Leaflet 使用 GCJ02 坐标
  return props.mapProvider === 'amap' || props.mapProvider === 'tencent'
})
const isBD09Provider = computed(() => props.mapProvider === 'baidu')

watch(() => props.mapProvider, (newProvider) => {
}, { immediate: true })

const currentPosition = computed<MarkerPosition | null>(() => {
  const { index, progress } = findPointIndexByTime(
    absoluteCurrentTime.value,
    points.value,
    props.config.startTime
  )

  if (index >= points.value.length - 1) {
    // 到达终点
    const lastPoint = points.value[points.value.length - 1]
    if (lastPoint) {
      const pos = {
        lat: isGCJ02Provider.value ? (lastPoint.latitude_gcj02 ?? lastPoint.latitude_wgs84 ?? lastPoint.latitude)
          : isBD09Provider.value ? (lastPoint.latitude_bd09 ?? lastPoint.latitude_wgs84 ?? lastPoint.latitude)
          : (lastPoint.latitude_wgs84 ?? lastPoint.latitude),
        lng: isGCJ02Provider.value ? (lastPoint.longitude_gcj02 ?? lastPoint.longitude_wgs84 ?? lastPoint.longitude)
          : isBD09Provider.value ? (lastPoint.longitude_bd09 ?? lastPoint.longitude_wgs84 ?? lastPoint.longitude)
          : (lastPoint.longitude_wgs84 ?? lastPoint.longitude),
        bearing: lastPoint.bearing ?? 0,
        speed: lastPoint.speed ?? null,
        elevation: lastPoint.elevation ?? null,
        time: lastPoint.time ?? null,
      }
      return pos
    }
  }

  const point = points.value[index]
  const nextPoint = points.value[index + 1]

  if (!point || !nextPoint) {
    return null
  }

  const result = interpolatePosition(point, nextPoint, progress, isGCJ02Provider.value, isBD09Provider.value)
  return result
})

// 信息浮层位置（简化为固定位置）
const infoPanelStyle = computed(() => ({
  top: '10px',
  left: '10px',
}))

// 格式化函数
function formatTime(time: string | null): string {
  if (!time) return '--:--:--'
  return new Date(time).toLocaleTimeString('zh-CN', { hour12: false })
}

function formatSpeed(speed: number | null): string {
  if (speed === null) return '-- km/h'
  return `${(speed * 3.6).toFixed(1)} km/h`
}

function formatElevation(elevation: number | null): string {
  if (elevation === null) return '-- m'
  return `${Math.round(elevation)} m`
}

// 事件处理
function handleTogglePlay() {
  animationStore.togglePlayPause()
}

function handleToggleCameraMode() {
  animationStore.toggleCameraMode()
}

function handleToggleOrientationMode() {
  animationStore.toggleOrientationMode()
}

function handleToggleInfoPanel() {
  animationStore.toggleInfoPanel()
}

function handleCycleMarkerStyle() {
  animationStore.cycleMarkerStyle()
}

function handleSeek(time: number) {
  animationStore.setPlaybackState('currentTime', time)
  updateAnimation()
}

function handleSetSpeed(speed: number) {
  animationStore.setSpeed(speed)
}

function handleExport() {
  showExportDialog.value = true
}

async function handleExportVideo(config: ExportConfig) {
  try {
    // 检查是否需要后端导出
    if (requiresBackendExport(props.mapProvider)) {
      // 使用后端 Playwright 导出
      const downloadUrl = await exportWithPlaywright(
        props.trackId,
        config,
        (progress) => {
          console.log('Export progress:', progress)
        }
      )
      downloadFile(downloadUrl, generateExportFilename(props.trackId, config.format))
      ElMessage.success('导出完成')
    } else {
      // 前端导出（暂时不支持）
      const prerequisites = checkExportPrerequisites()
      if (!prerequisites.canPlay) {
        ElMessage.error(prerequisites.reason)
        return
      }
      ElMessage.warning('前端导出功能开发中，请使用百度地图进行导出')
    }
  } catch (e: any) {
    console.error('Export error:', e)
    ElMessage.error(`导出失败: ${e.message || '未知错误'}`)
  }
}

// 动画循环
function animationLoop(timestamp: number) {
  if (!lastTimestamp.value) {
    lastTimestamp.value = timestamp
  }

  const delta = timestamp - lastTimestamp.value

  if (animationStore.isPlaying && delta > 0) {
    const adjustedDelta = delta * animationStore.playbackSpeed
    const newTime = animationStore.currentTime + adjustedDelta

    if (newTime >= duration.value) {
      // 播放完成
      animationStore.setPlaybackState('currentTime', duration.value)
      animationStore.setPlaybackState('isPlaying', false)
      updateAnimation()
    } else {
      // 直接修改 currentTime
      animationStore.setPlaybackState('currentTime', newTime)
      updateAnimation()
    }
  }

  lastTimestamp.value = timestamp
  animationFrameId.value = requestAnimationFrame(animationLoop)
}

// 更新动画
function updateAnimation() {
  const pos = currentPosition.value
  if (!pos) {
    return
  }

  const now = Date.now()
  // 节流更新：避免过于频繁地调用地图适配器
  if (now - lastUpdateTime.value < UPDATE_THROTTLE_MS) {
    return
  }

  lastUpdateTime.value = now

  // 更新地图标记位置
  setMarkerPosition(pos, animationStore.markerStyle)

  // 更新双色轨迹
  const { index } = findPointIndexByTime(
    absoluteCurrentTime.value,
    points.value,
    props.config.startTime
  )
  setPassedSegment(0, index)

  // 相机跟随模式
  if (animationStore.cameraMode === 'fixed-center') {
    setCameraToMarker(pos)
  }
}

// 生命周期
onMounted(() => {
  isInitialized.value = true
  animationFrameId.value = requestAnimationFrame(animationLoop)
})

onUnmounted(() => {
  if (animationFrameId.value) {
    cancelAnimationFrame(animationFrameId.value)
  }
})

// 监听播放状态变化
watch(() => animationStore.isPlaying, (isPlaying) => {
  lastTimestamp.value = 0
  // 通知地图组件更新动画播放状态，避免双色轨迹闪烁
  setAnimationPlaying(isPlaying)
})

// 监听相机模式变化，刷新轨迹线
watch(() => animationStore.cameraMode, () => {
  // 相机模式切换时，如果是播放状态，重新绘制轨迹线
  if (animationStore.isPlaying) {
    setAnimationPlaying(true)
  }
})

// 监听标记样式变化，更新地图上的标记
watch(() => animationStore.markerStyle, () => {
  const pos = currentPosition.value
  if (pos) {
    setMarkerPosition(pos, animationStore.markerStyle)
  }
})
</script>

<style scoped>
.track-animation-player {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
}

.track-animation-player > * {
  pointer-events: auto;
}

.info-panel {
  position: absolute;
  background: rgba(0, 0, 0, 0.7);
  color: white;
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.5;
  pointer-events: none;
  z-index: 1001;
}

.info-time {
  font-weight: 500;
}

.info-speed,
.info-elevation {
  opacity: 0.9;
}
</style>
