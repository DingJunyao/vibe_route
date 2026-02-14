# 轨迹动画功能实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**目标:** 在轨迹详情页和分享页面添加动画回放功能，支持倍速播放、画面模式切换和视频导出

**架构:**
- 前端：Vue 3 组件化架构，核心播放器组件 + HUD 控制面板 + 各地图引擎混入
- 后端：FastAPI 异步服务，使用 Playwright 录制视频导出
- 状态管理：Pinia store + localStorage 持久化

**技术栈:**
- 前端：Vue 3、TypeScript、Element Plus、MediaRecorder API
- 后端：Python 3.12+、FastAPI、Playwright、FFmpeg（可选）
- 地图引擎：高德、百度（GL/Legacy）、腾讯、Leaflet

---

## Phase 1: 基础类型和工具函数

### Task 1.1: 创建动画类型定义文件

**文件:**
- 创建: `frontend/src/types/animation.ts`

**Step 1: 创建类型定义文件**

```typescript
// frontend/src/types/animation.ts

import type { TrackPoint } from './track'

/**
 * 动画配置
 */
export interface AnimationConfig {
  trackId: number
  trackPoints: TrackPoint[]
  startTime: string      // ISO 8601
  endTime: string        // ISO 8601
  duration: number       // 毫秒
}

/**
 * 播放状态
 */
export interface PlaybackState {
  isPlaying: boolean
  currentTime: number    // 毫秒
  playbackSpeed: number  // 0.25, 0.5, 1, 2, 4, 8, 16
  cameraMode: CameraMode
  orientationMode: OrientationMode
  showInfoPanel: boolean
  markerStyle: MarkerStyle
}

/**
 * 画面模式
 */
export type CameraMode = 'full' | 'fixed-center'

/**
 * 朝向模式
 */
export type OrientationMode = 'north-up' | 'track-up'

/**
 * 标记样式
 */
export type MarkerStyle = 'arrow' | 'car' | 'person'

/**
 * 导出配置
 */
export interface ExportConfig {
  resolution: Resolution
  fps: 30 | 60
  showHUD: boolean
  format: 'webm' | 'mp4'
  speed: number  // 导出倍速，1.0 = 原速
}

/**
 * 分辨率选项
 */
export type Resolution = '720p' | '1080p' | '4k'

/**
 * 分辨率对应的尺寸
 */
export const RESOLUTION_DIMENSIONS: Record<Resolution, { width: number; height: number }> = {
  '720p': { width: 1280, height: 720 },
  '1080p': { width: 1920, height: 1080 },
  '4k': { width: 3840, height: 2160 },
} as const

/**
 * 移动标记位置
 */
export interface MarkerPosition {
  lat: number
  lng: number
  bearing: number  // 方位角 [0, 360)
  speed: number | null
  elevation: number | null
  time: string | null
}

/**
 * 动画偏好设置（本地存储）
 */
export interface AnimationPreferences {
  defaultSpeed: number
  showInfoPanel: boolean
  markerStyle: MarkerStyle
  defaultCameraMode: CameraMode
  defaultOrientationMode: OrientationMode
  exportResolution: Resolution
  exportFPS: 30 | 60
  exportShowHUD: boolean
}

/**
 * 默认偏好设置
 */
export const DEFAULT_PREFERENCES: AnimationPreferences = {
  defaultSpeed: 1,
  showInfoPanel: true,
  markerStyle: 'arrow',
  defaultCameraMode: 'full',
  defaultOrientationMode: 'north-up',
  exportResolution: '1080p',
  exportFPS: 30,
  exportShowHUD: true,
} as const

/**
 * 本地存储键名
 */
export const ANIMATION_STORAGE_KEY = 'vibe-route-animation-prefs'

/**
 * 倍速档位
 */
export const PLAYBACK_SPEEDS = [0.25, 0.5, 1, 2, 4, 8, 16] as const

/**
 * 倍速档位类型
 */
export type PlaybackSpeed = typeof PLAYBACK_SPEEDS[number]
```

**Step 2: 提交**

```bash
git add frontend/src/types/animation.ts
git commit -m "feat(animation): add animation type definitions"
```

---

### Task 1.2: 创建动画工具函数

**文件:**
- 创建: `frontend/src/utils/animationUtils.ts`

**Step 1: 创建工具函数文件**

```typescript
// frontend/src/utils/animationUtils.ts

import type { TrackPoint, MarkerPosition } from '@/types/animation'

/**
 * 计算轨迹持续时间（毫秒）
 */
export function calculateDuration(points: TrackPoint[]): number {
  if (points.length === 0) return 0

  // 找到第一个和最后一个有效的时间点
  const firstPoint = points.find(p => p.time)
  const lastPoint = [...points].reverse().find(p => p.time)

  if (!firstPoint?.time || !lastPoint?.time) {
    // 如果没有时间数据，返回 0
    return 0
  }

  return new Date(lastPoint.time).getTime() - new Date(firstPoint.time).getTime()
}

/**
 * 根据当前时间查找对应的轨迹点索引和插值进度
 * @param time - 当前播放时间（毫秒）
 * @param points - 轨迹点数组
 * @param startTime - 轨迹开始时间（ISO 字符串）
 * @returns 索引和进度 { index: number, progress: number }
 */
export function findPointIndexByTime(
  time: number,
  points: TrackPoint[],
  startTime: string
): { index: number; progress: number } {
  if (points.length === 0) return { index: 0, progress: 0 }
  if (points.length === 1) return { index: 0, progress: 0 }

  const startTimeMs = new Date(startTime).getTime()
  const elapsed = time - startTimeMs

  // 找到第一个有效时间点
  const firstValidIndex = points.findIndex(p => p.time)
  if (firstValidIndex === -1) {
    // 没有时间数据，使用线性索引
    const totalPoints = points.length
    const rawIndex = (elapsed / 1000) * 10 // 假设每秒 10 个点
    return {
      index: Math.min(Math.floor(rawIndex), totalPoints - 1),
      progress: rawIndex % 1,
    }
  }

  // 二分查找
  let left = firstValidIndex
  let right = points.length - 1

  while (left < right) {
    const mid = Math.floor((left + right) / 2)
    const midPoint = points[mid]
    if (!midPoint?.time) {
      // 跳过无效时间点
      left = mid + 1
      continue
    }
    const midTime = new Date(midPoint.time).getTime() - startTimeMs
    if (midTime < elapsed) {
      left = mid + 1
    } else {
      right = mid
    }
  }

  const index = Math.max(0, left - 1)
  const point = points[index]
  const nextPoint = points[index + 1]

  if (!point?.time || !nextPoint?.time) {
    return { index, progress: 0 }
  }

  const pointTime = new Date(point.time).getTime() - startTimeMs
  const nextPointTime = new Date(nextPoint.time).getTime() - startTimeMs
  const segmentDuration = nextPointTime - pointTime

  if (segmentDuration <= 0) {
    return { index, progress: 0 }
  }

  const progress = Math.min(1, Math.max(0, (elapsed - pointTime) / segmentDuration))

  return { index, progress }
}

/**
 * 在两个轨迹点之间进行线性插值
 */
export function interpolatePosition(
  point1: TrackPoint,
  point2: TrackPoint,
  progress: number
): MarkerPosition {
  const lat1 = point1.latitude_wgs84 ?? point1.latitude ?? 0
  const lng1 = point1.longitude_wgs84 ?? point1.longitude ?? 0
  const lat2 = point2.latitude_wgs84 ?? point2.latitude ?? 0
  const lng2 = point2.longitude_wgs84 ?? point2.longitude ?? 0

  const lat = lat1 + (lat2 - lat1) * progress
  const lng = lng1 + (lng2 - lng1) * progress

  // 方位角插值（处理 350° -> 10° 的情况）
  const bearing1 = point1.bearing ?? 0
  const bearing2 = point2.bearing ?? bearing1
  let bearing = bearing1 + (bearing2 - bearing1) * progress

  // 归一化到 [0, 360)
  if (bearing < 0) bearing += 360
  if (bearing >= 360) bearing -= 360

  // 速度插值
  const speed1 = point1.speed ?? 0
  const speed2 = point2.speed ?? 0
  const speed = speed1 + (speed2 - speed1) * progress

  // 海拔插值
  const elevation1 = point1.elevation ?? 0
  const elevation2 = point2.elevation ?? 0
  const elevation = elevation1 + (elevation2 - elevation1) * progress

  // 时间插值
  let time: string | null = null
  if (point1.time && point2.time) {
    const t1 = new Date(point1.time).getTime()
    const t2 = new Date(point2.time).getTime()
    const t = t1 + (t2 - t1) * progress
    time = new Date(t).toISOString()
  }

  return { lat, lng, bearing, speed, elevation, time }
}

/**
 * 计算最短旋转路径的角度差（处理 350° -> 10° 的情况）
 * @param from - 起始角度
 * @param to - 目标角度
 * @returns 角度差，范围 (-180, 180]
 */
export function calculateShortestRotation(from: number, to: number): number {
  let delta = to - from
  while (delta > 180) delta -= 360
  while (delta < -180) delta += 360
  return delta
}

/**
 * 归一化角度到 [0, 360)
 */
export function normalizeAngle(angle: number): number {
  let normalized = angle % 360
  if (normalized < 0) normalized += 360
  return normalized
}

/**
 * 格式化时间显示（毫秒转 HH:MM:SS）
 */
export function formatAnimationTime(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60

  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`
}

