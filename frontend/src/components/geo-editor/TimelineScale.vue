<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useGeoEditorStore } from '@/stores/geoEditor'

interface Props {
  points: any[]
  zoomStart: number
  zoomEnd: number
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'pointer-change': [position: number]
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

function handleScaleClick(e: MouseEvent) {
  if (!scaleRef.value) return
  const rect = scaleRef.value.getBoundingClientRect()
  const x = e.clientX - rect.left
  const position = x / rect.width

  // 转换为全局位置
  const globalPosition = props.zoomStart + position * (props.zoomEnd - props.zoomStart)
  emit('pointer-change', globalPosition)
}
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
</style>
