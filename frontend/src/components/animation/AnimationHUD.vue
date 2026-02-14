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
          @update:model-value="handleSeek"
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
import { ref, computed } from 'vue'
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

.hud-progress :deep(.el-slider) {
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