/**
 * 根据点数量和倍速计算采样步长
 */
export function getSampleStep(pointCount: number, speed: number): number {
  if (pointCount < 500) return 1
  if (speed >= 8) return 4
  if (speed >= 4) return 2
  if (pointCount < 2000) return 1
  return 2
}

/**
 * 检查轨迹是否有足够的数据用于动画播放
 */
export function canPlayAnimation(points: TrackPoint[]): { canPlay: boolean; reason?: string } {
  if (points.length === 0) {
    return { canPlay: false, reason: '无轨迹数据' }
  }
  if (points.length === 1) {
    return { canPlay: false, reason: '轨迹点不足' }
  }
  return { canPlay: true }
}

/**
 * 计算两个点之间的距离（米，使用 Haversine 公式）
 */
export function calculateDistance(
  lat1: number,
  lng1: number,
  lat2: number,
  lng2: number
): number {
  const R = 6371000 // 地球半径（米）
  const φ1 = (lat1 * Math.PI) / 180
  const φ2 = (lat2 * Math.PI) / 180
  const Δφ = ((lat2 - lat1) * Math.PI) / 180
  const Δλ = ((lng2 - lng1) * Math.PI) / 180

  const a =
    Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
    Math.cos(φ1) * Math.cos(φ2) * Math.sin(Δλ / 2) * Math.sin(Δλ / 2)
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))

  return R * c
}
```

**Step 2: 提交**

```bash
git add frontend/src/utils/animationUtils.ts
git commit -m "feat(animation): add animation utility functions"
```

---

### Task 1.3: 创建动画 Pinia Store

**文件:**
- 创建: `frontend/src/stores/animation.ts`

**Step 1: 创建动画状态管理 Store**

```typescript
// frontend/src/stores/animation.ts

import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import type {
  AnimationPreferences,
  PlaybackState,
  CameraMode,
  OrientationMode,
  MarkerStyle,
  PlaybackSpeed,
} from '@/types/animation'
import {
  DEFAULT_PREFERENCES,
  ANIMATION_STORAGE_KEY,
  PLAYBACK_SPEEDS,
} from '@/types/animation'

export const useAnimationStore = defineStore('animation', () => {
  // 从 localStorage 加载偏好设置
  const loadPreferences = (): AnimationPreferences => {
    try {
      const saved = localStorage.getItem(ANIMATION_STORAGE_KEY)
      if (saved) {
        return { ...DEFAULT_PREFERENCES, ...JSON.parse(saved) }
      }
    } catch (e) {
      console.warn('Failed to load animation preferences:', e)
    }
    return { ...DEFAULT_PREFERENCES }
  }

  // 保存偏好设置到 localStorage
  const savePreferences = (prefs: AnimationPreferences) => {
    try {
      localStorage.setItem(ANIMATION_STORAGE_KEY, JSON.stringify(prefs))
    } catch (e) {
      console.warn('Failed to save animation preferences:', e)
    }
  }

  // 偏好设置
  const preferences = ref<AnimationPreferences>(loadPreferences())

  // 监听偏好设置变化并保存
  watch(preferences, (newPrefs) => {
    savePreferences(newPrefs)
  }, { deep: true })

  // 当前播放状态
  const playbackState = ref<PlaybackState>({
    isPlaying: false,
    currentTime: 0,
    playbackSpeed: preferences.value.defaultSpeed,
    cameraMode: preferences.value.defaultCameraMode,
    orientationMode: preferences.value.defaultOrientationMode,
    showInfoPanel: preferences.value.showInfoPanel,
    markerStyle: preferences.value.markerStyle,
  })

  // 重置播放状态
  function resetPlaybackState() {
    playbackState.value = {
      isPlaying: false,
      currentTime: 0,
      playbackSpeed: preferences.value.defaultSpeed,
      cameraMode: preferences.value.defaultCameraMode,
      orientationMode: preferences.value.defaultOrientationMode,
      showInfoPanel: preferences.value.showInfoPanel,
      markerStyle: preferences.value.markerStyle,
    }
  }

  // 设置播放状态
  function setPlaybackState<K extends keyof PlaybackState>(
    key: K,
    value: PlaybackState[K]
  ) {
    playbackState.value[key] = value
  }

  // 切换播放/暂停
  function togglePlayPause() {
    playbackState.value.isPlaying = !playbackState.value.isPlaying
  }

  // 切换倍速
  function cycleSpeed() {
    const currentIndex = PLAYBACK_SPEEDS.indexOf(
      playbackState.value.playbackSpeed as PlaybackSpeed
    )
    const nextIndex = (currentIndex + 1) % PLAYBACK_SPEEDS.length
    playbackState.value.playbackSpeed = PLAYBACK_SPEEDS[nextIndex]
  }

  // 设置倍速
  function setSpeed(speed: number) {
    if (PLAYBACK_SPEEDS.includes(speed as PlaybackSpeed)) {
      playbackState.value.playbackSpeed = speed
    }
  }

  // 切换相机模式
  function toggleCameraMode() {
    const modes: CameraMode[] = ['full', 'fixed-center']
    const currentIndex = modes.indexOf(playbackState.value.cameraMode)
    playbackState.value.cameraMode = modes[(currentIndex + 1) % modes.length]
  }

  // 设置相机模式
  function setCameraMode(mode: CameraMode) {
    playbackState.value.cameraMode = mode
  }

  // 切换朝向模式
  function toggleOrientationMode() {
    const modes: OrientationMode[] = ['north-up', 'track-up']
    const currentIndex = modes.indexOf(playbackState.value.orientationMode)
    playbackState.value.orientationMode = modes[(currentIndex + 1) % modes.length]
  }

  // 设置朝向模式
  function setOrientationMode(mode: OrientationMode) {
    playbackState.value.orientationMode = mode
  }

  // 切换信息浮层
  function toggleInfoPanel() {
    playbackState.value.showInfoPanel = !playbackState.value.showInfoPanel
  }

  // 切换标记样式
  function cycleMarkerStyle() {
    const styles: MarkerStyle[] = ['arrow', 'car', 'person']
    const currentIndex = styles.indexOf(playbackState.value.markerStyle)
    playbackState.value.markerStyle = styles[(currentIndex + 1) % styles.length]
  }

  // 设置标记样式
  function setMarkerStyle(style: MarkerStyle) {
    playbackState.value.markerStyle = style
  }

  // 重置偏好设置
  function resetPreferences() {
    preferences.value = { ...DEFAULT_PREFERENCES }
  }

  // 更新偏好设置
  function updatePreferences<K extends keyof AnimationPreferences>(
    key: K,
    value: AnimationPreferences[K]
  ) {
    preferences.value[key] = value
  }

  // 监听 storage 事件（跨标签页同步）
  if (typeof window !== 'undefined') {
    window.addEventListener('storage', (e) => {
      if (e.key === ANIMATION_STORAGE_KEY && e.newValue) {
        try {
          preferences.value = {
            ...DEFAULT_PREFERENCES,
            ...JSON.parse(e.newValue),
          }
        } catch (err) {
          console.warn('Failed to sync animation preferences:', err)
        }
      }
    })
  }

  return {
    // 状态
    preferences,
    playbackState,

    // 计算属性
    isPlaying: computed(() => playbackState.value.isPlaying),
    currentTime: computed(() => playbackState.value.currentTime),
    playbackSpeed: computed(() => playbackState.value.playbackSpeed),
    cameraMode: computed(() => playbackState.value.cameraMode),
    orientationMode: computed(() => playbackState.value.orientationMode),
    showInfoPanel: computed(() => playbackState.value.showInfoPanel),
    markerStyle: computed(() => playbackState.value.markerStyle),

    // 方法
    resetPlaybackState,
    setPlaybackState,
    togglePlayPause,
    cycleSpeed,
    setSpeed,
    toggleCameraMode,
    setCameraMode,
    toggleOrientationMode,
    setOrientationMode,
    toggleInfoPanel,
    cycleMarkerStyle,
    setMarkerStyle,
    resetPreferences,
    updatePreferences,
    loadPreferences,
    savePreferences,
  }
})
```

**Step 2: 提交**

```bash
git add frontend/src/stores/animation.ts
git commit -m "feat(animation): add animation Pinia store"
```

---

## Phase 2: 核心播放器组件

### Task 2.1: 创建动画播放器核心组件

**文件:**
- 创建: `frontend/src/components/animation/TrackAnimationPlayer.vue`

**Step 1: 创建播放器组件**

```vue
<!-- frontend/src/components/animation/TrackAnimationPlayer.vue -->
<template>
  <div v-if="canPlay" class="track-animation-player">
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
      @toggle-camera-mode="animationStore.toggleCameraMode"
      @toggle-orientation-mode="animationStore.toggleOrientationMode"
      @toggle-info-panel="animationStore.toggleInfoPanel"
      @cycle-marker-style="animationStore.cycleMarkerStyle"
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
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useAnimationStore } from '@/stores/animation'
import { useAnimationMap } from '@/composables/animation/useAnimationMap'
import AnimationHUD from './AnimationHUD.vue'
import {
  calculateDuration,
  findPointIndexByTime,
  interpolatePosition,
  formatAnimationTime,
  canPlayAnimation as checkCanPlay,
  type TrackPoint,
  type MarkerPosition,
} from '@/utils/animationUtils'
import type { AnimationConfig } from '@/types/animation'

