<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useGeoEditorStore } from '@/stores/geoEditor'

interface Props {
  points: any[]
  zoomStart: number
  zoomEnd: number
  pointerPosition: number
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'pointer-change': [position: number]
  'pointer-drag-start': []
  'pointer-drag-end': []
}>()

const geoEditorStore = useGeoEditorStore()
const scaleRef = ref<HTMLElement>()

// 计算时间刻度
const ticks = computed(() => {
  if (props.points.length === 0) return []

  const startTime = props.points[0]?.time ? new Date(props.points[0].time).getTime() : 0
  const endTime = props.points[props.points.length - 1]?.time
    ? new Date(props.points[props.points.length - 1].time).getTime()
    : startTime + 3600000

  const totalDuration = endTime - startTime || 3600000
  const visibleStart = startTime + totalDuration * props.zoomStart
  const visibleEnd = startTime + totalDuration * props.zoomEnd
  const visibleDuration = visibleEnd - visibleStart

  // 根据可见时长决定刻度间隔
  let interval: number
  if (visibleDuration <= 60000) {
    interval = 10000 // 10秒
  } else if (visibleDuration <= 300000) {
    interval = 30000 // 30秒
  } else if (visibleDuration <= 600000) {
    interval = 60000 // 1分钟
  } else if (visibleDuration <= 3600000) {
    interval = 300000 // 5分钟
  } else {
    interval = 600000 // 10分钟
  }

  // 计算刻度
  const result: Array<{ position: number; time: string; isMajor: boolean }> = []

  // 对齐到 interval
  const firstTickTime = Math.ceil(visibleStart / interval) * interval

  for (let t = firstTickTime; t <= visibleEnd; t += interval) {
    const relativeTime = t - startTime
    const position = relativeTime / totalDuration

    if (position >= props.zoomStart && position <= props.zoomEnd) {
      const date = new Date(t)
      const hours = String(date.getHours()).padStart(2, '0')
      const minutes = String(date.getMinutes()).padStart(2, '0')
      const seconds = String(date.getSeconds()).padStart(2, '0')
      const timeStr = `${hours}:${minutes}:${seconds}`

      result.push({
        position: (position - props.zoomStart) / (props.zoomEnd - props.zoomStart),
        time: timeStr,
        isMajor: true,
      })

      // 添加次刻度（5个）
      const minorInterval = interval / 6
      for (let i = 1; i < 6; i++) {
        const minorTime = t + minorInterval * i
        const minorPosition = (minorTime - startTime) / totalDuration
        if (minorPosition <= props.zoomEnd) {
          result.push({
            position: (minorPosition - props.zoomStart) / (props.zoomEnd - props.zoomStart),
            time: '',
            isMajor: false,
          })
        }
      }
    }
  }

  return result
})

// 指针拖动
const isDragging = ref(false)

function handleScaleClick(e: MouseEvent) {
  if (!scaleRef.value) return
  const rect = scaleRef.value.getBoundingClientRect()
  const x = e.clientX - rect.left
  const position = x / rect.width

  // 转换为全局位置
  const globalPosition = props.zoomStart + position * (props.zoomEnd - props.zoomStart)
  emit('pointer-change', globalPosition)
}

function handlePointerMouseDown(e: MouseEvent) {
  e.stopPropagation()
  isDragging.value = true
  emit('pointer-drag-start')

  const handleMouseMove = (e: MouseEvent) => {
    if (!scaleRef.value || !isDragging.value) return
    const rect = scaleRef.value.getBoundingClientRect()
    const x = Math.max(0, Math.min(rect.width, e.clientX - rect.left))
    const position = x / rect.width
    const globalPosition = props.zoomStart + position * (props.zoomEnd - props.zoomStart)
    emit('pointer-change', globalPosition)
  }

  const handleMouseUp = () => {
    isDragging.value = false
    emit('pointer-drag-end')
    window.removeEventListener('mousemove', handleMouseMove)
    window.removeEventListener('mouseup', handleMouseUp)
  }

  window.addEventListener('mousemove', handleMouseMove)
  window.addEventListener('mouseup', handleMouseUp)
}

// 计算指针位置（相对于可见区域）
const pointerVisiblePosition = computed(() => {
  const globalPos = props.pointerPosition
  if (globalPos < props.zoomStart || globalPos > props.zoomEnd) return null
  return (globalPos - props.zoomStart) / (props.zoomEnd - props.zoomStart)
})

// 格式化指针时间
const pointerTime = computed(() => {
  if (props.points.length === 0) return '--:--:--'
  const startTime = props.points[0]?.time ? new Date(props.points[0].time).getTime() : 0
  const endTime = props.points[props.points.length - 1]?.time
    ? new Date(props.points[props.points.length - 1].time).getTime()
    : startTime + 3600000
  const totalDuration = endTime - startTime || 3600000

  const pointerTimeMs = startTime + totalDuration * props.pointerPosition
  const date = new Date(pointerTimeMs)
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')
  return `${hours}:${minutes}:${seconds}`
})
</script>

<template>
  <div class="timeline-scale" ref="scaleRef" @click="handleScaleClick">
    <!-- 刻度 -->
    <div
      v-for="(tick, index) in ticks"
      :key="index"
      class="tick"
      :class="{ 'tick-major': tick.isMajor, 'tick-minor': !tick.isMajor }"
      :style="{ left: `${tick.position * 100}%` }"
    >
      <div v-if="tick.isMajor" class="tick-label">{{ tick.time }}</div>
    </div>

    <!-- 指针 -->
    <div
      v-if="pointerVisiblePosition !== null"
      class="playhead"
      :style="{ left: `${pointerVisiblePosition * 100}%` }"
      @mousedown="handlePointerMouseDown"
    >
      <div class="playhead-line"></div>
      <div class="playhead-top"></div>
      <div class="playhead-bottom"></div>
      <div class="playhead-time">{{ pointerTime }}</div>
    </div>
  </div>
</template>

<style scoped>
.timeline-scale {
  position: relative;
  width: 100%;
  height: 32px;
  background: var(--el-bg-color-page);
  border-bottom: 1px solid var(--el-border-color-lighter);
  cursor: crosshair;
  user-select: none;
}

.tick {
  position: absolute;
  top: 0;
  bottom: 0;
  pointer-events: none;
}

.tick-major {
  border-left: 1px solid var(--el-border-color);
}

.tick-major::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 1px;
  height: 8px;
  background: var(--el-text-color-secondary);
}

.tick-minor {
  border-left: 1px solid transparent;
}

.tick-minor::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 1px;
  height: 4px;
  background: var(--el-border-color-darker);
}

.tick-label {
  position: absolute;
  top: 10px;
  left: 4px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

.playhead {
  position: absolute;
  top: 0;
  bottom: 0;
  z-index: 10;
  cursor: ew-resize;
  pointer-events: auto;
}

.playhead-line {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 2px;
  background: #f56c6c;
  transform: translateX(-1px);
}

.playhead-top,
.playhead-bottom {
  position: absolute;
  left: -5px;
  width: 0;
  height: 0;
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
}

.playhead-top {
  top: 0;
  border-top: 8px solid #f56c6c;
}

.playhead-bottom {
  bottom: 0;
  border-bottom: 8px solid #f56c6c;
}

.playhead-time {
  position: absolute;
  top: -20px;
  left: 50%;
  transform: translateX(-50%);
  background: #f56c6c;
  color: white;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
  white-space: nowrap;
}
</style>
