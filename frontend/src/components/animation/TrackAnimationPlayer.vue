<!-- frontend/src/components/animation/TrackAnimationPlayer.vue -->
<template>
  <div v-if="canPlay && animationStore.showControls" class="track-animation-player">
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
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useAnimationStore } from '@/stores/animation'
import { useAnimationMap } from '@/composables/animation/useAnimationMap'
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
const { setMarkerPosition, setPassedSegment, setCameraToMarker, setAnimationPlaying, fitTrackWithPadding } = useAnimationMap()

// 状态
const isInitialized = ref(false)
const animationFrameId = ref<number | null>(null)
const lastTimestamp = ref(0)
const lastUpdateTime = ref(0)  // 上次更新地图的时间
const showExportDialog = ref(false)
const hudHeight = ref(0)

// 地图更新节流：每帧最多更新一次
const UPDATE_THROTTLE_MS = 33  // 约30fps

// 计算属性
const duration = computed(() => props.config.duration)
const points = computed(() => props.config.trackPoints)

const canPlay = computed(() => {
  const result = checkCanPlay(points.value).canPlay
  console.log('[TrackAnimationPlayer] canPlay computed:', result, 'points.length:', points.value.length)
  return result
})

// 监听 canPlay 和 showControls 变化（调试用）
watch([canPlay, () => animationStore.showControls], ([playable, showControls]) => {
  console.log('[TrackAnimationPlayer] canPlay & showControls changed:', { playable, showControls })
  console.log('[TrackAnimationPlayer] Component will render:', playable && showControls)
})

// 计算绝对时间戳（用于 findPointIndexByTime）
const absoluteCurrentTime = computed(() => {
  const startTimeMs = new Date(props.config.startTime).getTime()
  return startTimeMs + animationStore.currentTime
})

// 获取当前地图提供商的坐标类型
const isGCJ02Provider = computed(() => {
  // AMap 引擎、Tencent 引擎、高德 Leaflet、腾讯 Leaflet 使用 GCJ02 坐标
  const result = props.mapProvider === 'amap' || props.mapProvider === 'tencent'
  console.log('[TrackAnimationPlayer] isGCJ02Provider:', result, 'mapProvider:', props.mapProvider)
  return result
})
const isBD09Provider = computed(() => {
  const result = props.mapProvider === 'baidu'
  console.log('[TrackAnimationPlayer] isBD09Provider:', result, 'mapProvider:', props.mapProvider)
  return result
})

watch(() => props.mapProvider, (newProvider) => {
  console.log('[TrackAnimationPlayer] mapProvider changed to:', newProvider)
}, { immediate: true })

// 事件处理
const emit = defineEmits<{
  (e: 'position-changed', position: { lat: number; lng: number; bearing: number; speed: number | null; elevation: number | null; time: string | null }): void
}>()

// 缓存上次计算的位置
let lastCalculatedPosition: ReturnType<typeof interpolatePosition> | null = null

// 计算当前位置并 emit 给父组件
function updateAndEmitPosition() {
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
      lastCalculatedPosition = pos
      console.log('[TrackAnimationPlayer] Emitting position-changed (end of track):', pos)
      emit('position-changed', pos)
    }
  }

  const point = points.value[index]
  const nextPoint = points.value[index + 1]

  if (!point || !nextPoint) {
    console.log('[TrackAnimationPlayer] No point or nextPoint, index:', index)
    return
  }

  const result = interpolatePosition(point, nextPoint, progress, isGCJ02Provider.value, isBD09Provider.value)
  lastCalculatedPosition = result
  console.log('[TrackAnimationPlayer] Emitting position-changed (interpolated):', result)
  emit('position-changed', result)
}

// 获取上次计算的位置
updateAndEmitPosition.getLastPosition = () => lastCalculatedPosition

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
        () => {}
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

// HUD 高度变化处理
function handleHeightChanged(height: number) {
  hudHeight.value = height
  // 桌面端需要调整地图视野以避免 HUD 遮挡
  // 移动端 HUD 固定在屏幕底部，但切换到全轨迹画面时需要调整视野
  if (animationStore.cameraMode === 'full') {
    if (isMobile()) {
      // 移动端：使用地图加载时的默认缩放逻辑（5% padding）
      fitTrackWithPadding(5)
    } else {
      // 桌面端：添加底部 padding 避免遮挡
      const padding = height + 20
      fitTrackWithPadding(padding)
    }
  }
}