interface Props {
  config: AnimationConfig
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'position-change', position: MarkerPosition): void
  (e: 'segment-update', passedEnd: number): void
}>()

const animationStore = useAnimationStore()
const { setPassedSegment, setMarkerPosition, setCameraToMarker, setMapRotation } = useAnimationMap()

// 状态
const isInitialized = ref(false)
const animationFrameId = ref<number | null>(null)
const lastTimestamp = ref(0)

// 计算属性
const duration = computed(() => props.config.duration)
const points = computed(() => props.config.trackPoints)

const canPlay = computed(() => checkCanPlay(points.value).canPlay)

const currentPosition = computed<MarkerPosition | null>(() => {
  const { index, progress } = findPointIndexByTime(
    animationStore.currentTime,
    points.value,
    props.config.startTime
  )

  if (index >= points.value.length - 1) {
    // 到达终点
    const lastPoint = points.value[points.value.length - 1]
    if (lastPoint) {
      return {
        lat: lastPoint.latitude_wgs84 ?? lastPoint.latitude ?? 0,
        lng: lastPoint.longitude_wgs84 ?? lastPoint.longitude ?? 0,
        bearing: lastPoint.bearing ?? 0,
        speed: lastPoint.speed ?? null,
        elevation: lastPoint.elevation ?? null,
        time: lastPoint.time ?? null,
      }
    }
  }

  const point = points.value[index]
  const nextPoint = points.value[index + 1]

  if (!point || !nextPoint) return null

  return interpolatePosition(point, nextPoint, progress)
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

function handleSeek(time: number) {
  animationStore.setPlaybackState('currentTime', time)
  updatePosition()
}

function handleSetSpeed(speed: number) {
  animationStore.setSpeed(speed)
}

function handleExport() {
  // 打开导出对话框（后续实现）
  console.log('Export animation')
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
      updatePosition()
    } else {
      animationStore.setPlaybackState('currentTime', newTime)
      updatePosition()
    }
  }

  lastTimestamp.value = timestamp
  animationFrameId.value = requestAnimationFrame(animationLoop)
}

// 更新位置
function updatePosition() {
  const pos = currentPosition.value
  if (!pos) return

  // 通知地图更新
  emit('position-change', pos)
  setMarkerPosition(pos)

  // 更双色轨迹
  const { index } = findPointIndexByTime(
    animationStore.currentTime,
    points.value,
    props.config.startTime
  )
  emit('segment-update', index)
  setPassedSegment(0, index)

  // 固定中心模式
  if (animationStore.cameraMode === 'fixed-center') {
    setCameraToMarker(pos)

    if (animationStore.orientationMode === 'track-up') {
      setMapRotation(pos.bearing)
    }
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
```

**Step 2: 提交**

```bash
git add frontend/src/components/animation/TrackAnimationPlayer.vue
git commit -m "feat(animation): add TrackAnimationPlayer component"
```

---

### Task 2.2: 创建 HUD 控制面板组件

**文件:**
- 创建: `frontend/src/components/animation/AnimationHUD.vue`

**Step 1: 创建 HUD 组件**

```vue
<!-- frontend/src/components/animation/AnimationHUD.vue -->
<template>
  <div class="animation-hud">
    <div class="hud-content">
      <!-- 第一行：播放状态 + 倍速 -->
      <div class="hud-row hud-controls">
        <el-button
          :icon="isPlaying ? VideoPause : VideoPlay"
          circle
          size="small"
          @click="$emit('toggle-play')"
        />
        <div class="speed-display" @click="showSpeedMenu = !showSpeedMenu">
          {{ playbackSpeed }}x
        </div>
      </div>

      <!-- 第二行：进度条 -->
      <div class="hud-row hud-progress">
        <el-slider
          :model-value="progressPercent"
          :format-tooltip="formatProgressTooltip"
          @input="handleSeek"
        />
        <div class="time-display">
          {{ formatTime(currentTime) }} / {{ formatTime(totalDuration) }}
        </div>
      </div>

      <!-- 第三行：功能按钮 -->
      <div class="hud-row hud-actions">
        <el-tooltip :content="cameraModeTooltip">
          <el-button
            :icon="getCameraModeIcon()"
            size="small"
            @click="$emit('toggle-camera-mode')"
          />
        </el-tooltip>
        <el-tooltip content="信息浮层">
          <el-button
            :type="showInfoPanel ? 'primary' : ''"
            size="small"
            @click="$emit('toggle-info-panel')"
          >
            <el-icon><Location /></el-icon>
          </el-button>
        </el-tooltip>
        <el-tooltip content="标记样式">
          <el-button size="small" @click="$emit('cycle-marker-style')">
            <component :is="getMarkerIcon()" />
          </el-button>
        </el-tooltip>
        <el-tooltip content="导出视频">
          <el-button size="small" @click="$emit('export')">
            <el-icon><Film /></el-icon>
          </el-button>
        </el-tooltip>
      </div>

      <!-- 倍速菜单 -->
      <div v-if="showSpeedMenu" class="speed-menu">
        <div
          v-for="speed in SPEED_OPTIONS"
          :key="speed"
          class="speed-option"
          :class="{ active: speed === playbackSpeed }"
          @click="handleSetSpeed(speed)"
        >
          {{ speed }}x
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  VideoPlay,
  VideoPause,
  Location,
  Film,
  Monitor,
  Aim,
  ArrowDown,
} from '@element-plus/icons-vue'
import { formatAnimationTime } from '@/utils/animationUtils'

interface Props {
  isPlaying: boolean
  currentTime: number
  totalDuration: number
  playbackSpeed: number
  cameraMode: 'full' | 'fixed-center'
  orientationMode: 'north-up' | 'track-up'
  showInfoPanel: boolean
  markerStyle: 'arrow' | 'car' | 'person'
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'toggle-play'): void
  (e: 'seek', time: number): void
  (e: 'set-speed', speed: number): void
  (e: 'toggle-camera-mode'): void
  (e: 'toggle-orientation-mode'): void
  (e: 'toggle-info-panel'): void
  (e: 'cycle-marker-style'): void
  (e: 'export'): void
}>()

const SPEED_OPTIONS = [0.25, 0.5, 1, 2, 4, 8, 16] as const
const showSpeedMenu = ref(false)

const progressPercent = computed(() => {
  if (props.totalDuration === 0) return 0
  return (props.currentTime / props.totalDuration) * 100
})

const cameraModeTooltip = computed(() => {
  if (props.cameraMode === 'full') return '全轨迹画面'
  if (props.orientationMode === 'north-up') return '固定中心 - 正北朝上'
  return '固定中心 - 轨迹朝上'
})

function formatTime(ms: number): string {
  return formatAnimationTime(ms)
}

function formatProgressTooltip(value: number): string {
  const time = (props.totalDuration * value) / 100
  return formatTime(time)
}

function handleSeek(value: number) {
  const time = (props.totalDuration * value) / 100
  emit('seek', time)
}

function handleSetSpeed(speed: number) {
  emit('set-speed', speed)
  showSpeedMenu.value = false
}

function getCameraModeIcon() {
  if (props.cameraMode === 'full') return Monitor
  return Aim
}

function getMarkerIcon() {
  switch (props.markerStyle) {
    case 'arrow':
      return ArrowDown
    case 'car':
      return 'div' // 简化，后续可替换为图标
    case 'person':
      return 'div'
    default:
      return ArrowDown
  }
}
</script>

<style scoped>
.animation-hud {
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 1000;
}

.hud-content {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 8px;
  padding: 12px 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
  min-width: 280px;
}

.hud-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.hud-row + .hud-row {
  margin-top: 8px;
}

.hud-controls {
  justify-content: space-between;
}

