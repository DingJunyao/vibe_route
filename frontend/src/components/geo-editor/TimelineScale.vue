<script setup lang="ts">
import { ref, computed } from 'vue'

interface Props {
  points: any[]
  zoomStart: number
  zoomEnd: number
  timeScaleUnit?: 'time' | 'duration' | 'index'
  // 外部悬浮的高亮索引（来自地图）
  highlightIndex?: number | null | any
}

const props = withDefaults(defineProps<Props>(), {
  timeScaleUnit: 'time',
  highlightIndex: null,
})

const emit = defineEmits<{
  'pointer-change': [position: number]
  'scale-hover': [pointIndex: number | null]  // 悬浮时的点索引
}>()

const scaleRef = ref<HTMLElement>()
const scaleContentRef = ref<HTMLElement>()

// 悬浮指示器位置（百分比）
const hoverIndicatorPosition = ref<number | null>(null)

// 规范化 highlightIndex（处理 ref 解包问题）
const normalizedHighlightIndex = computed(() => {
  if (props.highlightIndex === null || props.highlightIndex === undefined) {
    return null
  }
  // 如果是 ref 对象，获取其值
  if (typeof props.highlightIndex === 'object' && 'value' in props.highlightIndex) {
    return props.highlightIndex.value
  }
  // 确保返回 number 或 null
  const num = Number(props.highlightIndex)
  return isNaN(num) ? null : num
})

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

// 获取内容区域的像素宽度
const contentWidth = computed(() => {
  if (!scaleContentRef.value) return 800 // 默认值
  return scaleContentRef.value.getBoundingClientRect().width
})

// 时间刻度可选间隔（毫秒），从小到大排序
const TIME_INTERVALS = [
  1000,      // 1秒
  2000,      // 2秒
  5000,      // 5秒
  10000,     // 10秒
  30000,     // 30秒
  60000,     // 1分钟
  120000,    // 2分钟
  300000,    // 5分钟
  600000,    // 10分钟
  1800000,   // 30分钟
  3600000,   // 1小时
  7200000,   // 2小时
  21600000,  // 6小时
  43200000,  // 12小时
  86400000,  // 1天
]

// 根据像素宽度选择合适的时间间隔
function selectTimeInterval(visibleDuration: number, minPixelSpacing: number): number {
  const pixelsPerMs = contentWidth.value / visibleDuration
  const minIntervalMs = minPixelSpacing / pixelsPerMs

  // 找到大于等于最小间隔的最小刻度
  for (const interval of TIME_INTERVALS) {
    if (interval >= minIntervalMs) {
      return interval
    }
  }
  return TIME_INTERVALS[TIME_INTERVALS.length - 1]
}

