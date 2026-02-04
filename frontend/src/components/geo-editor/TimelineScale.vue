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

// 格式化时长：统一使用 HH:MM:SS 格式
function formatDuration(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60

  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
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

// 根据可见范围选择时间间隔，确保至少有指定数量的主刻度
function selectTimeIntervalWithMinimumTicks(
  visibleDuration: number,
  minPixelSpacing: number,
  minMajorTicks: number = 3
): number {
  // 首先按像素间距选择间隔
  let interval = selectTimeInterval(visibleDuration, minPixelSpacing)

  // 检查这个间隔会产生多少个主刻度，如果少于最少数量，缩小间隔
  while (Math.ceil(visibleDuration / interval) < minMajorTicks) {
    // 在 TIME_INTERVALS 中找下一个更小的间隔
    const currentIndex = TIME_INTERVALS.indexOf(interval)
    if (currentIndex > 0) {
      interval = TIME_INTERVALS[currentIndex - 1]
    } else {
      // 已经是最小间隔了，不能再缩小
      break
    }
  }

  return interval
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

  const result: Array<{ position: number; label: string; isMajor: boolean; level?: 0 | 1 | 2 }> = []

  // 主刻度最小像素间距
  const MAJOR_TICK_MIN_PX = 50

  // 计算可视区域内的点索引范围
  const visibleStartIndex = Math.max(0, Math.floor(totalPoints * props.zoomStart))
  const visibleEndIndex = Math.min(totalPoints - 1, Math.ceil(totalPoints * props.zoomEnd))

  // 根据单位决定刻度间隔
  if (props.timeScaleUnit === 'time' || props.timeScaleUnit === 'duration') {
    // 计算可视区域的时间跨度
    const visibleDuration = totalDuration * (props.zoomEnd - props.zoomStart)

    // 根据时间跨度选择主刻度时间间隔
    const majorInterval = selectTimeIntervalWithMinimumTicks(visibleDuration, MAJOR_TICK_MIN_PX, 3)

    // 计算对应的点索引间隔（近似）
    // 假设时间均匀分布，计算每个时间间隔对应的点数
    const pointsPerMillisecond = totalPoints / totalDuration
    const majorPointInterval = Math.round(majorInterval * pointsPerMillisecond)
    const halfMajorPointInterval = Math.round(majorPointInterval / 2)
    const tenthMajorPointInterval = Math.round(majorPointInterval / 10)

    // 确保至少有最小间隔
    const safeMajorInterval = Math.max(majorPointInterval, 10)
    const safeHalfInterval = Math.max(halfMajorPointInterval, 5)
    const safeTenthInterval = Math.max(tenthMajorPointInterval, 1)

    // 扩展边界
    const extendedEndIndex = Math.min(totalPoints - 1, visibleEndIndex + safeMajorInterval * 2)

    // 计算起始对齐：找到第一个与时间边界对齐的点索引
    const firstVisibleTime = props.points[visibleStartIndex]?.time
      ? new Date(props.points[visibleStartIndex].time).getTime()
      : startTime + totalDuration * props.zoomStart
    const alignedTime = Math.floor(firstVisibleTime / majorInterval) * majorInterval
    const alignedStartIndex = findPointIndexByTime(alignedTime)

    // 收集所有候选刻度
    const candidates: Array<{ position: number; label: string; level: 0 | 1 | 2; time: number }> = []

    // 生成主刻度 (level 0)：按点索引，但与时间边界对齐
    for (let idx = alignedStartIndex; idx <= extendedEndIndex; idx += safeMajorInterval) {
      if (idx < 0 || idx >= totalPoints) continue
      const point = props.points[idx]
      if (!point?.time) continue

      const position = idx / totalPoints
      if (position < props.zoomStart || position > props.zoomEnd) continue

      const time = new Date(point.time).getTime()
      candidates.push({
        position: (position - props.zoomStart) / (props.zoomEnd - props.zoomStart),
        label: '',
        level: 0,
        time,
      })
    }

    // 生成次刻度 (level 1)：主刻度中间
    for (let offset = safeHalfInterval; offset < safeMajorInterval; offset += safeMajorInterval) {
      for (let idx = alignedStartIndex + offset; idx <= extendedEndIndex; idx += safeMajorInterval) {
        if (idx < 0 || idx >= totalPoints) continue
        const point = props.points[idx]
        if (!point?.time) continue

        const position = idx / totalPoints
        if (position < props.zoomStart || position > props.zoomEnd) continue

        const time = new Date(point.time).getTime()
        candidates.push({
          position: (position - props.zoomStart) / (props.zoomEnd - props.zoomStart),
          label: '',
          level: 1,
          time,
        })
      }
    }

    // 生成三级刻度 (level 2)：每 1/10 主刻度间隔
    for (let offset = safeTenthInterval; offset < safeMajorInterval; offset += safeTenthInterval) {
      // 跳过主刻度位置（offset 是 majorInterval 的倍数）
      if (offset % safeMajorInterval === 0) continue
      // 跳过次刻度位置（offset 是 halfInterval 的倍数）
      if (safeHalfInterval > 0 && offset % safeHalfInterval === 0) continue

      for (let idx = alignedStartIndex + offset; idx <= extendedEndIndex; idx += safeMajorInterval) {
        if (idx < 0 || idx >= totalPoints) continue
        const point = props.points[idx]
        if (!point?.time) continue

        const position = idx / totalPoints
        if (position < props.zoomStart || position > props.zoomEnd) continue

        const time = new Date(point.time).getTime()
        candidates.push({
          position: (position - props.zoomStart) / (props.zoomEnd - props.zoomStart),
          label: '',
          level: 2,
          time,
        })
      }
    }

    // 去重：按位置合并相近的刻度
    candidates.sort((a, b) => a.position - b.position)

    // 定义不同级别刻度的最小间距（主刻度需要更大的间距以避免标签重叠）
    const MIN_SPACING_MAJOR = 0.05      // 主刻度：5%
    const MIN_SPACING_SECONDARY = 0.01  // 次刻度：1%
    const MIN_SPACING_TERTIARY = 0.002  // 三级刻度：0.2%

    // 按级别分组过滤
    const filtered: typeof candidates = []

    // 首先添加所有主刻度
    const majorCandidates = candidates.filter(c => c.level === 0)
    for (const c of majorCandidates) {
      const tooClose = filtered.some(f =>
        Math.abs(f.position - c.position) < MIN_SPACING_MAJOR
      )
      if (!tooClose) filtered.push(c)
    }

    // 然后添加次刻度（只与主刻度检查间距，不与次刻度互检）
    const secondaryCandidates = candidates.filter(c => c.level === 1)
    for (const c of secondaryCandidates) {
      const tooClose = filtered.some(f =>
        f.level === 0 && Math.abs(f.position - c.position) < MIN_SPACING_SECONDARY
      )
      if (!tooClose) filtered.push(c)
    }

    // 最后添加三级刻度（只与主刻度检查间距）
    const tertiaryCandidates = candidates.filter(c => c.level === 2)
    for (const c of tertiaryCandidates) {
      const tooClose = filtered.some(f =>
        f.level === 0 && Math.abs(f.position - c.position) < MIN_SPACING_TERTIARY
      )
      if (!tooClose) filtered.push(c)
    }

    // 按位置排序
    filtered.sort((a, b) => a.position - b.position)

    // 生成最终结果，为主刻度添加标签
    for (const tick of filtered) {
      let label: string
      if (tick.level === 0) {
        // 主刻度添加标签
        if (props.timeScaleUnit === 'time') {
          const date = new Date(tick.time)
          const hours = String(date.getHours()).padStart(2, '0')
          const minutes = String(date.getMinutes()).padStart(2, '0')
          const seconds = String(date.getSeconds()).padStart(2, '0')
          label = `${hours}:${minutes}:${seconds}`
        } else {
          label = formatDuration(tick.time - startTime)
        }
      } else {
        label = ''
      }
      result.push({
        position: tick.position,
        label,
        isMajor: tick.level === 0,
        level: tick.level,
      })
    }
  } else {
    // 索引模式：基于像素宽度计算
    const visibleStartIndex = Math.floor(totalPoints * props.zoomStart)
    const visibleEndIndex = Math.ceil(totalPoints * props.zoomEnd)
    const visiblePointCount = visibleEndIndex - visibleStartIndex

    // 根据像素宽度计算每个主刻度代表多少个点
    const pointsPerPx = visiblePointCount / contentWidth.value
    const majorTickPoints = Math.ceil(MAJOR_TICK_MIN_PX * pointsPerPx)
    // 找到最接近的 1/2/5/10 的倍数
    const magnitude = Math.pow(10, Math.floor(Math.log10(majorTickPoints)))
    const normalized = majorTickPoints / magnitude
    let interval: number
    if (normalized <= 1) interval = 1 * magnitude
    else if (normalized <= 2) interval = 2 * magnitude
    else if (normalized <= 5) interval = 5 * magnitude
    else interval = 10 * magnitude

    // 确保至少有 3 个主刻度
    const minMajorTicks = 3
    const estimatedTickCount = Math.ceil(visiblePointCount / interval)
    if (estimatedTickCount < minMajorTicks) {
      // 缩小间隔以至少产生 minMajorTicks 个主刻度
      interval = Math.max(1, Math.floor(visiblePointCount / minMajorTicks))
      // 再次规范化为 1/2/5/10 的倍数
      const newMagnitude = Math.pow(10, Math.floor(Math.log10(interval)))
      const newNormalized = interval / newMagnitude
      if (newNormalized <= 1) interval = 1 * newMagnitude
      else if (newNormalized <= 2) interval = 2 * newMagnitude
      else if (newNormalized <= 5) interval = 5 * newMagnitude
      else interval = 10 * newMagnitude
    }

    // 三级刻度间隔
    const tertiaryInterval = Math.max(1, Math.floor(interval / 10))  // 三级刻度：每 1/10 主刻度间隔
    const secondaryInterval = Math.max(1, Math.floor(interval / 2))   // 次刻度：主刻度中间

    // 生成主刻度 (level 0)
    const firstMajorIndex = Math.ceil(visibleStartIndex / interval) * interval
    for (let idx = firstMajorIndex; idx <= visibleEndIndex; idx += interval) {
      const position = idx / totalPoints
      if (position >= props.zoomStart && position <= props.zoomEnd) {
        result.push({
          position: (position - props.zoomStart) / (props.zoomEnd - props.zoomStart),
          label: String(idx),
          isMajor: true,
          level: 0,
        })
      }
    }

    // 生成次刻度 (level 1)
    const firstSecondaryIndex = Math.ceil(visibleStartIndex / secondaryInterval) * secondaryInterval
    for (let idx = firstSecondaryIndex; idx <= visibleEndIndex; idx += secondaryInterval) {
      // 跳过主刻度位置
      if (idx % interval === 0) continue
      const position = idx / totalPoints
      if (position >= props.zoomStart && position <= props.zoomEnd) {
        result.push({
          position: (position - props.zoomStart) / (props.zoomEnd - props.zoomStart),
          label: '',
          isMajor: false,
          level: 1,
        })
      }
    }

    // 生成三级刻度 (level 2)
    const firstTertiaryIndex = Math.ceil(visibleStartIndex / tertiaryInterval) * tertiaryInterval
    for (let idx = firstTertiaryIndex; idx <= visibleEndIndex; idx += tertiaryInterval) {
      // 跳过主刻度和次刻度位置
      if (idx % interval === 0) continue
      if (idx % secondaryInterval === 0) continue
      const position = idx / totalPoints
      if (position >= props.zoomStart && position <= props.zoomEnd) {
        result.push({
          position: (position - props.zoomStart) / (props.zoomEnd - props.zoomStart),
          label: '',
          isMajor: false,
          level: 2,
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
          :class="{
            'tick-major': tick.level === 0,
            'tick-secondary': tick.level === 1,
            'tick-tertiary': tick.level === 2
          }"
          :style="{ left: `${tick.position * 100}%` }"
        >
          <div v-if="tick.level === 0 && tick.label" class="tick-label">{{ tick.label }}</div>
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

/* 主刻度 (level 0) - 长线，深色，带标签 */
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

/* 次刻度 (level 1) - 长线，浅色，无标签 */
.tick-secondary::before {
  top: 0;
  height: var(--geo-editor-tick-major-height);
  background: var(--el-border-color);
}

.tick-secondary::after {
  bottom: 0;
  height: var(--geo-editor-tick-major-height);
  background: var(--el-border-color);
}

/* 三级刻度 (level 2) - 短线，浅色，无标签 */
.tick-tertiary::before {
  top: 0;
  height: var(--geo-editor-tick-minor-height);
  background: var(--el-border-color);
}

.tick-tertiary::after {
  bottom: 0;
  height: var(--geo-editor-tick-minor-height);
  background: var(--el-border-color);
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