.speed-display {
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  user-select: none;
  padding: 4px 8px;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.speed-display:hover {
  background-color: var(--el-fill-color-light);
}

.hud-progress {
  flex-direction: column;
  align-items: stretch;
}

.hud-progress .el-slider {
  margin: 0;
}

.time-display {
  text-align: center;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}

.hud-actions {
  justify-content: center;
}

.speed-menu {
  position: absolute;
  bottom: 100%;
  left: 0;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
  padding: 4px 0;
  margin-bottom: 8px;
  min-width: 60px;
}

.speed-option {
  padding: 8px 16px;
  text-align: center;
  cursor: pointer;
  transition: background-color 0.2s;
}

.speed-option:hover {
  background-color: var(--el-fill-color-light);
}

.speed-option.active {
  color: var(--el-color-primary);
  font-weight: 500;
}
</style>
```

**Step 2: 提交**

```bash
git add frontend/src/components/animation/AnimationHUD.vue
git commit -m "feat(animation): add AnimationHUD component"
```

---

## Phase 3: 地图动画混入

### Task 3.1: 创建动画地图适配接口和 composable

**文件:**
- 创建: `frontend/src/composables/animation/useAnimationMap.ts`

**Step 1: 创建动画地图 composable**

```typescript
// frontend/src/composables/animation/useAnimationMap.ts

import { ref, computed } from 'vue'
import type { MarkerPosition } from '@/types/animation'

/**
 * 动画地图适配接口
 */
export interface AnimationMapAdapter {
  // 设置双色轨迹
  setPassedSegment(start: number, end: number): void

  // 设置移动标记
  setMarkerPosition(position: MarkerPosition): void

  // 设置地图中心
  setCameraToMarker(position: MarkerPosition): void

  // 设置地图旋转
  setMapRotation(bearing: number): void

  // 获取当前旋转角度
  getMapRotation(): number
}

/**
 * 动画地图 composable
 */
export function useAnimationMap() {
  const currentAdapter = ref<AnimationMapAdapter | null>(null)
  const currentRotation = ref(0)

  // 注册适配器
  function registerAdapter(adapter: AnimationMapAdapter) {
    currentAdapter.value = adapter
  }

  // 取消注册
  function unregisterAdapter() {
    currentAdapter.value = null
  }

  // 设置双色轨迹
  function setPassedSegment(start: number, end: number) {
    currentAdapter.value?.setPassedSegment(start, end)
  }

  // 设置移动标记
  function setMarkerPosition(position: MarkerPosition) {
    currentAdapter.value?.setMarkerPosition(position)
  }

  // 设置地图中心
  function setCameraToMarker(position: MarkerPosition) {
    currentAdapter.value?.setCameraToMarker(position)
  }

  // 设置地图旋转（平滑过渡）
  function setMapRotation(targetBearing: number) {
    if (!currentAdapter.value) return

    const current = currentAdapter.value.getMapRotation()
    const delta = calculateShortestRotation(current, targetBearing)

    // 平滑过渡（分5步完成）
    const steps = 5
    const stepDelta = delta / steps
    let currentStep = 0

    function animate() {
      if (currentStep < steps) {
        const newRotation = current + stepDelta * (currentStep + 1)
        currentAdapter.value?.setMapRotation(normalizeAngle(newRotation))
        currentStep++
        requestAnimationFrame(animate)
      }
    }

    animate()
  }

  // 辅助函数
  function calculateShortestRotation(from: number, to: number): number {
    let delta = to - from
    while (delta > 180) delta -= 360
    while (delta < -180) delta += 360
    return delta
  }

  function normalizeAngle(angle: number): number {
    let normalized = angle % 360
    if (normalized < 0) normalized += 360
    return normalized
  }

  return {
    currentAdapter,
    currentRotation,
    registerAdapter,
    unregisterAdapter,
    setPassedSegment,
    setMarkerPosition,
    setCameraToMarker,
    setMapRotation,
  }
}
```

**Step 2: 提交**

```bash
git add frontend/src/composables/animation/useAnimationMap.ts
git commit -m "feat(animation): add useAnimationMap composable"
```

---

### Task 3.2: 为 AMap 添加动画支持

**文件:**
- 修改: `frontend/src/components/map/AMap.vue`

**Step 1: 在 AMap.vue 中添加动画支持**

在 `<script setup>` 部分添加以下内容：

```typescript
// 在 AMap.vue 的 script setup 中添加

import { onMounted, onUnmounted } from 'vue'
import { useAnimationMap, type AnimationMapAdapter } from '@/composables/animation/useAnimationMap'

// 动画相关状态
const animationPassedPolyline = ref<AMap.Polyline | null>(null)
const animationRemainingPolyline = ref<AMap.Polyline | null>(null)
const animationMarker = ref<AMap.Marker | null>(null)
const animationMarkerContent = ref<HTMLDivElement | null>(null)
const currentMapRotation = ref(0)

// 创建动画标记图标
function createAnimationIcon() {
  const div = document.createElement('div')
  div.innerHTML = `
    <div style="
      width: 24px;
      height: 24px;
      position: relative;
    ">
      <div style="
        width: 0;
        height: 0;
        border-left: 12px solid transparent;
        border-right: 12px solid transparent;
        border-bottom: 20px solid #409eff;
        transform: rotate(0deg);
      "></div>
    </div>
  `
  return div
}

// 实现动画地图适配器
const animationAdapter: AnimationMapAdapter = {
  setPassedSegment(start: number, end: number) {
    if (!AMapInstance || !props.tracks[0]?.points) return

    const points = props.tracks[0].points
    const passedPoints = points.slice(0, end + 1)
    const remainingPoints = points.slice(end)

    // 转换为 AMap.LngLat 数组
    const toLngLat = (p: any) => new AMap.LngLat(
      p.longitude_gcj02 ?? p.longitude_wgs84 ?? p.longitude,
      p.latitude_gcj02 ?? p.latitude_wgs84 ?? p.latitude
    )

    // 移除旧的轨迹
    if (animationPassedPolyline.value) {
      AMapInstance.remove(animationPassedPolyline.value)
    }
    if (animationRemainingPolyline.value) {
      AMapInstance.remove(animationRemainingPolyline.value)
    }

    // 绘制已过轨迹（蓝色）
    if (passedPoints.length > 1) {
      animationPassedPolyline.value = new AMap.Polyline({
        path: passedPoints.map(toLngLat),
        strokeColor: '#409eff',
        strokeWeight: 5,
        strokeOpacity: 0.8,
      })
      AMapInstance.add(animationPassedPolyline.value)
    }

    // 绘制未过轨迹（灰色）
    if (remainingPoints.length > 1) {
      animationRemainingPolyline.value = new AMap.Polyline({
        path: remainingPoints.map(toLngLat),
        strokeColor: '#c0c4cc',
        strokeWeight: 5,
        strokeOpacity: 0.5,
      })
      AMapInstance.add(animationRemainingPolyline.value)
    }
  },

  setMarkerPosition(position: MarkerPosition) {
    if (!AMapInstance) return

    // 转换坐标（假设使用 GCJ02）
    // TODO: 根据当前坐标系转换
    const lngLat = new AMap.LngLat(position.lng, position.lat)

    if (!animationMarker.value) {
      // 创建标记
      animationMarker.value = new AMap.Marker({
        position: lngLat,
        content: createAnimationIcon(),
        offset: new AMap.Pixel(-12, -10),
      })
      AMapInstance.add(animationMarker.value)
    } else {
      animationMarker.value.setPosition(lngLat)
    }

    // 旋转标记（更新图标旋转角度）
    const content = animationMarker.value.getContent() as HTMLDivElement
    if (content) {
      const arrow = content.querySelector('div > div') as HTMLDivElement
      if (arrow) {
        arrow.style.transform = `rotate(${position.bearing}deg)`
      }
    }
  },

  setCameraToMarker(position: MarkerPosition) {
    if (!AMapInstance) return
    const lngLat = new AMap.LngLat(position.lng, position.lat)
    AMapInstance.setCenter(lngLat)
  },

  setMapRotation(bearing: number) {
    // 高德地图需要切换到 3D 模式才能旋转
    if (!AMapInstance) return

    // 设置为 3D 模式
    AMapInstance.setViewMode('3D')

    // 设置旋转角度（高德使用 pitch，rotation 是俯仰角）
    // 高德地图的旋转是通过 setRotation 实现的，参数是 0-360
    currentMapRotation.value = bearing
    AMapInstance.setRotation(bearing)
  },

  getMapRotation() {
    return currentMapRotation.value
  },
}

// 注册适配器
onMounted(() => {
  // 等待地图初始化
  setTimeout(() => {
    useAnimationMap().registerAdapter(animationAdapter)
  }, 100)
})

onUnmounted(() => {
  useAnimationMap().unregisterAdapter()

  // 清理动画元素
  if (animationPassedPolyline.value) {
    AMapInstance?.remove(animationPassedPolyline.value)
  }
  if (animationRemainingPolyline.value) {
    AMapInstance?.remove(animationRemainingPolyline.value)
  }
  if (animationMarker.value) {
    AMapInstance?.remove(animationMarker.value)
  }
})
```

**Step 2: 提交**

```bash
git add frontend/src/components/map/AMap.vue
git commit -m "feat(animation): add animation support to AMap"
```

---

### Task 3.3: 为 LeafletMap 添加动画支持

**文件:**
- 修改: `frontend/src/components/map/LeafletMap.vue`

**Step 1: 在 LeafletMap.vue 中添加动画支持**

```typescript
// 在 LeafletMap.vue 的 script setup 中添加

import { useAnimationMap, type AnimationMapAdapter } from '@/composables/animation/useAnimationMap'

// 动画相关状态
const animationPassedPolyline = ref<L.Polyline | null>(null)
const animationRemainingPolyline = ref<L.Polyline | null>(null)
const animationMarker = ref<L.Marker | null>(null)
const animationMarkerIcon = ref<L.DivIcon | null>(null)

// 创建动画标记图标
function createAnimationIcon() {
  return L.divIcon({
    className: 'animation-marker',
    html: `
      <div style="
        width: 24px;
        height: 24px;
        position: relative;
      ">
        <div class="animation-arrow" style="
          width: 0;
          height: 0;
          border-left: 12px solid transparent;
          border-right: 12px solid transparent;
          border-bottom: 20px solid #409eff;
          transform-origin: center 70%;
        "></div>
      </div>
    `,
    iconSize: [24, 24],
    iconAnchor: [12, 20],
  })
}

// 实现动画地图适配器
const animationAdapter: AnimationMapAdapter = {
  setPassedSegment(start: number, end: number) {
    if (!map || !props.tracks[0]?.points) return

    const points = props.tracks[0].points
    const passedPoints = points.slice(0, end + 1)
    const remainingPoints = points.slice(end)

    const toLatLng = (p: any) => [
      p.latitude_wgs84 ?? p.latitude,
      p.longitude_wgs84 ?? p.longitude,
    ] as [number, number]

    // 移除旧的轨迹
    if (animationPassedPolyline.value) {
      map.removeLayer(animationPassedPolyline.value)
    }
    if (animationRemainingPolyline.value) {
      map.removeLayer(animationRemainingPolyline.value)
    }

    // 绘制已过轨迹（蓝色）
    if (passedPoints.length > 1) {
      animationPassedPolyline.value = L.polyline(
        passedPoints.map(toLatLng),
        {
          color: '#409eff',
          weight: 5,
          opacity: 0.8,
        }
      ).addTo(map)
    }

    // 绘制未过轨迹（灰色）
    if (remainingPoints.length > 1) {
      animationRemainingPolyline.value = L.polyline(
        remainingPoints.map(toLatLng),
        {
          color: '#c0c4cc',
          weight: 5,
          opacity: 0.5,
        }
      ).addTo(map)
    }
  },

  setMarkerPosition(position: MarkerPosition) {
    if (!map) return

    const latLng: [number, number] = [position.lat, position.lng]

    if (!animationMarker.value) {
      animationMarkerIcon.value = createAnimationIcon()
      animationMarker.value = L.marker(latLng, {
        icon: animationMarkerIcon.value,
      }).addTo(map)
    } else {
      animationMarker.value.setLatLng(latLng)
    }

    // 旋转箭头
    const icon = animationMarker.value.getElement()
    if (icon) {
      const arrow = icon.querySelector('.animation-arrow') as HTMLDivElement
      if (arrow) {
        arrow.style.transform = `rotate(${position.bearing}deg)`
      }
    }
  },

  setCameraToMarker(position: MarkerPosition) {
    if (!map) return
    map.panTo([position.lat, position.lng])
  },

  setMapRotation(bearing: number) {
    // Leaflet 默认不支持旋转
    // 需要使用 leaflet-rotate 插件
    // 或者使用 CSS transform
    console.warn('Leaflet rotation requires plugin')
  },

  getMapRotation() {
    return 0
  },
}

// 注册适配器
onMounted(() => {
  setTimeout(() => {
    useAnimationMap().registerAdapter(animationAdapter)
  }, 100)
})

onUnmounted(() => {
  useAnimationMap().unregisterAdapter()

  if (animationPassedPolyline.value) {
    map?.removeLayer(animationPassedPolyline.value)
  }
  if (animationRemainingPolyline.value) {
    map?.removeLayer(animationRemainingPolyline.value)
  }
  if (animationMarker.value) {
    map?.removeLayer(animationMarker.value)
  }
})
```

**Step 2: 提交**

```bash
git add frontend/src/components/map/LeafletMap.vue
git commit -m "feat(animation): add animation support to LeafletMap"
```

---

### Task 3.4: 为 BMap 和 TencentMap 添加动画支持

**文件:**
- 修改: `frontend/src/components/map/BMap.vue`
- 修改: `frontend/src/components/map/TencentMap.vue`

**Step 1: 在 BMap.vue 中添加动画支持**

```typescript
// 在 BMap.vue 中添加（类似 AMap 的实现）
// 注意：百度 Legacy 版本不支持地图旋转

import { useAnimationMap, type AnimationMapAdapter } from '@/composables/animation/useAnimationMap'

// 动画相关状态
const animationPassedPolyline = ref<any>(null)
const animationRemainingPolyline = ref<any>(null)
const animationMarker = ref<any>(null)

// 实现动画地图适配器
const animationAdapter: AnimationMapAdapter = {
  setPassedSegment(start: number, end: number) {
    if (!BMapInstance || !props.tracks[0]?.points) return

    const points = props.tracks[0].points
    const passedPoints = points.slice(0, end + 1)
    const remainingPoints = points.slice(end)

    const BMapClass = (window as any).BMap || (window as any).BMapGL
    const toPoint = (p: any) => new BMapClass.Point(
      p.longitude_bd09 ?? p.longitude_wgs84 ?? p.longitude,
      p.latitude_bd09 ?? p.latitude_wgs84 ?? p.latitude
    )

    // 移除旧的轨迹
    if (animationPassedPolyline.value) {
      BMapInstance.removeOverlay(animationPassedPolyline.value)
    }
    if (animationRemainingPolyline.value) {
      BMapInstance.removeOverlay(animationRemainingPolyline.value)
    }

    // 绘制轨迹
    if (passedPoints.length > 1) {
      animationPassedPolyline.value = new BMapClass.Polyline(
        passedPoints.map(toPoint),
        {
          strokeColor: '#409eff',
          strokeWeight: 5,
          strokeOpacity: 0.8,
        }
      )
      BMapInstance.addOverlay(animationPassedPolyline.value)
    }

    if (remainingPoints.length > 1) {
      animationRemainingPolyline.value = new BMapClass.Polyline(
        remainingPoints.map(toPoint),
        {
          strokeColor: '#c0c4cc',
          strokeWeight: 5,
          strokeOpacity: 0.5,
        }
      )
      BMapInstance.addOverlay(animationRemainingPolyline.value)
    }
  },

  setMarkerPosition(position: MarkerPosition) {
    if (!BMapInstance) return

    const BMapClass = (window as any).BMap || (window as any).BMapGL
    const point = new BMapClass.Point(position.lng, position.lat)

    if (!animationMarker.value) {
      // 创建自定义标记
      animationMarker.value = new BMapClass.Marker(point, {
        // 自定义图标
      })
      BMapInstance.addOverlay(animationMarker.value)
    } else {
      animationMarker.value.setPosition(point)
    }
  },

  setCameraToMarker(position: MarkerPosition) {
    if (!BMapInstance) return
    const BMapClass = (window as any).BMap || (window as any).BMapGL
    const point = new BMapClass.Point(position.lng, position.lat)
    BMapInstance.setCenter(point)
  },

  setMapRotation(bearing: number) {
    // 百度 Legacy 版本不支持旋转
    if (props.defaultLayerId === 'baidu_legacy') {
      console.warn('Baidu Legacy does not support rotation')
      return
    }
    // GL 版本支持
    if (BMapInstance && typeof BMapInstance.setMapStyle === 'function') {
      // GL 版本的旋转方法
    }
  },

  getMapRotation() {
    return 0
  },
}

// 注册和清理（同 AMap）
onMounted(() => {
  setTimeout(() => {
    useAnimationMap().registerAdapter(animationAdapter)
  }, 100)
})

onUnmounted(() => {
  useAnimationMap().unregisterAdapter()
  // 清理动画元素
})
```

**Step 2: 在 TencentMap.vue 中添加动画支持**

```typescript
// 在 TencentMap.vue 中添加

import { useAnimationMap, type AnimationMapAdapter } from '@/composables/animation/useAnimationMap'

// 动画相关状态
const animationPassedPolyline = ref<any>(null)
const animationRemainingPolyline = ref<any>(null)
const animationMarker = ref<any>(null)
const currentMapRotation = ref(0)

// 实现动画地图适配器
const animationAdapter: AnimationMapAdapter = {
  setPassedSegment(start: number, end: number) {
    if (!TMapInstance || !props.tracks[0]?.points) return

    const points = props.tracks[0].points
    const passedPoints = points.slice(0, end + 1)
    const remainingPoints = points.slice(end)

    const TMap = (window as any).TMap
    const toLatLng = (p: any) => new TMap.LatLng(
      p.latitude_gcj02 ?? p.latitude_wgs84 ?? p.latitude,
      p.longitude_gcj02 ?? p.longitude_wgs84 ?? p.longitude
    )

    // 移除旧的轨迹
    if (animationPassedPolyline.value) {
      animationPassedPolyline.value.setMap(null)
    }
    if (animationRemainingPolyline.value) {
      animationRemainingPolyline.value.setMap(null)
    }

    // 绘制轨迹
    if (passedPoints.length > 1) {
      animationPassedPolyline.value = new TMap.MultiPolyline({
        geometries: [{
          id: 'passed',
          styleId: 'passed-style',
          paths: [passedPoints.map(toLatLng)],
        }],
        styles: {
          'passed-style': new TMap.PolylineStyle({
            color: '#409eff',
            width: 5,
            borderWidth: 0,
          }),
        },
      })
      animationPassedPolyline.value.setMap(TMapInstance)
    }

    if (remainingPoints.length > 1) {
      animationRemainingPolyline.value = new TMap.MultiPolyline({
        geometries: [{
          id: 'remaining',
          styleId: 'remaining-style',
          paths: [remainingPoints.map(toLatLng)],
        }],
        styles: {
          'remaining-style': new TMap.PolylineStyle({
            color: '#c0c4cc',
            width: 5,
            borderWidth: 0,
          }),
        },
      })
      animationRemainingPolyline.value.setMap(TMapInstance)
    }
  },

  setMarkerPosition(position: MarkerPosition) {
    if (!TMapInstance) return

    const TMap = (window as any).TMap
    const latLng = new TMap.LatLng(position.lat, position.lng)

    if (!animationMarker.value) {
      animationMarker.value = new TMap.MultiMarker({
        geometries: [{
          id: 'animation-marker',
          position: latLng,
        }],
        styles: {
          'animation-marker': new TMap.MarkerStyle({
            width: 24,
            height: 24,
            anchor: { x: 12, y: 20 },
          }),
        },
      })
      animationMarker.value.setMap(TMapInstance)
    } else {
      animationMarker.value.setGeometries([
        { id: 'animation-marker', position: latLng },
      ])
    }
  },

  setCameraToMarker(position: MarkerPosition) {
    if (!TMapInstance) return
    const TMap = (window as any).TMap
    TMapInstance.setCenter(new TMap.LatLng(position.lat, position.lng))
  },

  setMapRotation(bearing: number) {
    if (!TMapInstance) return
    TMapInstance.setRotation(bearing)
    currentMapRotation.value = bearing
  },

  getMapRotation() {
    return currentMapRotation.value
  },
}

// 注册和清理（同 AMap）
onMounted(() => {
  setTimeout(() => {
    useAnimationMap().registerAdapter(animationAdapter)
  }, 100)
})

onUnmounted(() => {
  useAnimationMap().unregisterAdapter()
  // 清理动画元素
})
```

**Step 3: 提交**

```bash
git add frontend/src/components/map/BMap.vue frontend/src/components/map/TencentMap.vue
git commit -m "feat(animation): add animation support to BMap and TencentMap"
```

---

## Phase 4: 集成到轨迹详情页

### Task 4.1: 在 UniversalMap 中添加动画播放按钮

**文件:**
- 修改: `frontend/src/components/map/UniversalMap.vue`

**Step 1: 添加播放按钮和动画组件**

在模板的 `.map-controls` 中添加播放按钮：

```vue
<!-- 在 map-controls 中，全屏按钮之前添加 -->
<el-button-group size="small" class="animation-btn">
  <el-button @click="toggleAnimation" :type="isAnimationActive ? 'primary' : ''">
    <el-icon><VideoPlay /></el-icon>
  </el-button>
</el-button-group>
```

在 script 中添加：

```typescript
import { VideoPlay } from '@element-plus/icons-vue'
import { ref, computed } from 'vue'
import TrackAnimationPlayer from '@/components/animation/TrackAnimationPlayer.vue'
import type { AnimationConfig } from '@/types/animation'
import { calculateDuration } from '@/utils/animationUtils'

// 动画状态
const isAnimationActive = ref(false)

// 获取第一条轨迹的动画配置
const animationConfig = computed<AnimationConfig | null>(() => {
  if (!props.tracks || props.tracks.length === 0) return null

  const track = props.tracks[0]
  const points = track.points || []

  if (points.length < 2) return null

  // 查找有效的时间范围
  const firstPoint = points.find(p => p.time)
  const lastPoint = [...points].reverse().find(p => p.time)

  if (!firstPoint?.time || !lastPoint?.time) {
    return null
  }

  return {
    trackId: typeof track.id === 'number' ? track.id : 0,
    trackPoints: points,
    startTime: firstPoint.time,
    endTime: lastPoint.time,
    duration: calculateDuration(points),
  }
})

// 切换动画播放
function toggleAnimation() {
  isAnimationActive.value = !isAnimationActive.value
}
```

在模板末尾添加动画播放器组件：

```vue
<!-- 动画播放器 -->
<TrackAnimationPlayer
  v-if="isAnimationActive && animationConfig"
  :config="animationConfig"
  @position-change="handleAnimationPosition"
  @segment-update="handleAnimationSegment"
/>
```

**Step 2: 提交**

```bash
git add frontend/src/components/map/UniversalMap.vue
git commit -m "feat(animation): add animation toggle button to UniversalMap"
```

---

### Task 4.2: 更新 TrackDetail.vue 支持动画

**文件:**
- 修改: `frontend/src/views/TrackDetail.vue`

**Step 1: 确保地图组件正确传递轨迹数据**

检查 UniversalMap 组件的 tracks prop 是否正确传递包含完整时间信息的轨迹点数据。

**Step 2: 提交**

```bash
git add frontend/src/views/TrackDetail.vue
git commit -m "feat(animation): update TrackDetail for animation support"
```

---

## Phase 5: 视频导出功能

### Task 5.1: 创建前端视频导出工具

**文件:**
- 创建: `frontend/src/utils/animationExporter.ts`

**Step 1: 创建导出工具**

```typescript
// frontend/src/utils/animationExporter.ts

import type { ExportConfig, AnimationConfig, RESOLUTION_DIMENSIONS } from '@/types/animation'

/**
 * 前端动画视频导出器
 */
export class AnimationExporter {
  private canvas: HTMLCanvasElement
  private ctx: CanvasRenderingContext2D
  private config: ExportConfig
  private animationConfig: AnimationConfig

  constructor(
    config: ExportConfig,
    animationConfig: AnimationConfig
  ) {
    this.config = config
    this.animationConfig = animationConfig

    // 创建离屏 Canvas
    this.canvas = document.createElement('canvas')
    const { width, height } = this.getDimensions()
    this.canvas.width = width
    this.canvas.height = height

    const ctx = this.canvas.getContext('2d')
    if (!ctx) throw new Error('Failed to get 2D context')
    this.ctx = ctx
  }

  private getDimensions() {
    const dimensions: Record<string, { width: number; height: number }> = {
      '720p': { width: 1280, height: 720 },
      '1080p': { width: 1920, height: 1080 },
      '4k': { width: 3840, height: 2160 },
    }
    return dimensions[this.config.resolution]
  }

  /**
   * 导出视频
   */
  async export(
    onProgress?: (progress: number) => void
  ): Promise<Blob> {
    const { width, height } = this.getDimensions()
    const fps = this.config.fps
    const frameDuration = 1000 / fps
    const totalDuration = this.animationConfig.duration / this.config.speed

    // 创建 MediaRecorder
    const stream = this.canvas.captureStream(fps)
    const mimeType = this.getMimeType()
    const recorder = new MediaRecorder(stream, {
      mimeType,
      videoBitsPerSecond: this.getBitrate(),
    })

    const chunks: BlobPart[] = []
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) {
        chunks.push(e.data)
      }
    }

    recorder.start()

    // 逐帧渲染
    const totalFrames = Math.ceil(totalDuration / frameDuration)
    for (let frame = 0; frame < totalFrames; frame++) {
      const time = (frame * frameDuration * this.config.speed) + this.animationConfig.trackPoints[0]?.time ?
        new Date(this.animationConfig.trackPoints[0].time).getTime() :
        0

      // 清空画布
      this.ctx.fillStyle = '#f0f0f0'
      this.ctx.fillRect(0, 0, width, height)

      // 绘制地图内容（需要地图组件支持）
      await this.drawMapFrame(time)

      // 绘制 HUD
      if (this.config.showHUD) {
        this.drawHUD(time, totalDuration)
      }

      // 进度回调
      onProgress?.((frame / totalFrames) * 100)

      // 等待一帧
      await this.waitFrame(fps)
    }

    // 停止录制
    recorder.stop()

    return new Promise<Blob>((resolve) => {
      recorder.onstop = () => {
        const blob = new Blob(chunks, { type: mimeType })
        resolve(blob)
      }
    })
  }

  private getMimeType(): string {
    if (this.config.format === 'mp4' && MediaRecorder.isTypeSupported('video/mp4')) {
      return 'video/mp4'
    }
    return 'video/webm;codecs=vp9'
  }

  private getBitrate(): number {
    const bitrates: Record<string, number> = {
      '720p': 5000000,      // 5 Mbps
      '1080p': 10000000,    // 10 Mbps
      '4k': 30000000,       // 30 Mbps
    }
    return bitrates[this.config.resolution] || 10000000
  }

  private async drawMapFrame(time: number): Promise<void> {
    // TODO: 从地图组件获取当前帧
    // 这需要地图组件支持截图功能
    // 可以使用 captureMap() 方法
  }

  private drawHUD(currentTime: number, totalDuration: number): void {
    const { width } = this.getDimensions()

    // 绘制进度条背景
    const padding = 20
    const barWidth = width - padding * 2
    const barHeight = 6
    const barY = this.canvas.height - 40

    this.ctx.fillStyle = 'rgba(0, 0, 0, 0.3)'
    this.ctx.beginPath()
    this.ctx.roundRect(padding, barY, barWidth, barHeight, 3)
    this.ctx.fill()

    // 绘制进度
    const progress = currentTime / totalDuration
    this.ctx.fillStyle = '#409eff'
    this.ctx.beginPath()
    this.ctx.roundRect(padding, barY, barWidth * progress, barHeight, 3)
    this.ctx.fill()
  }

  private waitFrame(fps: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, 1000 / fps))
  }

  /**
   * 取消导出
   */
  cancel(): void {
    // 清理资源
  }
}

