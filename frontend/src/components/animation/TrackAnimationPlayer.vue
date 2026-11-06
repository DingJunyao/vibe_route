<!-- frontend/src/components/animation/TrackAnimationPlayer.vue -->
<template>
  <div v-if="canPlay && animationStore.showControls" class="track-animation-player">
    <!-- 桌面端：HUD 控制面板和信息浮层 -->
    <template v-if="!isMobile">
      <!-- 控制面板（导出模式隐藏，导出视频不包含控制 UI） -->
      <AnimationHUD
        v-if="!exportMode"
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
        @toggle-info-panel="handleToggleInfoPanel"
        @cycle-marker-style="handleCycleMarkerStyle"
        @export="handleExport"
        @height-changed="handleHeightChanged"
      />

      <!-- 桌面端：信息浮层 -->
      <div
        v-if="animationStore.showInfoPanel && currentPosition"
        class="info-panel"
        :style="infoPanelStyle"
      >
        <!-- 导出模式：播放进度、当前时间、剩余时间（时长用 HH:MM:SS 格式化，勿用时间戳格式） -->
        <div v-if="exportMode" class="info-export-progress">
          {{ formatDurationText(animationStore.currentTime) }} / {{ formatDurationText(duration) }}
          · {{ Math.round((animationStore.currentTime / duration) * 100) }}%
          · 剩余 {{ formatDurationText(Math.max(0, duration - animationStore.currentTime)) }}
        </div>
        <div class="info-time">{{ formatTime(currentPosition.time) }}</div>
        <div class="info-speed">{{ formatSpeed(currentPosition.speed) }}</div>
        <div class="info-elevation">{{ formatElevation(currentPosition.elevation) }}</div>
      </div>
    </template>

    <!-- 导出对话框 -->
    <AnimationExportDialog
      ref="exportDialogRef"
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
import { useAnimationMap, getGlobalViewState } from '@/composables/animation/useAnimationMap'
import AnimationHUD from './AnimationHUD.vue'
import AnimationExportDialog from './AnimationExportDialog.vue'
import {
  calculateDuration,
  calculateDistance,
  calculateShortestRotation,
  findPointIndexByTime,
  interpolatePosition,
  formatAnimationTime,
  getFixedCenterZoom,
  canPlayAnimation as checkCanPlay,
  type TrackPoint,
  type MarkerPosition,
} from '@/utils/animationUtils'
import { smoothedCameraAt, cameraHeadingAt, type AnimationCRS } from '@/utils/animation/cameraSmoothing'
import { isChinaRegionPoints } from '@/utils/coordTransform'
import { startExportTask, buildExportConfig } from '@/utils/animation/videoExport'
import type { AnimationConfig, ExportOptions } from '@/types/animation'

interface Props {
  config: AnimationConfig
  trackId: number
  mapProvider: string
  exportMode?: boolean  // 导出模式：强制桌面布局、隐藏控制面板（导出视频仅地图+动画）
}

const props = defineProps<Props>()

const animationStore = useAnimationStore()
const { setMarkerPosition, setPassedSegment, setCameraToMarker, applyMapRotation, setAnimationPlaying, fitTrackWithPadding, waitForMapIdle } = useAnimationMap()

// 状态
const isInitialized = ref(false)
const animationFrameId = ref<number | null>(null)
const lastTimestamp = ref(0)
const lastUpdateTime = ref(0)  // 上次更新地图的时间
const showExportDialog = ref(false)
const exportDialogRef = ref<InstanceType<typeof AnimationExportDialog> | null>(null)
const hudHeight = ref(0)
// 最近一次应用的固定中心自适应缩放（null 表示待应用，模式/地图切换后重置）
let lastFixedCenterZoom: number | null = null

// 地图更新节流：每帧最多更新一次
const UPDATE_THROTTLE_MS = 33  // 约30fps

// 计算属性
const duration = computed(() => props.config.duration)
const points = computed(() => props.config.trackPoints)

const canPlay = computed(() => checkCanPlay(points.value).canPlay)

// 检测是否为移动端（导出模式强制桌面布局）
const isMobile = computed(() => !props.exportMode && window.innerWidth <= 1366)