// 检测是否为移动端
function isMobile(): boolean {
  return window.innerWidth <= 1366
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
  console.log('[TrackAnimationPlayer] updateAnimation() called, isPlaying:', animationStore.isPlaying, 'currentTime:', animationStore.currentTime)

  updateAndEmitPosition()

  const now = Date.now()
  // 节流更新：避免过于频繁地调用地图适配器
  if (now - lastUpdateTime.value < UPDATE_THROTTLE_MS) {
    console.log('[TrackAnimationPlayer] updateAnimation() throttled')
    return
  }

  lastUpdateTime.value = now

  // 更新地图标记位置和双色轨迹（通过 currentPosition 计算）
  const pos = updateAndEmitPosition.getLastPosition?.() ?? null
  console.log('[TrackAnimationPlayer] Position:', pos)

  if (!pos) {
    console.log('[TrackAnimationPlayer] No position, skipping update')
    return
  }

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
  console.log('[TrackAnimationPlayer] onMounted called')
  console.log('[TrackAnimationPlayer] canPlay:', canPlay.value)
  console.log('[TrackAnimationPlayer] showControls:', animationStore.showControls)
  isInitialized.value = true
  animationFrameId.value = requestAnimationFrame(animationLoop)
})

onUnmounted(() => {
  console.log('[TrackAnimationPlayer] onUnmounted called')
  if (animationFrameId.value) {
    cancelAnimationFrame(animationFrameId.value)
  }
})

// 监听播放状态变化
watch(() => animationStore.isPlaying, (isPlaying) => {
  lastTimestamp.value = 0
  // 通知地图组件更新动画播放状态，避免双色轨迹闪烁
  setAnimationPlaying(isPlaying)
  // 确保标记在状态变化时立即更新
  updateAnimation()
})

// 监听时间变化，确保 seek 操作时标记更新
watch(() => animationStore.currentTime, () => {
  // 在非播放状态下（如 seek 操作），需要手动触发更新
  if (!animationStore.isPlaying) {
    updateAnimation()
  }
})

// 监听相机模式变化，刷新轨迹线
watch(() => animationStore.cameraMode, (newMode) => {
  // 相机模式切换时，如果是播放状态，重新绘制轨迹线
  if (animationStore.isPlaying) {
    setAnimationPlaying(true)
  }
  // 切换到全轨迹画面时，调整地图视野
  if (newMode === 'full') {
    if (isMobile()) {
      // 移动端：使用地图加载时的默认缩放逻辑（5% padding）
      fitTrackWithPadding(5)
    } else if (hudHeight.value > 0) {
      // 桌面端：添加底部 padding 避免遮挡
      const padding = hudHeight.value + 20
      fitTrackWithPadding(padding)
    }
  }
})

// 监听 HUD 高度变化
watch(hudHeight, (newHeight) => {
  // 如果是全轨迹画面模式，调整地图视野
  if (animationStore.cameraMode === 'full' && newHeight > 0) {
    if (isMobile()) {
      // 移动端：使用地图加载时的默认缩放逻辑（5% padding）
      fitTrackWithPadding(5)
    } else {
      // 桌面端：添加底部 padding 避免遮挡
      const padding = newHeight + 20
      fitTrackWithPadding(padding)
    }
  }
})

// 监听地图切换，全轨迹模式下重新调整视野
watch(() => props.mapProvider, () => {
  // 如果是全轨迹画面模式，重新调整地图视野
  if (animationStore.cameraMode === 'full') {
    // 延迟执行，等待地图初始化完成
    nextTick(() => {
      setTimeout(() => {
        if (isMobile()) {
          // 移动端：使用地图加载时的默认缩放逻辑（5% padding）
          fitTrackWithPadding(5)
        } else if (hudHeight.value > 0) {
          // 桌面端：添加底部 padding 避免遮挡
          const padding = hudHeight.value + 20
          fitTrackWithPadding(padding)
        }
      }, 500)
    })
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
</style>