/**
 * 导出辅助函数
 */
export async function exportAnimationVideo(
  config: ExportConfig,
  animationConfig: AnimationConfig,
  onProgress?: (progress: number) => void
): Promise<Blob> {
  const exporter = new AnimationExporter(config, animationConfig)
  return exporter.export(onProgress)
}
```

**Step 2: 提交**

```bash
git add frontend/src/utils/animationExporter.ts
git commit -m "feat(animation): add frontend video exporter"
```

---

### Task 5.2: 创建导出对话框组件

**文件:**
- 创建: `frontend/src/components/animation/AnimationExportDialog.vue`

**Step 1: 创建导出对话框**

```vue
<!-- frontend/src/components/animation/AnimationExportDialog.vue -->
<template>
  <el-dialog
    v-model="visible"
    title="导出动画视频"
    width="500px"
    @close="handleClose"
  >
    <el-form :model="form" label-width="100px">
      <el-form-item label="导出方式">
        <el-radio-group v-model="form.exportMethod">
          <el-radio value="frontend">浏览器导出</el-radio>
          <el-radio value="backend">服务器导出</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="分辨率">
        <el-select v-model="form.resolution">
          <el-option label="720P (1280×720)" value="720p" />
          <el-option label="1080P (1920×1080)" value="1080p" />
          <el-option label="4K (3840×2160)" value="4k" />
        </el-select>
      </el-form-item>

      <el-form-item label="帧率">
        <el-radio-group v-model="form.fps">
          <el-radio :label="30">30 fps</el-radio>
          <el-radio :label="60">60 fps</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="显示控制面板">
        <el-switch v-model="form.showHUD" />
      </el-form-item>

      <el-form-item label="视频格式">
        <el-select v-model="form.format">
          <el-option label="WebM" value="webm" />
          <el-option label="MP4" value="mp4" />
        </el-select>
      </el-form-item>

      <el-form-item label="导出倍速">
        <el-slider
          v-model="form.speed"
          :min="0.5"
          :max="32"
          :step="0.5"
          :marks="{ 1: '1x', 2: '2x', 4: '4x', 8: '8x', 16: '16x' }"
          show-stops
        />
      </el-form-item>
    </el-form>

    <div v-if="exporting" class="export-progress">
      <el-progress :percentage="exportProgress" />
      <p class="progress-text">正在导出... {{ exportProgress.toFixed(0) }}%</p>
    </div>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button
        type="primary"
        :loading="exporting"
        :disabled="exporting"
        @click="handleExport"
      >
        {{ exporting ? '导出中...' : '开始导出' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import type { ExportConfig, AnimationConfig } from '@/types/animation'
import { exportAnimationVideo } from '@/utils/animationExporter'

interface Props {
  modelValue: boolean
  animationConfig: AnimationConfig
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()

const visible = ref(props.modelValue)
const exporting = ref(false)
const exportProgress = ref(0)

const form = ref({
  exportMethod: 'frontend',
  resolution: '1080p' as const,
  fps: 30 as 30 | 60,
  showHUD: true,
  format: 'webm' as 'webm' | 'mp4',
  speed: 1.0,
})

watch(() => props.modelValue, (val) => {
  visible.value = val
})

watch(visible, (val) => {
  emit('update:modelValue', val)
})

async function handleExport() {
  exporting.value = true
  exportProgress.value = 0

  try {
    const config: ExportConfig = {
      resolution: form.value.resolution,
      fps: form.value.fps,
      showHUD: form.value.showHUD,
      format: form.value.format,
      speed: form.value.speed,
    }

    if (form.value.exportMethod === 'frontend') {
      // 前端导出
      const blob = await exportAnimationVideo(
        config,
        props.animationConfig,
        (progress) => {
          exportProgress.value = progress
        }
      )

      // 下载文件
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `animation_${Date.now()}.${form.value.format}`
      a.click()
      URL.revokeObjectURL(url)
    } else {
      // 后端导出（后续实现）
      console.log('Backend export not implemented yet')
    }
  } catch (error) {
    console.error('Export failed:', error)
  } finally {
    exporting.value = false
  }
}

function handleClose() {
  if (exporting.value) return
  visible.value = false
}
</script>

<style scoped>
.export-progress {
  margin-top: 20px;
}

.progress-text {
  margin-top: 10px;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}
</style>
```

**Step 2: 提交**

```bash
git add frontend/src/components/animation/AnimationExportDialog.vue
git commit -m "feat(animation): add AnimationExportDialog component"
```

---

## Phase 6: 后端视频导出 API

### Task 6.1: 创建后端 Schema

**文件:**
- 创建: `backend/app/schemas/animation.py`

**Step 1: 创建动画 Schema**

```python
# backend/app/schemas/animation.py

from pydantic import BaseModel, Field
from typing import Literal, Optional

class AnimationExportRequest(BaseModel):
    """动画导出请求"""
    resolution: Literal['720p', '1080p', '4k'] = '1080p'
    fps: Literal[30, 60] = 30
    show_hud: bool = True
    format: Literal['webm', 'mp4'] = 'mp4'
    speed: float = Field(default=1.0, ge=0.25, le=32.0)

class AnimationExportStatus(BaseModel):
    """动画导出状态"""
    task_id: str
    status: Literal['pending', 'processing', 'completed', 'failed']
    progress: float = 0.0  # 0-100
    error: Optional[str] = None
    download_url: Optional[str] = None
```

**Step 2: 提交**

```bash
git add backend/app/schemas/animation.py
git commit -m "feat(animation): add animation schemas"
```

---

### Task 6.2: 创建动画导出服务

**文件:**
- 创建: `backend/app/services/animation_service.py`

**Step 1: 创建动画服务**

```python
# backend/app/services/animation_service.py

import asyncio
import uuid
from pathlib import Path
from loguru import logger
from typing import Optional

try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright 未安装，动画导出功能不可用")

from app.schemas.animation import AnimationExportRequest, AnimationExportStatus


class AnimationService:
    """动画导出服务"""

    def __init__(self):
        self._browser: Optional[Browser] = None
        self._tasks: dict[str, AnimationExportStatus] = {}

    async def get_browser(self) -> Optional[Browser]:
        """获取浏览器实例"""
        if not PLAYWRIGHT_AVAILABLE:
            return None

        if self._browser is None:
            try:
                playwright = await async_playwright().start()
                self._browser = await playwright.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                    ]
                )
                logger.info("Playwright 浏览器启动成功")
            except Exception as e:
                logger.error(f"Playwright 浏览器启动失败: {e}")
                return None

        return self._browser

    async def create_export_task(
        self,
        track_id: int,
        config: AnimationExportRequest,
        base_url: str = "http://localhost:5173"
    ) -> str:
        """创建导出任务"""
        task_id = str(uuid.uuid4())

        # 初始化任务状态
        self._tasks[task_id] = AnimationExportStatus(
            task_id=task_id,
            status='pending',
            progress=0.0
        )

        # 启动后台任务
        asyncio.create_task(self._execute_export(
            task_id, track_id, config, base_url
        ))

        return task_id

    async def _execute_export(
        self,
        task_id: str,
        track_id: int,
        config: AnimationExportRequest,
        base_url: str
    ):
        """执行导出任务"""
        status = self._tasks[task_id]
        status.status = 'processing'

        try:
            browser = await self.get_browser()
            if not browser:
                raise Exception("Playwright 不可用")

            # 计算视频尺寸
            dimensions = {
                '720p': (1280, 720),
                '1080p': (1920, 1080),
                '4k': (3840, 2160),
            }
            width, height = dimensions[config.resolution]

            # 创建页面
            page = await browser.new_page(
                viewport={'width': width, 'height': height},
                record_video_dir=Path(f'backend/data/exports/{task_id}'),
                record_video_size={'width': width, 'height': height}
            )

            # 访问动画页面
            animation_url = f"{base_url}/tracks/{track_id}/animation-only"
            await page.goto(animation_url)

            # 等待地图加载
            await page.wait_for_selector('.map-container', timeout=30000)

            # 设置导出配置
            await page.evaluate(f'''
                window.startAnimationExport({{
                    resolution: "{config.resolution}",
                    fps: {config.fps},
                    showHUD: {str(config.showHUD).lower()},
                    speed: {config.speed}
                }})
            ''')

            # 等待动画完成
            duration = await page.evaluate('window.animationDuration')
            await asyncio.sleep(duration / config.speed + 2)  # 额外缓冲时间

            # 停止录制
            await page.close()

            # 更新状态
            status.status = 'completed'
            status.progress = 100.0
            status.download_url = f'/api/tracks/{track_id}/animation/export/download/{task_id}'

        except Exception as e:
            logger.error(f"导出任务失败: {e}")
            status.status = 'failed'
            status.error = str(e)

    def get_task_status(self, task_id: str) -> Optional[AnimationExportStatus]:
        """获取任务状态"""
        return self._tasks.get(task_id)


# 全局实例
animation_service = AnimationService()
```

**Step 2: 提交**

```bash
git add backend/app/services/animation_service.py
git commit -m "feat(animation): add animation export service"
```

---

### Task 6.3: 创建动画 API 路由

**文件:**
- 创建: `backend/app/api/animation.py`
- 修改: `backend/app/main.py`

**Step 1: 创建动画路由**

```python
# backend/app/api/animation.py

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path

from app.api.auth import get_current_user
from app.models.user import User
from app.schemas.animation import AnimationExportRequest, AnimationExportStatus
from app.services.animation_service import animation_service

router = APIRouter(prefix="/tracks/{track_id}/animation", tags=["animation"])


@router.post("/export")
async def create_export_task(
    track_id: int,
    config: AnimationExportRequest,
    current_user: User = Depends(get_current_user)
):
    """创建动画导出任务"""
    task_id = await animation_service.create_export_task(
        track_id=track_id,
        config=config
    )
    return {"task_id": task_id}


@router.get("/export/status/{task_id}")
async def get_export_status(
    task_id: str,
    current_user: User = Depends(get_current_user)
) -> AnimationExportStatus:
    """查询导出任务状态"""
    status = animation_service.get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="任务不存在")
    return status