// 计算绝对时间戳（用于 findPointIndexByTime）
const absoluteCurrentTime = computed(() => {
  const startTimeMs = new Date(props.config.startTime).getTime()
  return startTimeMs + animationStore.currentTime
})

// 获取当前地图提供商的坐标类型
const isGCJ02Provider = computed(() => {
  // 高德/腾讯 SDK、二者 Leaflet 均为 GCJ02。
  // Google 路网底图（roadmap）的中国数据同样是 GCJ02 偏移的（实测：卫星图是 WGS84
  // 真值、路网图是 GCJ02，两者不一致；本项目只配 roadmap 图层），故一并按 GCJ02。
  // 境外 gcj02 == wgs84（转换守卫），无需分支
  return props.mapProvider === 'amap' || props.mapProvider === 'tencent' ||
    props.mapProvider === 'google'
})
const isBD09Provider = computed(() => {
  // 百度口径仅境内轨迹适用：百度海外底图按 WGS84 对齐，
  // 轨迹的 BD09 字段对境外点是套用中国偏移算法的结果（偏差约 1km）
  return props.mapProvider === 'baidu' && isChinaRegionPoints(points.value)
})

// 相机平滑使用的坐标系（与 interpolatePosition 的坐标字段选择一致）
const camCRS = computed<AnimationCRS>(() =>
  isGCJ02Provider.value ? 'gcj02' : isBD09Provider.value ? 'bd09' : 'wgs84'
)

// 最近一次解析出的平滑航向：静止段（前后 4 分钟无位移）保持该航向，避免镜头/标记甩头
let lastCameraHeading: number | null = null
// 最近一次应用的双色轨迹索引（-1 表示待应用；setPassedSegment 每次全量重建两条线，索引未变时跳过）
let lastPassedIndex = -1
// 上次逐帧 seek 的相机状态（亚像素跳帧用：SDK 对微小移动去重会导致 moveend 不触发）
let lastSeekCamera: { lat: number; lng: number; bearing: number; zoom: number | null } | null = null

/**
 * 当前时刻的相机状态（平滑位置 + 平滑航向）。
 * 仅相机与固定中心标记使用；轨迹无有效时间数据时返回 null（回退原始位置/方位角）。
 */
function cameraAtCurrentTime(): { lat: number; lng: number; heading: number | null } | null {
  const pts = points.value
  const cam = smoothedCameraAt(absoluteCurrentTime.value, pts, camCRS.value)
  if (!cam) return null
  const heading = cameraHeadingAt(absoluteCurrentTime.value, pts)
  if (heading !== null) {
    lastCameraHeading = heading
    return { ...cam, heading }
  }
  // 前后 4 分钟均静止：保持上次航向（开局即静止时为 null，回退 pos.bearing）
  return { ...cam, heading: lastCameraHeading }
}

// 轨迹数据变化（加载完成/切换轨迹）时重置相机平滑与跳帧状态
watch(() => props.config.trackPoints, () => {
  lastCameraHeading = null
  lastSeekCamera = null
  lastPassedIndex = -1
})

watch(() => props.mapProvider, () => {}, { immediate: true })

// 事件处理
const emit = defineEmits<{
  (e: 'position-changed', position: { lat: number; lng: number; bearing: number; speed: number | null; elevation: number | null; time: string | null }): void
}>()

// 桌面端：当前位置计算属性
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

// 格式化函数（桌面端信息浮层使用）
function formatTime(time: string | null): string {
  if (!time) return '--:--:--'
  return new Date(time).toLocaleTimeString('zh-CN', { hour12: false })
}

// 毫秒时长 → HH:MM:SS（导出进度行使用，currentTime 是时长而非时间戳）
function formatDurationText(ms: number): string {
  return formatAnimationTime(ms)
}

function formatSpeed(speed: number | null): string {
  if (speed === null) return '-- km/h'
  return `${(speed * 3.6).toFixed(1)} km/h`
}

function formatElevation(elevation: number | null): string {
  if (elevation === null) return '-- m'
  return `${Math.round(elevation)} m`
}

// 移动端：计算当前位置并 emit 给父组件
// 缓存上次计算的位置
let lastCalculatedPosition: ReturnType<typeof interpolatePosition> | null = null

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
      emit('position-changed', pos)
    }
  }

  const point = points.value[index]
  const nextPoint = points.value[index + 1]

  if (!point || !nextPoint) {
    return
  }

  const result = interpolatePosition(point, nextPoint, progress, isGCJ02Provider.value, isBD09Provider.value)
  lastCalculatedPosition = result
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

