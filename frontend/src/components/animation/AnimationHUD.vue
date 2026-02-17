<!-- frontend/src/components/animation/AnimationHUD.vue -->
<template>
  <div class="animation-hud">
    <div class="hud-content" ref="hudContentRef">
      <!-- 第一行：进度条 -->
      <div class="hud-row hud-progress">
        <el-slider
          :model-value="progressPercent"
          :format-tooltip="formatProgressTooltip"
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
import { ref, computed, onMounted, onUnmounted } from 'vue'
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
</script>

<style scoped>
.animation-hud {
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10000;
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
  justify-content: center;
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