@router.get("/export/download/{task_id}")
async def download_exported_video(
    track_id: int,
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    """下载已完成的视频"""
    status = animation_service.get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="任务不存在")

    if status.status != 'completed':
        raise HTTPException(status_code=400, detail="任务尚未完成")

    video_path = Path(f'backend/data/exports/{task_id}.webm')
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    return FileResponse(
        video_path,
        media_type='video/webm',
        filename=f'animation_{track_id}.webm'
    )
```

**Step 2: 在 main.py 中注册路由**

```python
# 在 backend/app/main.py 中添加导入
from app.api import animation

# 在 create_app 中注册路由
app.include_router(animation.router)
```

**Step 3: 提交**

```bash
git add backend/app/api/animation.py backend/app/main.py
git commit -m "feat(animation): add animation API routes"
```

---

## Phase 7: 测试与完善

### Task 7.1: 添加动画页面路由

**文件:**
- 修改: `frontend/src/router/index.ts`

**Step 1: 添加动画专用页面路由（如果需要单独页面）**

如果需要单独的动画页面，添加路由。否则跳过此步骤。

**Step 2: 提交**

```bash
git add frontend/src/router/index.ts
git commit -m "feat(animation): add animation route"
```

---

### Task 7.2: 在分享页面添加动画支持

**文件:**
- 修改: `frontend/src/views/SharedTrack.vue`

**Step 1: 添加动画播放按钮和组件**

参考 TrackDetail.vue 的实现，在 SharedTrack.vue 中添加动画支持。

**Step 2: 提交**

```bash
git add frontend/src/views/SharedTrack.vue
git commit -m "feat(animation): add animation support to SharedTrack"
```

---

### Task 7.3: 添加动画专用页面（用于导出）

**文件:**
- 创建: `frontend/src/views/TrackAnimationOnly.vue`

**Step 1: 创建专用动画页面**

```vue
<!-- frontend/src/views/TrackAnimationOnly.vue -->
<template>
  <div class="track-animation-only">
    <div class="map-container">
      <UniversalMap
        ref="mapRef"
        :tracks="[trackWithPoints]"
        :mode="'detail'"
      />
      <TrackAnimationPlayer
        v-if="animationConfig && isExporting"
        :config="animationConfig"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import UniversalMap from '@/components/map/UniversalMap.vue'