async function handleExportVideo(options: ExportOptions) {
  // 统一使用后端 Playwright 导出：导出页面与用户预览完全一致，
  // 且不受各引擎前端捕获限制（CORS 污染、DOM 渲染、瓦片跨域等）影响；
  // 提交到录屏任务队列后立即返回，进度与下载在「录屏任务」页进行
  const config = buildExportConfig(options)
  exportDialogRef.value?.startExport()
  try {
    await startExportTask(props.trackId, config)
    exportDialogRef.value?.finishQueued()
  } catch (e: any) {
    console.error('Export error:', e)
    const detail = e?.response?.data?.detail || e?.message || '未知错误'
    exportDialogRef.value?.finishError(String(detail))
  }
}

// HUD 高度变化处理
function handleHeightChanged(height: number) {
  hudHeight.value = height
  // 如果当前是全轨迹画面模式，立即调整地图视野（四周 10% 边距）
  if (animationStore.cameraMode === 'full') {
    fitTrackWithPadding(0)
  }
}

// 导出模式瓦片就绪门控：加载中的 Leaflet 瓦片数（非 Leaflet 引擎恒为 0，不门控）
function pendingTileCount(): number {
  return document.querySelectorAll('.leaflet-tile:not(.leaflet-tile-loaded)').length
}

// 瓦片门控起始时间：持续超过 TILE_GATE_TIMEOUT_MS 后放行推进，
// 防止加载失败（永不进入 loaded 状态）的瓦片把播放永久卡死。
// 慢网络下宁可画面停顿也不录进灰块，上限放宽到 30s
let tileGateSince = 0
const TILE_GATE_TIMEOUT_MS = 30000