// 二分查找：根据时间找到对应的点索引
function findPointIndexByTime(targetTime: number): number {
  if (props.points.length === 0) return 0

  let left = 0
  let right = props.points.length - 1

  while (left < right) {
    const mid = Math.floor((left + right) / 2)
    const pointTime = props.points[mid]?.time
      ? new Date(props.points[mid].time).getTime()
      : 0

    if (pointTime < targetTime) {
      left = mid + 1
    } else {
      right = mid
    }
  }

  // 检查 left-1 是否更接近
  if (left > 0) {
    const currentDiff = Math.abs(
      (props.points[left]?.time ? new Date(props.points[left].time).getTime() : Infinity) - targetTime
    )
    const prevDiff = Math.abs(
      (props.points[left - 1]?.time ? new Date(props.points[left - 1].time).getTime() : Infinity) - targetTime
    )
    if (prevDiff < currentDiff) {
      return left - 1
    }
  }

  return left
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

  const result: Array<{ position: number; label: string; isMajor: boolean }> = []

  // 主刻度最小像素间距
  const MAJOR_TICK_MIN_PX = 50

  // 根据单位决定刻度间隔
  if (props.timeScaleUnit === 'time' || props.timeScaleUnit === 'duration') {
    // 根据像素宽度选择主刻度间隔
    const majorInterval = selectTimeInterval(visibleDuration, MAJOR_TICK_MIN_PX)
    const minorInterval = majorInterval / 5 // 每个主刻度之间 4 个次刻度

    const firstMinorTick = Math.ceil(visibleStart / minorInterval) * minorInterval

    // 收集所有候选刻度
    const candidates: Array<{ position: number; label: string; isMajor: boolean; time: number }> = []

    // 添加次刻度候选
    for (let t = firstMinorTick; t <= visibleEnd; t += minorInterval) {
      const pointIndex = findPointIndexByTime(t)
      const position = pointIndex / totalPoints

      if (position >= props.zoomStart && position <= props.zoomEnd) {
        // 获取该点的实际时间用于标签
        const actualTime = props.points[pointIndex]?.time
          ? new Date(props.points[pointIndex].time).getTime()
          : t
        candidates.push({
          position: (position - props.zoomStart) / (props.zoomEnd - props.zoomStart),
          label: '',
          isMajor: t % majorInterval === 0,
          time: actualTime,
        })
      }
    }

    // 去重并确保最小间距
    const MIN_SPACING = 0.02 // 最小间距（占总宽度的百分比）
    candidates.sort((a, b) => a.position - b.position)

    const filtered: typeof candidates = []
    for (const candidate of candidates) {
      // 检查是否与已有刻度太近
      const tooClose = filtered.some(f => Math.abs(f.position - candidate.position) < MIN_SPACING)
      if (!tooClose) {
        filtered.push(candidate)
      }
    }

    // 生成最终结果，为主刻度添加标签
    for (const tick of filtered) {
      if (tick.isMajor) {
        let label: string
        if (props.timeScaleUnit === 'time') {
          const date = new Date(tick.time)
          const hours = String(date.getHours()).padStart(2, '0')
          const minutes = String(date.getMinutes()).padStart(2, '0')
          const seconds = String(date.getSeconds()).padStart(2, '0')
          label = `${hours}:${minutes}:${seconds}`
        } else {
          label = formatDuration(tick.time - startTime)
        }
        result.push({
          position: tick.position,
          label,
          isMajor: true,
        })
      } else {
        result.push({
          position: tick.position,
          label: '',
          isMajor: false,
        })
      }
    }
  } else {
    // 索引模式：基于像素宽度计算
    const visibleStartIndex = Math.floor(totalPoints * props.zoomStart)
    const visibleEndIndex = Math.ceil(totalPoints * props.zoomEnd)

    // 根据像素宽度计算每个主刻度代表多少个点
    const pointsPerPx = (visibleEndIndex - visibleStartIndex) / contentWidth.value
    const majorTickPoints = Math.ceil(MAJOR_TICK_MIN_PX * pointsPerPx)
    // 找到最接近的 5/10/50/100 的倍数
    const magnitude = Math.pow(10, Math.floor(Math.log10(majorTickPoints)))
    const normalized = majorTickPoints / magnitude
    let interval: number
    if (normalized <= 1) interval = 1 * magnitude
    else if (normalized <= 2) interval = 2 * magnitude
    else if (normalized <= 5) interval = 5 * magnitude
    else interval = 10 * magnitude

    const minorInterval = Math.max(1, Math.floor(interval / 5))

    const firstTickIndex = Math.ceil(visibleStartIndex / interval) * interval
    const firstMinorIndex = Math.ceil(visibleStartIndex / minorInterval) * minorInterval

    // 添加次刻度
    for (let idx = firstMinorIndex; idx <= visibleEndIndex; idx += minorInterval) {
      const position = idx / totalPoints

      if (position >= props.zoomStart && position <= props.zoomEnd) {
        if (idx % interval !== 0) {
          result.push({
            position: (position - props.zoomStart) / (props.zoomEnd - props.zoomStart),
            label: '',
            isMajor: false,
          })
        }
      }
    }

    // 添加主刻度
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
  if (!scaleContentRef.value) return

  const rect = scaleContentRef.value.getBoundingClientRect()
  const x = e.clientX - rect.left
  const position = Math.max(0, Math.min(1, x / rect.width))
  const globalPosition = props.zoomStart + position * (props.zoomEnd - props.zoomStart)
  emit('pointer-change', globalPosition)
}

// 鼠标悬浮处理（仅桌面端）
function handleScaleMouseMove(e: MouseEvent) {
  // 触摸设备不处理 mousemove，避免干扰触摸事件
  if ('ontouchstart' in window || navigator.maxTouchPoints > 0) return

  if (!scaleContentRef.value || props.points.length === 0) return

  const rect = scaleContentRef.value.getBoundingClientRect()
  const x = e.clientX - rect.left
  const position = Math.max(0, Math.min(1, x / rect.width))

  // 更新悬浮指示器位置
  hoverIndicatorPosition.value = position * 100

  // 计算对应的点索引
  const globalPosition = props.zoomStart + position * (props.zoomEnd - props.zoomStart)
  const pointIndex = Math.floor(globalPosition * props.points.length)
  emit('scale-hover', pointIndex)
}

function handleScaleMouseLeave() {
  // 触摸设备不处理
  if ('ontouchstart' in window || navigator.maxTouchPoints > 0) return

  hoverIndicatorPosition.value = null
  emit('scale-hover', null)
}
</script>

<template>
  <div class="timeline-scale" ref="scaleRef">
    <div class="scale-content">
      <div
        class="scale-content-area"
        ref="scaleContentRef"
        @click="handleScaleClick"
        @mousemove="handleScaleMouseMove"
        @mouseleave="handleScaleMouseLeave"
      >
        <div
          v-for="(tick, index) in ticks"
          :key="index"
          class="tick"
          :class="{ 'tick-major': tick.isMajor }"
          :style="{ left: `${tick.position * 100}%` }"
        >
          <div v-if="tick.isMajor && tick.label" class="tick-label">{{ tick.label }}</div>
        </div>

        <!-- 鼠标悬浮指示器（内部悬浮） -->
        <div
          v-if="hoverIndicatorPosition !== null"
          class="hover-indicator"
          :style="{ left: `${hoverIndicatorPosition}%` }"
        />

        <!-- 外部高亮指示器（来自地图悬浮） -->
        <div
          v-if="normalizedHighlightIndex !== null"
          class="external-highlight-indicator"
          :style="{ left: `${((normalizedHighlightIndex / props.points.length) - props.zoomStart) / (props.zoomEnd - props.zoomStart) * 100}%` }"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.timeline-scale {
  position: relative;
  width: 100%;
  height: 32px;
  background: var(--el-fill-color-lighter);
  border-bottom: 1px solid var(--el-border-color-lighter);
  cursor: crosshair;
  user-select: none;
  touch-action: none;
}

.scale-content {
  position: relative;
  width: 100%;
  height: 100%;
  padding-left: var(--geo-editor-padding-left);
  padding-right: var(--geo-editor-padding-right);
  box-sizing: border-box;
}

.scale-content-area {
  position: relative;
  width: 100%;
  height: 100%;
  background: var(--el-bg-color-page);
}

.tick {
  position: absolute;
  top: 0;
  bottom: 0;
  pointer-events: none;
}

/* 刻度线 - 使用共享变量 */
.tick::before,
.tick::after {
  content: '';
  position: absolute;
  left: 0;
  width: 1px;
}

/* 次刻度 */
.tick:not(.tick-major)::before {
  top: 0;
  height: var(--geo-editor-tick-minor-height);
  background: var(--el-border-color);
}

.tick:not(.tick-major)::after {
  bottom: 0;
  height: var(--geo-editor-tick-minor-height);
  background: var(--el-border-color);
}

/* 主刻度 */
.tick-major::before {
  top: 0;
  height: var(--geo-editor-tick-major-height);
  background: var(--el-text-color-primary);
}

.tick-major::after {
  bottom: 0;
  height: var(--geo-editor-tick-major-height);
  background: var(--el-text-color-primary);
}

.tick-label {
  position: absolute;
  top: 25%;
  left: 0;
  transform: translateX(-50%);
  font-size: 11px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

/* 悬浮指示器（鼠标在刻度上移动时） */
.hover-indicator {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 2px;
  background: var(--el-color-primary);
  opacity: 0.6;
  pointer-events: none;
  transform: translateX(-50%);
}

/* 外部高亮指示器（来自地图悬浮） */
.external-highlight-indicator {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 2px;
  background: var(--el-color-success);
  opacity: 0.6;
  pointer-events: none;
  transform: translateX(-50%);
}
</style>