import TrackAnimationPlayer from '@/components/animation/TrackAnimationPlayer.vue'
import { trackApi } from '@/api/track'
import type { AnimationConfig } from '@/types/animation'
import { calculateDuration } from '@/utils/animationUtils'

const route = useRoute()
const mapRef = ref()
const trackWithPoints = ref(null)
const isExporting = ref(false)

const animationConfig = computed<AnimationConfig | null>(() => {
  if (!trackWithPoints.value?.points) return null

  const points = trackWithPoints.value.points
  const firstPoint = points.find((p: any) => p.time)
  const lastPoint = [...points].reverse().find((p: any) => p.time)

  if (!firstPoint?.time || !lastPoint?.time) return null

  return {
    trackId: trackWithPoints.value.id,
    trackPoints: points,
    startTime: firstPoint.time,
    endTime: lastPoint.time,
    duration: calculateDuration(points),
  }
})

onMounted(async () => {
  const trackId = Number(route.params.id)
  const data = await trackApi.getPoints(trackId)
  trackWithPoints.value = {
    id: trackId,
    points: data.points,
  }

  // 设置全局标志
  ;(window as any).mapReady = true
  ;(window as any).animationDuration = animationConfig.value?.duration || 0
})

// 全局导出函数
;(window as any).startAnimationExport = (config: any) => {
  isExporting.value = true
  return Promise.resolve()
}
</script>