// 动画循环
function animationLoop(timestamp: number) {
  if (!lastTimestamp.value) {
    lastTimestamp.value = timestamp
  }

  // 导出模式（流式录制）：瓦片未就绪时本帧不推进，避免未加载瓦片入镜
  // （画面短暂停顿优于灰块；时间轴以挂钟为准，停顿即输出中的短暂驻留）
  if (props.exportMode && animationStore.isPlaying) {
    const pending = pendingTileCount()
    if (pending > 0) {
      if (!tileGateSince) {
        tileGateSince = timestamp
      }
      if (timestamp - tileGateSince < TILE_GATE_TIMEOUT_MS) {
        lastTimestamp.value = timestamp
        animationFrameId.value = requestAnimationFrame(animationLoop)
        return
      }
      // 门控超时：放行推进（tileGateSince 保持，待瓦片清零后重置）
    } else {
      tileGateSince = 0
    }
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
// force: 跳过节流立即应用（模式切换时使用，确保切换即刻生效）
function updateAnimation(force = false) {
  // 移动端：需要在每次更新时计算并 emit 位置
  if (isMobile.value) {
    updateAndEmitPosition()
  }

  const now = Date.now()
  // 节流更新：避免过于频繁地调用地图适配器
  if (!force && now - lastUpdateTime.value < UPDATE_THROTTLE_MS) {
    return
  }

  lastUpdateTime.value = now

  // 桌面端：从 currentPosition 计算属性获取位置
  // 移动端：从 updateAndEmitPosition 获取位置
  const pos = isMobile.value ? updateAndEmitPosition.getLastPosition?.() ?? null : currentPosition.value

  if (!pos) {
    return
  }

  // 相机平滑（±1.5s 位置滑动平均 + 航向窗口测向圆周平滑，移植 amap_remotion）：
  // 仅相机与固定中心标记使用平滑结果，抑制 GPS 抖动；full 模式标记仍压原始轨迹线
  const cam = cameraAtCurrentTime()
  const markerPos: MarkerPosition = cam && animationStore.cameraMode === 'fixed-center'
    ? { ...pos, lat: cam.lat, lng: cam.lng }
    : pos
  if (cam?.heading != null) {
    markerPos.bearing = cam.heading
  }
  setMarkerPosition(markerPos, animationStore.markerStyle)

  // 更新双色轨迹（索引未变时跳过：setPassedSegment 每次全量重建两条 Polyline，
  // 逐帧导出/静止回放下是主要的每帧开销）
  const { index } = findPointIndexByTime(
    absoluteCurrentTime.value,
    points.value,
    props.config.startTime
  )
  if (index !== lastPassedIndex) {
    setPassedSegment(0, index)
    lastPassedIndex = index
  }

  // 相机与朝向模式：
  // - fixed-center：平滑相机位置居中（标记与相机同点，恒居中），朝向按 orientationMode
  //   （track-up 时轨迹方向始终指向画面上方）；缩放按速度自适应（60km/h 及以下约 30m/格，
  //   速度更高适当缩小）。缩放仅在进入模式或速度档位变化时应用，避免逐帧覆盖用户手动缩放
  // - full：展示整个路径，固定正北朝上（视野在模式切换时调整，不逐帧 fit）
  if (animationStore.cameraMode === 'fixed-center') {
    const center: MarkerPosition = cam ? { ...pos, lat: cam.lat, lng: cam.lng } : pos
    const targetZoom = getFixedCenterZoom(pos.speed, pos.lat)
    if (lastFixedCenterZoom === null || targetZoom !== lastFixedCenterZoom) {
      setCameraToMarker(center, targetZoom)
      lastFixedCenterZoom = targetZoom
    } else {
      setCameraToMarker(center)
    }
    applyMapRotation(
      animationStore.orientationMode === 'track-up' ? (cam?.heading ?? pos.bearing) : 0
    )
  } else {
    applyMapRotation(0)
  }
}

// 生命周期
onMounted(() => {
  isInitialized.value = true
  animationFrameId.value = requestAnimationFrame(animationLoop)

  // 初始化时触发一次位置更新（移动端需要 emit position-changed）
  if (isMobile.value) {
    updateAndEmitPosition()
  }

  // 导出模式（后端逐帧截图）：暴露单帧定位接口
  // 后端对每帧调用 seek → 强制刷新 → 等待地图空闲（瓦片加载完成）→ 截图，
  // 输出视频不受实时录制下瓦片加载滞后与压缩质量问题影响
  if (props.exportMode) {
    let exportInstanceReady = false
    ;(window as any).__seekExportFrame = async (t: number) => {
      animationStore.setPlaybackState('isPlaying', false)
      animationStore.setPlaybackState('currentTime', t)
      // 首帧等待地图实例就绪：exportState=ready 可能早于 SDK 异步初始化完成
      //（实测首次 seek 打在实例未建好时，waitForIdle 立即返回、适配层调用全部落空）。
      // 连续 3 次读到非空视图状态才算稳：配置异步加载期间 UniversalMap 会先挂 Leaflet
      // 兜底再切 SDK 引擎，实例会经历 null 窗口，单次非空可能来自即将被换掉的实例
      if (!exportInstanceReady) {
        exportInstanceReady = true
        const readyStart = Date.now()
        let stable = 0
        while (stable < 3 && Date.now() - readyStart < 10000) {
          stable = getGlobalViewState().center ? stable + 1 : 0
          await new Promise((r) => setTimeout(r, 150))
        }
      }
      // 亚像素跳帧（移植 amap_remotion）：与上一帧相比相机位移 < 0.6px 且转角 < 0.06°
      // 时直接复用上一帧画面——SDK 对无效移动去重会使 moveend 不触发、等待链悬挂，
      // 且画面无可见差异。仅 fixed-center 判定相机状态；full 模式相机静止但标记
      // 持续移动，不跳帧（仅靠 waitForIdle 的收敛判定）
      const pos = currentPosition.value
      const cam = cameraAtCurrentTime()
      if (cam && pos && animationStore.cameraMode === 'fixed-center') {
        const zoom = getGlobalViewState().zoom
        const bearing = cam.heading ?? pos.bearing
        if (
          lastSeekCamera &&
          lastSeekCamera.zoom !== null &&
          zoom !== null &&
          lastSeekCamera.zoom === zoom
        ) {
          const cosLat = Math.max(
            0.1,
            Math.cos((((lastSeekCamera.lat + cam.lat) / 2) * Math.PI) / 180)
          )
          const mPerPx = (156543.03392 * cosLat) / Math.pow(2, lastSeekCamera.zoom)
          const movedPx =
            calculateDistance(lastSeekCamera.lat, lastSeekCamera.lng, cam.lat, cam.lng) / mPerPx
          const dBearing = Math.abs(calculateShortestRotation(lastSeekCamera.bearing, bearing))
          if (movedPx < 0.6 && dBearing < 0.06) return
        }
        lastSeekCamera = { lat: cam.lat, lng: cam.lng, bearing, zoom }
      }
      updateAnimation(true)
      await waitForMapIdle()
    }
    // 预热页专用：仅定位不等待（快速扫掠/跟随主录制页前方位置，把瓦片请求排入浏览器缓存）
    ;(window as any).__seekExportPosition = (t: number) => {
      animationStore.setPlaybackState('isPlaying', false)
      animationStore.setPlaybackState('currentTime', t)
      updateAnimation(true)
    }
  }
})

onUnmounted(() => {
  if (animationFrameId.value) {
    cancelAnimationFrame(animationFrameId.value)
  }
  if (props.exportMode) {
    delete (window as any).__seekExportFrame
    delete (window as any).__seekExportPosition
  }
})

// 监听播放状态变化
watch(() => animationStore.isPlaying, (isPlaying) => {
  lastTimestamp.value = 0
  // 通知地图组件更新动画播放状态，避免双色轨迹闪烁
  setAnimationPlaying(isPlaying)
  // 播放态切换会清空/重建双色轨迹线，索引缓存随之失效
  lastPassedIndex = -1
  // 确保标记在状态变化时立即更新
  updateAnimation()
})

// 监听时间变化，确保 seek 操作时标记更新
watch(() => animationStore.currentTime, () => {
  // 在非播放状态下（如 seek 操作），需要手动触发更新
  if (!animationStore.isPlaying) {
    updateAnimation()
    // 移动端也需要 emit position-changed
    if (isMobile.value) {
      updateAndEmitPosition()
    }
  }
})

// 监听相机模式变化，刷新轨迹线
watch(() => animationStore.cameraMode, (newMode) => {
  // 相机模式切换时，如果是播放状态，重新绘制轨迹线
  if (animationStore.isPlaying) {
    setAnimationPlaying(true)
  }
})

// 监听相机/朝向模式切换：无论播放状态都立即按新模式刷新一次画面
// （若只依赖动画循环，rAF 节流/页面隐藏的场景下切换会迟迟看不到效果）
// 注意顺序：先 updateAnimation（full 模式复位旋转到正北），再 fit——否则会在旋转状态下 fit 导致边距错大
watch(() => [animationStore.cameraMode, animationStore.orientationMode] as const, () => {
  // 重置缩放记忆，进入固定中心时重新应用自适应缩放
  lastFixedCenterZoom = null
  // 相机模式切换会经 setAnimationPlaying 清空重建双色轨迹，索引缓存失效
  lastPassedIndex = -1
  updateAnimation(true)
  if (animationStore.cameraMode === 'full') {
    fitTrackWithPadding(0)
  }
})

// 监听 HUD 高度变化：全轨迹画面按 10% 边距重新 fit
watch(hudHeight, (newHeight) => {
  if (animationStore.cameraMode === 'full' && newHeight > 0) {
    fitTrackWithPadding(0)
  }
})

// 监听地图切换，全轨迹模式下重新调整视野；固定中心下重置缩放记忆待新地图重新应用
watch(() => props.mapProvider, () => {
  lastFixedCenterZoom = null
  if (animationStore.cameraMode === 'full') {
    // 延迟执行，等待地图初始化完成
    nextTick(() => {
      setTimeout(() => {
        fitTrackWithPadding(0)
      }, 500)
    })
  }
})

// 监听标记样式变化，更新地图上的标记
watch(() => animationStore.markerStyle, () => {
  const pos = isMobile.value ? updateAndEmitPosition.getLastPosition?.() ?? null : currentPosition.value
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

/* 导出模式：播放进度信息行 */
.info-export-progress {
  font-weight: 500;
  color: #ffd666;
  border-bottom: 1px solid rgba(255, 255, 255, 0.25);
  padding-bottom: 4px;
  margin-bottom: 4px;
}
</style>
