<!-- frontend/src/components/animation/AnimationHUD.vue -->
<template>
  <div class="animation-hud" :class="{ 'animation-hud-mobile': isMobile }">
    <div ref="hudContentRef" class="hud-content">
      <!-- 移动端信息显示（在进度条上方） -->
      <div v-if="props.showInfoPanel && props.position" class="hud-info-mobile">
        <span class="info-time">{{ formatPositionTime(props.position.time) }}</span>
        <span class="info-separator">•</span>
        <span class="info-speed">{{ formatSpeed(props.position.speed) }}</span>
        <span class="info-separator">•</span>
        <span class="info-elevation">{{ formatElevation(props.position.elevation) }}</span>
      </div>

      <!-- 第一行：进度条 -->
      <div class="hud-row hud-progress">
        <el-slider
          :model-value="progressPercent"
          :format-tooltip="formatProgressTooltip"
          :popper-class="'slider-tooltip-high-zindex'"
          @update:model-value="handleSeek"
        />
        <div class="time-display">
          {{ formatTime(currentTime) }} / {{ formatTime(totalDuration) }}
        </div>
      </div>

      <!-- 第二行：播放控制 + 倍速 + 功能按钮 -->
      <div class="hud-row hud-controls">
        <el-button
          :icon="isPlaying ? VideoPause : VideoPlay"
          size="small"
          @click="$emit('toggle-play')"
        />
        <div class="speed-display" @click="showSpeedMenu = !showSpeedMenu">
          {{ playbackSpeed }}x
        </div>
        <div class="divider" />
        <el-tooltip :content="cameraModeTooltip">
          <el-button
            :icon="getCameraModeIcon()"
            size="small"
            @click="$emit('toggle-camera-mode')"
          />
        </el-tooltip>
        <el-tooltip v-if="!isMobile" content="信息浮层">
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
            <el-icon v-if="props.markerStyle === 'arrow'"><ArrowDown /></el-icon>
            <el-icon v-else-if="props.markerStyle === 'car'"><Van /></el-icon>
            <el-icon v-else><User /></el-icon>
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
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import {
  VideoPlay,
  VideoPause,
  Location,
  Film,
  Monitor,
  Aim,
  ArrowDown,
  Van,
  User,
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
  position?: {
    time: string | null
    speed: number | null
    elevation: number | null
  } | null
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
  (e: 'height-changed', height: number): void
}>()

const SPEED_OPTIONS = [0.25, 0.5, 1, 2, 4, 8, 16] as const
const showSpeedMenu = ref(false)
const hudContentRef = ref<HTMLElement | null>(null)

// 计算 HUD 高度并 emit
function emitHeight() {
  if (hudContentRef.value) {
    const height = hudContentRef.value.offsetHeight
    emit('height-changed', height)
  }
}

onMounted(() => {
  // 初始计算高度
  emitHeight()

  // 监听尺寸变化（比如倍速菜单展开/收起）
  if (hudContentRef.value) {
    const resizeObserver = new ResizeObserver(() => {
      emitHeight()
    })
    resizeObserver.observe(hudContentRef.value)

    onUnmounted(() => {
      resizeObserver.disconnect()
    })
  }
})

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

function handleSeek(value: number | number[]) {
  // 防止无效的 seek 值
  const numValue = Array.isArray(value) ? value[0] : value
  if (numValue === undefined || isNaN(numValue) || numValue < 0 || numValue > 100 || props.totalDuration <= 0) {
    return
  }
  const time = (props.totalDuration * numValue) / 100
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

// 检测是否为移动端
const isMobile = computed(() => window.innerWidth <= 1366)

// 格式化位置信息的时间
function formatPositionTime(time: string | null): string {
  if (!time) return '--:--:--'
  return new Date(time).toLocaleTimeString('zh-CN', { hour12: false })
}

// 格式化速度
function formatSpeed(speed: number | null): string {
  if (speed === null) return '-- km/h'
  return `${(speed * 3.6).toFixed(1)} km/h`
}

// 格式化海拔
function formatElevation(elevation: number | null): string {
  if (elevation === null) return '--m'
  return `${elevation.toFixed(0)}m`
}
</script>

<style scoped>
/* 桌面端 HUD 容器 */
.animation-hud {
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10000;
}

/* 移动端 HUD 容器 */
.animation-hud-mobile {
  position: static;
  transform: none;
  z-index: auto;
}

.hud-content {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 8px;
  padding: 12px 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
  min-width: 280px;
}

.animation-hud-mobile .hud-content {
  background: #fff;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 4px;
  padding: 12px 16px;
  box-shadow: none;
  min-width: 100%;
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
  justify-content: center;
}

/* 移动端信息显示 */
.hud-info-mobile {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.95);
  color: var(--el-text-color-primary);
  border-radius: 6px;
  font-size: 13px;
  white-space: nowrap;
  margin-bottom: 8px;
  border: 1px solid var(--el-border-color-lighter);
}

.info-time {
  font-weight: 500;
  color: var(--el-color-primary);
}

.info-speed,
.info-elevation {
  opacity: 0.9;
}

.info-separator {
  opacity: 0.6;
}

.divider {
  width: 1px;
  height: 16px;
  background-color: var(--el-border-color-lighter);
  margin: 0 4px;
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
  align-items: center;
  flex: 1;
}

.hud-progress :deep(.el-slider) {
  margin: 0;
  flex: 1;
}

/* 进度条 tooltip 高层级 */
.slider-tooltip-high-zindex {
  z-index: 20000 !important;
}

.time-display {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  min-width: 100px;
  text-align: center;
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

<style>
/* 非 scoped 样式：全局设置进度条 tooltip 的 z-index */
.slider-tooltip-high-zindex {
  z-index: 20000 !important;
}
</style>