<style scoped>
.track-animation-only {
  width: 100vw;
  height: 100vh;
  overflow: hidden;
}

.map-container {
  width: 100%;
  height: 100%;
}
</style>
```

**Step 2: 添加路由**

```typescript
{
  path: '/tracks/:id/animation-only',
  name: 'TrackAnimationOnly',
  component: () => import('@/views/TrackAnimationOnly.vue'),
  meta: { requiresAuth: true }
}
```

**Step 3: 提交**

```bash
git add frontend/src/views/TrackAnimationOnly.vue
git commit -m "feat(animation): add TrackAnimationOnly page for export"
```

---

## Phase 8: 文档与收尾

### Task 8.1: 更新设计文档

**文件:**
- 修改: `docs/plans/2026-02-10-track-animation-design.md`

**Step 1: 标记实施完成**

在设计文档末尾添加：

```markdown
## 实施状态

- [x] Phase 1: 基础类型和工具函数
- [x] Phase 2: 核心播放器组件
- [x] Phase 3: 地图动画混入
- [x] Phase 4: 集成到轨迹详情页
- [x] Phase 5: 视频导出功能
- [x] Phase 6: 后端视频导出 API
- [x] Phase 7: 测试与完善
- [x] Phase 8: 文档与收尾

**实施完成日期**: 2026-02-10
```

**Step 2: 提交**

```bash
git add docs/plans/2026-02-10-track-animation-design.md
git commit -m "docs(animation): mark implementation as complete"
```

---

### Task 8.2: 最终提交

**Step 1: 查看所有更改**

```bash
git status
```

**Step 2: 创建最终汇总提交**

```bash
git add -A
git commit -m "feat(animation): complete track animation feature implementation

This commit adds the complete track animation feature including:
- Animation playback with multiple speed options (0.25x - 16x)
- Dual-color track display (passed/remaining)
- Moving marker with direction arrow
- Camera modes: full view / fixed center
- Orientation modes: north-up / track-up
- Frontend and backend video export
- Local storage for user preferences

Related files:
- frontend/src/types/animation.ts
- frontend/src/utils/animationUtils.ts
- frontend/src/stores/animation.ts
- frontend/src/components/animation/
- frontend/src/composables/animation/
- frontend/src/components/map/*.vue (animation support)
- backend/app/api/animation.py
- backend/app/schemas/animation.py
- backend/app/services/animation_service.py"
```

---

## 附录：测试检查清单

### 功能测试

- [ ] 播放/暂停按钮正常工作
- [ ] 进度条拖动更新位置
- [ ] 倍速切换正确生效
- [ ] 画面模式切换（全轨迹/固定中心）
- [ ] 朝向模式切换（正北/轨迹）
- [ ] 信息浮层显示正确
- [ ] 标记样式切换
- [ ] 视频导出（前端）
- [ ] 视频导出（后端）
- [ ] 本地存储持久化

### 兼容性测试

- [ ] 高德地图
- [ ] 百度地图 GL
- [ ] 百度地图 Legacy
- [ ] 腾讯地图
- [ ] Leaflet（天地图/OSM）

### 边界情况测试

- [ ] 空轨迹（0 个点）
- [ ] 单点轨迹（1 个点）
- [ ] 无时间数据的轨迹
- [ ] 无 bearing 数据的轨迹
- [ ] 超长轨迹（>2000 点）
- [ ] 超短视频导出（<10 秒）
- [ ] 超长视频导出（>10 分钟）

### 性能测试

- [ ] 500 点轨迹播放流畅
- [ ] 2000 点轨迹播放流畅
- [ ] 5000 点轨迹播放流畅（采样优化）
- [ ] 前端导出内存占用正常
