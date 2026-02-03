<script setup lang="ts">
import { ref, computed } from 'vue'

interface Props {
  points: any[]
  zoomStart: number
  zoomEnd: number
  timeScaleUnit?: 'time' | 'duration' | 'index'
}

const props = withDefaults(defineProps<Props>(), {
  timeScaleUnit: 'time',
})

const emit = defineEmits<{
  'pointer-change': [position: number]
}>()

const scaleRef = ref<HTMLElement>()

// 格式化时长
function formatDuration(ms: number): string {
  const seconds = Math.floor(ms / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)

  if (hours > 0) {
    const mins = minutes % 60
    return `${hours}:${String(mins).padStart(2, '0')}`
  } else if (minutes > 0) {
    const secs = seconds % 60
    return `${minutes}:${String(secs).padStart(2, '0')}`
  } else {
    return `${seconds}s`
  }
}

// 计算刻度
const ticks = computed(() => {
  if (props.points.length === 0) return []

  const totalPoints = props.points.length
  const startTime = props.points[0]?.time ? new Date(props.points[0].time).getTime() : 0
  const endTime = props.points[props.points.length - 1]?.time
    ? new Date(props.points[props.points.length - 1].time).getTime()
    : startTime + 3600000
  const totalDuration = endTime - startTime || 3600000

  const visibleStart = startTime + totalDuration * props.zoomStart
  const visibleEnd = startTime + totalDuration * props.zoomEnd
  const visibleDuration = visibleEnd - visibleStart
  const visibleStartIndex = Math.floor(totalPoints * props.zoomStart)
  const visibleEndIndex = Math.ceil(totalPoints * props.zoomEnd)
  const visibleCount = visibleEndIndex - visibleStartIndex

  const result: Array<{ position: number; label: string; isMajor: boolean }> = []

  // 根据单位决定刻度间隔
  if (props.timeScaleUnit === 'time') {
    // 时间模式：根据可见时长决定间隔
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

    const firstTickTime = Math.ceil(visibleStart / interval) * interval

    for (let t = firstTickTime; t <= visibleEnd; t += interval) {
      const relativeTime = t - startTime
      const position = relativeTime / totalDuration

      if (position >= props.zoomStart && position <= props.zoomEnd) {
        const date = new Date(t)
        const hours = String(date.getHours()).padStart(2, '0')
        const minutes = String(date.getMinutes()).padStart(2, '0')
        const seconds = String(date.getSeconds()).padStart(2, '0')
        const label = `${hours}:${minutes}:${seconds}`

        result.push({
          position: (position - props.zoomStart) / (props.zoomEnd - props.zoomStart),
          label,
          isMajor: true,
        })
      }
    }
  } else if (props.timeScaleUnit === 'duration') {
    // 时长模式
    let interval: number
    if (visibleDuration <= 60000) {
      interval = 10000 // 10秒
    } else if (visibleDuration <= 300000) {
      interval = 60000 // 1分钟
    } else if (visibleDuration <= 3600000) {
      interval = 300000 // 5分钟
    } else {
      interval = 600000 // 10分钟
    }

    const firstTickTime = Math.ceil(visibleStart / interval) * interval

    for (let t = firstTickTime; t <= visibleEnd; t += interval) {
      const relativeTime = t - startTime
      const position = relativeTime / totalDuration

      if (position >= props.zoomStart && position <= props.zoomEnd) {
        result.push({
          position: (position - props.zoomStart) / (props.zoomEnd - props.zoomStart),
          label: formatDuration(t - startTime),
          isMajor: true,
        })
      }
    }
  } else {
    // 索引模式
    let interval: number
    if (visibleCount <= 100) {
      interval = 10
    } else if (visibleCount <= 500) {
      interval = 50
    } else if (visibleCount <= 1000) {
      interval = 100
    } else {
      interval = 500
    }

    const firstTickIndex = Math.ceil(visibleStartIndex / interval) * interval

    for (let idx = firstTickIndex; idx <= visibleEndIndex; idx += interval) {
      const position = idx / totalPoints

      if (position >= props.zoomStart && position <= props.zoomEnd) {
        result.push({
          position: (position - props.zoomStart) / (props.zoomEnd - props.zoomStart),
          label: String(idx),
          isMajor: true,
        })
      }
    }
  }

  return result
})

function handleScaleClick(e: MouseEvent) {
  if (!scaleRef.value) return
  const rect = scaleRef.value.getBoundingClientRect()

  // 点击位置相对于内容区域（从标签区域后开始）
  const LABEL_WIDTH = 65
  const x = Math.max(0, e.clientX - rect.left - LABEL_WIDTH)
  const contentWidth = rect.width - LABEL_WIDTH
  const position = x / contentWidth

  // 转换为全局位置
  const globalPosition = props.zoomStart + position * (props.zoomEnd - props.zoomStart)
  emit('pointer-change', globalPosition)
}
</script>

<template>
  <div class="timeline-scale" ref="scaleRef" @click="handleScaleClick">
    <!-- 刻度容器（包含标签区域和内容区域） -->
    <div class="scale-content">
      <!-- 刻度 -->
      <div
        v-for="(tick, index) in ticks"
        :key="index"
        class="tick"
        :class="{ 'tick-major': tick.isMajor }"
        :style="{ left: `${tick.position * 100}%` }"
      >
        <div v-if="tick.isMajor && tick.label" class="tick-label">{{ tick.label }}</div>
      </div>
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

.scale-content {
  position: relative;
  width: 100%;
  height: 100%;
  padding-left: 65px;  /* 标签区域宽度 */
  box-sizing: border-box;
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

.tick-label {
  position: absolute;
  top: 10px;
  left: -4px;  /* 紧贴刻度线左侧，带一点间距 */
  transform: translateX(-100%);  /* 向右平移自身宽度，实现右对齐 */
  padding-right: 4px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}
</style>
