# 地理编辑器改进实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 改进地理编辑器，新增图表区域、刻度切换、折叠功能、撤销/重做和波纹剪辑联动。

**Architecture:** 基于现有 GeoEditor.vue 重构，新增图表面板组件、撤销重做管理器，修改时间轴和编辑对话框。

**Tech Stack:** Vue 3 (Composition API), Element Plus, Pinia, ECharts

---

## Task 1: 创建编辑器 Pinia Store

**Files:**
- Create: `frontend/src/stores/geoEditor.ts`

**Step 1: 定义 Store 类型**

```typescript
// frontend/src/stores/geoEditor.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export type TrackType = 'province' | 'city' | 'district' | 'roadNumber' | 'roadName'
export type TimeScaleUnit = 'time' | 'duration' | 'index'

export interface TrackSegment {
  id: string
  startIndex: number
  endIndex: number
  pointCount: number
  value: string | null
  valueEn: string | null
  isSelected?: boolean
  isHovered?: boolean
  isEdited?: boolean
}

export interface TrackTimeline {
  type: TrackType
  label: string
  segments: TrackSegment[]
  hasEnglish: boolean
}

export interface EditHistory {
  id: string
  timestamp: number
  action: 'edit' | 'resize' | 'split' | 'merge'
  description: string
  before: { tracks: TrackTimeline[], selectedId: string | null }
  after: { tracks: TrackTimeline[], selectedId: string | null }
}

export const useGeoEditorStore = defineStore('geoEditor', () => {
  // State
  const trackId = ref<number | null>(null)
  const points = ref<any[]>([])
  const tracks = ref<TrackTimeline[]>([])
  const totalDuration = ref(0)

  const selectedSegmentId = ref<string | null>(null)
  const hoveredSegmentId = ref<string | null>(null)

  const timeScaleUnit = ref<TimeScaleUnit>('time')
  const isChartExpanded = ref(true)
  const isTimelineExpanded = ref(true)

  const history = ref<EditHistory[]>([])
  const historyIndex = ref(-1)

  const hasUnsavedChanges = ref(false)
  const lastSavedAt = ref<number | null>(null)

  // Getters
  const canUndo = computed(() => historyIndex.value > 0)
  const canRedo = computed(() => historyIndex.value < history.value.length - 1)

  // Actions
  function setTrack(id: number, pts: any[]) {
    trackId.value = id
    points.value = pts
    calculateTotalDuration()
  }

  function calculateTotalDuration() {
    if (points.value.length < 2) {
      totalDuration.value = 0
      return
    }
    const first = new Date(points.value[0].time).getTime()
    const last = new Date(points.value[points.value.length - 1].time).getTime()
    totalDuration.value = last - first
  }

  function setTracks(newTracks: TrackTimeline[]) {
    tracks.value = newTracks
  }

  function selectSegment(id: string | null) {
    selectedSegmentId.value = id
  }

  function hoverSegment(id: string | null) {
    hoveredSegmentId.value = id
  }

  function setTimeScaleUnit(unit: TimeScaleUnit) {
    timeScaleUnit.value = unit
  }

  function toggleChart() {
    isChartExpanded.value = !isChartExpanded.value
  }

  function toggleTimeline() {
    isTimelineExpanded.value = !isTimelineExpanded.value
  }

  function recordAction(
    action: EditHistory['action'],
    description: string,
    before: TrackTimeline[],
    after: TrackTimeline[]
  ) {
    const historyItem: EditHistory = {
      id: `hist_${Date.now()}`,
      timestamp: Date.now(),
      action,
      description,
      before: { tracks: before, selectedId: selectedSegmentId.value },
      after: { tracks: after, selectedId: selectedSegmentId.value }
    }

    // 移除当前位置之后的历史
    if (historyIndex.value < history.value.length - 1) {
      history.value = history.value.slice(0, historyIndex.value + 1)
    }

    history.value.push(historyItem)
    historyIndex.value = history.value.length - 1

    // 限制历史数量
    if (history.value.length > 50) {
      history.value.shift()
      historyIndex.value--
    }

    hasUnsavedChanges.value = true
    persistHistory()
  }

  function undo(): boolean {
    if (!canUndo.value) return false
    historyIndex.value--
    restoreState(history.value[historyIndex.value].before)
    return true
  }

  function redo(): boolean {
    if (!canRedo.value) return false
    historyIndex.value++
    restoreState(history.value[historyIndex.value].after)
    return true
  }

  function restoreState(state: EditHistory['before'] | EditHistory['after']) {
    tracks.value = state.tracks.map(t => ({
      ...t,
      segments: t.segments.map(s => ({ ...s }))
    }))
    selectedSegmentId.value = state.selectedId
  }

  const STORAGE_KEY = 'geo-editor-history'

  function persistHistory() {
    if (!trackId.value) return
    const data = {
      history: history.value,
      historyIndex: historyIndex.value,
      trackId: trackId.value,
      savedAt: Date.now()
    }
    localStorage.setItem(`${STORAGE_KEY}-${trackId.value}`, JSON.stringify(data))
  }

  function restoreSession(id: number): boolean {
    const data = localStorage.getItem(`${STORAGE_KEY}-${id}`)
    if (!data) return false

    try {
      const parsed = JSON.parse(data)
      history.value = parsed.history || []
      historyIndex.value = parsed.historyIndex ?? -1
      return true
    } catch {
      return false
    }
  }

  function clearHistory() {
    history.value = []
    historyIndex.value = -1
    if (trackId.value) {
      localStorage.removeItem(`${STORAGE_KEY}-${trackId.value}`)
    }
  }

  function markAsSaved() {
    hasUnsavedChanges.value = false
    lastSavedAt.value = Date.now()
  }

  function reset() {
    trackId.value = null
    points.value = []
    tracks.value = []
    totalDuration.value = 0
    selectedSegmentId.value = null
    hoveredSegmentId.value = null
    isChartExpanded.value = true
    isTimelineExpanded.value = true
    clearHistory()
    hasUnsavedChanges.value = false
    lastSavedAt.value = null
  }

  return {
    // State
    trackId,
    points,
    tracks,
    totalDuration,
    selectedSegmentId,
    hoveredSegmentId,
    timeScaleUnit,
    isChartExpanded,
    isTimelineExpanded,
    history,
    historyIndex,
    hasUnsavedChanges,
    lastSavedAt,

    // Getters
    canUndo,
    canRedo,

    // Actions
    setTrack,
    calculateTotalDuration,
    setTracks,
    selectSegment,
    hoverSegment,
    setTimeScaleUnit,
    toggleChart,
    toggleTimeline,
    recordAction,
    undo,
    redo,
    restoreSession,
    clearHistory,
    markAsSaved,
    reset
  }
})
```

**Step 2: 验证文件创建**

Run: `ls -la frontend/src/stores/geoEditor.ts`
Expected: 文件存在

**Step 3: Commit**

```bash
git add frontend/src/stores/geoEditor.ts
git commit -m "feat(geo-editor): add Pinia store with undo/redo support"
```

---

## Task 2: 创建图表面板组件

**Files:**
- Create: `frontend/src/components/geo-editor/GeoChartPanel.vue`

**Step 1: 创建组件**

```vue
<!-- frontend/src/components/geo-editor/GeoChartPanel.vue -->
<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import type { TrackPoint } from '@/api/track'

interface Props {
  points: TrackPoint[]
  timeScaleUnit: 'time' | 'duration' | 'index'
  highlightedRange?: { start: number; end: number } | null
}

const props = defineProps<Props>()

interface Emits {
  (e: 'highlight', dataIndex: number): void
  (e: 'hoverChange', dataIndex: number | null): void
}

const emit = defineEmits<Emits>()

const chartRef = ref<HTMLElement>()
let elevationChart: echarts.ECharts | null = null
let speedChart: echarts.ECharts | null = null

// 图表显示状态
const showElevation = ref(true)
const showSpeed = ref(true)

// 计算图表数据
const chartData = computed(() => {
  if (props.points.length === 0) return { xAxis: [], elevation: [], speed: [] }

  const xAxis: string[] = []
  const elevation: number[] = []
  const speed: number[] = []

  let startTime = props.points[0]?.time ? new Date(props.points[0].time).getTime() : 0

  props.points.forEach((point, index) => {
    // x 轴标签根据单位变化
    let label = ''
    if (props.timeScaleUnit === 'index') {
      label = index.toString()
    } else if (props.timeScaleUnit === 'duration') {
      const pointTime = point.time ? new Date(point.time).getTime() : startTime
      const duration = pointTime - startTime
      label = formatDuration(duration)
    } else {
      // time
      label = point.time ? formatTime(point.time) : index.toString()
    }

    xAxis.push(label)
    elevation.push(point.elevation || 0)
    speed.push(point.speed || 0)
  })

  return { xAxis, elevation, speed }
})

// 格式化时长为 HH:MM:SS.mmm
function formatDuration(ms: number): string {
  const hours = Math.floor(ms / 3600000)
  const minutes = Math.floor((ms % 3600000) / 60000)
  const seconds = Math.floor((ms % 60000) / 1000)
  const milliseconds = ms % 1000

  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}.${String(milliseconds).padStart(3, '0')}`
}

// 格式化时间为 HH:MM:SS.mmm
function formatTime(timeStr: string): string {
  const date = new Date(timeStr)
  if (isNaN(date.getTime())) return timeStr

  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')
  const ms = String(date.getMilliseconds()).padStart(3, '0')

  return `${hours}:${minutes}:${seconds}.${ms}`
}

// 高亮区域
const highlightArea = computed(() => {
  if (!props.highlightedRange) return null
  return {
    start: props.highlightedRange.start,
    end: props.highlightedRange.end
  }
})

// 初始化图表
function initCharts() {
  if (!chartRef.value) return

  // 销毁旧实例
  if (elevationChart) {
    elevationChart.dispose()
    elevationChart = null
  }
  if (speedChart) {
    speedChart.dispose()
    speedChart = null
  }

  // 创建海拔图表
  const elevationEl = chartRef.value.querySelector('.elevation-chart') as HTMLElement
  if (elevationEl && showElevation.value) {
    elevationChart = echarts.init(elevationEl)
    updateElevationChart()
  }

  // 创建速度图表
  const speedEl = chartRef.value.querySelector('.speed-chart') as HTMLElement
  if (speedEl && showSpeed.value) {
    speedChart = echarts.init(speedEl)
    updateSpeedChart()
  }
}

// 更新海拔图表
function updateElevationChart() {
  if (!elevationChart) return

  const option: echarts.EChartsOption = {
    grid: { top: 10, right: 10, bottom: 20, left: 40 },
    xAxis: {
      type: 'category',
      data: chartData.value.xAxis,
      axisLabel: { show: false },
      axisLine: { show: false },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      name: '海拔 (m)',
      nameTextStyle: { fontSize: 10 }
    },
    series: [{
      type: 'line',
      data: chartData.value.elevation,
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 1 },
      areaStyle: { opacity: 0.3 }
    }]
  }

  // 添加高亮区域
  if (highlightArea.value) {
    option.dataZoom = [{
      type: 'inside',
      start: (highlightArea.value.start / props.points.length) * 100,
      end: (highlightArea.value.end / props.points.length) * 100
    }]
  }

  elevationChart.setOption(option)
}

// 更新速度图表
function updateSpeedChart() {
  if (!speedChart) return

  const option: echarts.EChartsOption = {
    grid: { top: 10, right: 10, bottom: 20, left: 40 },
    xAxis: {
      type: 'category',
      data: chartData.value.xAxis,
      axisLabel: { show: false },
      axisLine: { show: false },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      name: '速度 (km/h)',
      nameTextStyle: { fontSize: 10 }
    },
    series: [{
      type: 'line',
      data: chartData.value.speed,
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 1 },
      areaStyle: { opacity: 0.3 }
    }]
  }

  if (highlightArea.value) {
    option.dataZoom = [{
      type: 'inside',
      start: (highlightArea.value.start / props.points.length) * 100,
      end: (highlightArea.value.end / props.points.length) * 100
    }]
  }

  speedChart.setOption(option)
}

// 监听变化
watch(() => [chartData.value, highlightArea.value], () => {
  updateElevationChart()
  updateSpeedChart()
}, { deep: true })

watch(() => props.timeScaleUnit, () => {
  updateElevationChart()
  updateSpeedChart()
})

// 图表事件处理
function setupChartEvents() {
  if (!elevationChart && !speedChart) return

  const handler = (params: any) => {
    if (params.dataIndex !== undefined) {
      emit('highlight', params.dataIndex)
    }
  }

  const hoverHandler = (params: any) => {
    if (params.dataIndex !== undefined) {
      emit('hoverChange', params.dataIndex)
    } else {
      emit('hoverChange', null)
    }
  }

  elevationChart?.on('click', handler)
  elevationChart?.on('mousemove', hoverHandler)
  elevationChart?.on('mouseout', () => emit('hoverChange', null))

  speedChart?.on('click', handler)
  speedChart?.on('mousemove', hoverHandler)
  speedChart?.on('mouseout', () => emit('hoverChange', null))
}

// 窗口大小变化
function handleResize() {
  elevationChart?.resize()
  speedChart?.resize()
}

onMounted(() => {
  nextTick(() => {
    initCharts()
    setupChartEvents()
  })
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  elevationChart?.dispose()
  speedChart?.dispose()
  window.removeEventListener('resize', handleResize)
})

// 暴露刷新方法供父组件调用
function refresh() {
  nextTick(() => {
    initCharts()
    setupChartEvents()
  })
}

defineExpose({ refresh })
</script>

<template>
  <div v-if="points.length > 0" ref="chartRef" class="geo-chart-panel">
    <div v-if="showElevation" class="chart-container elevation-chart-container">
      <div class="chart-label">海拔</div>
      <div class="elevation-chart" style="width: 100%; height: 100%;"></div>
    </div>
    <div v-if="showSpeed" class="chart-container speed-chart-container">
      <div class="chart-label">速度</div>
      <div class="speed-chart" style="width: 100%; height: 100%;"></div>
    </div>
  </div>
  <div v-else class="chart-empty">
    <span>无数据</span>
  </div>
</template>

<style scoped>
.geo-chart-panel {
  display: flex;
  gap: 8px;
  height: 100%;
  padding: 8px;
  background: var(--el-bg-color-page);
}

.chart-container {
  flex: 1;
  display: flex;
  position: relative;
  background: var(--el-bg-color);
  border-radius: 4px;
  overflow: hidden;
}

.chart-label {
  position: absolute;
  top: 4px;
  left: 8px;
  font-size: 10px;
  color: var(--el-text-color-secondary);
  z-index: 1;
}

.chart-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--el-text-color-placeholder);
  font-size: 12px;
}

@media (max-width: 768px) {
  .geo-chart-panel {
    flex-direction: column;
  }
}
</style>
```

**Step 2: 验证文件创建**

Run: `ls -la frontend/src/components/geo-editor/GeoChartPanel.vue`
Expected: 文件存在

**Step 3: Commit**

```bash
git add frontend/src/components/geo-editor/GeoChartPanel.vue
git commit -m "feat(geo-editor): add chart panel component with elevation and speed"
```

---

## Task 3: 创建刻度尺组件

**Files:**
- Create: `frontend/src/components/geo-editor/TimeScaleRuler.vue`

**Step 1: 创建组件**

```vue
<!-- frontend/src/components/geo-editor/TimeScaleRuler.vue -->
<script setup lang="ts">
import { computed } from 'vue'
import type { TrackPoint } from '@/api/track'

interface Props {
  points: TrackPoint[]
  timeScaleUnit: 'time' | 'duration' | 'index'
  containerWidth: number
  scrollLeft: number
}

const props = defineProps<Props>()

interface TimeTick {
  position: number
  label: string
}

// 计算刻度
const ticks = computed<TimeTick[]>(() => {
  if (props.points.length === 0) return []

  const result: TimeTick[] = []
  const totalPoints = props.points.length

  // 根据容器宽度决定刻度间隔
  let tickInterval: number
  const pixelsPerTick = 100 // 每个刻度至少100px
  const tickCount = Math.max(1, Math.floor(props.containerWidth / pixelsPerTick))
  tickInterval = Math.max(1, Math.floor(totalPoints / tickCount))

  // 取整到漂亮的数字
  tickInterval = roundToNiceNumber(tickInterval)

  const startTime = props.points[0]?.time
    ? new Date(props.points[0].time).getTime()
    : Date.now()

  for (let i = 0; i < totalPoints; i += tickInterval) {
    const point = props.points[i]
    if (!point) continue

    const position = (i / totalPoints) * props.containerWidth
    let label = ''

    if (props.timeScaleUnit === 'index') {
      label = i.toString()
    } else if (props.timeScaleUnit === 'duration') {
      const pointTime = point.time ? new Date(point.time).getTime() : startTime
      const duration = pointTime - startTime
      label = formatDuration(duration)
    } else {
      label = point.time ? formatTime(point.time) : i.toString()
    }

    result.push({ position, label })
  }

  // 添加最后一个点的刻度
  const lastIndex = totalPoints - 1
  if (result.length === 0 || result[result.length - 1].position < props.containerWidth - 1) {
    const lastPoint = props.points[lastIndex]
    if (lastPoint) {
      let label = ''
      if (props.timeScaleUnit === 'index') {
        label = lastIndex.toString()
      } else if (props.timeScaleUnit === 'duration') {
        const pointTime = lastPoint.time ? new Date(lastPoint.time).getTime() : startTime
        const duration = pointTime - startTime
        label = formatDuration(duration)
      } else {
        label = lastPoint.time ? formatTime(lastPoint.time) : lastIndex.toString()
      }
      result.push({ position: props.containerWidth, label })
    }
  }

  return result
})

// 可见刻度（考虑滚动）
const visibleTicks = computed(() => {
  return ticks.value.map(tick => ({
    ...tick,
    visiblePosition: Math.max(0, tick.position - props.scrollLeft)
  }))
})

function roundToNiceNumber(n: number): number {
  const niceNumbers = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]
  const magnitude = Math.pow(10, Math.floor(Math.log10(n)))
  for (const nice of niceNumbers) {
    if (nice * magnitude >= n) {
      return nice * magnitude
    }
  }
  return n
}

function formatDuration(ms: number): string {
  const hours = Math.floor(ms / 3600000)
  const minutes = Math.floor((ms % 3600000) / 60000)
  const seconds = Math.floor((ms % 60000) / 1000)

  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
  }
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

function formatTime(timeStr: string): string {
  const date = new Date(timeStr)
  if (isNaN(date.getTime())) return timeStr

  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')

  return `${hours}:${minutes}:${seconds}`
}
</script>

<template>
  <div class="time-scale-ruler">
    <div class="ruler-track">
      <div
        v-for="(tick, index) in visibleTicks"
        :key="index"
        class="tick-mark"
        :style="{ left: `${tick.visiblePosition}px` }"
      >
        <span class="tick-label">{{ tick.label }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.time-scale-ruler {
  height: 24px;
  background: var(--el-fill-color-lighter);
  border-bottom: 1px solid var(--el-border-color);
  position: relative;
}

.ruler-track {
  height: 100%;
  position: relative;
}

.tick-mark {
  position: absolute;
  top: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  pointer-events: none;
}

.tick-mark::before {
  content: '';
  width: 1px;
  height: 6px;
  background: var(--el-border-color);
  margin-bottom: 2px;
}

.tick-label {
  font-size: 9px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
  transform: translateX(-50%);
}
</style>
```

**Step 2: 验证文件创建**

Run: `ls -la frontend/src/components/geo-editor/TimeScaleRuler.vue`
Expected: 文件存在

**Step 3: Commit**

```bash
git add frontend/src/components/geo-editor/TimeScaleRuler.vue
git commit -m "feat(geo-editor): add time scale ruler component with unit support"
```

---

## Task 4: 重写 SegmentEditDialog 为单字段编辑

**Files:**
- Modify: `frontend/src/components/geo-editor/SegmentEditDialog.vue`

**Step 1: 备份原文件**

```bash
cp frontend/src/components/geo-editor/SegmentEditDialog.vue frontend/src/components/geo-editor/SegmentEditDialog.vue.bak
```

**Step 2: 重写组件**

```vue
<!-- frontend/src/components/geo-editor/SegmentEditDialog.vue -->
<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'

type TrackType = 'province' | 'city' | 'district' | 'roadNumber' | 'roadName'

interface Props {
  modelValue: boolean
  trackType: TrackType
  segmentId: string
  startIndex: number
  endIndex: number
  currentValue: string | null
  currentValueEn: string | null
}

interface Emits {
  (e: 'update:modelValue', value: boolean): void
  (e: 'save', data: { trackType: TrackType; segmentId: string; value: string; valueEn: string | null }): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const formRef = ref()
const formData = ref({ value: '', valueEn: '' })

// 轨道配置
const TRACK_CONFIG = {
  province: { label: '省份', hasEnglish: true, placeholder: '如：北京市' },
  city: { label: '城市', hasEnglish: true, placeholder: '如：北京市' },
  district: { label: '区县', hasEnglish: true, placeholder: '如：朝阳区' },
  roadNumber: { label: '道路编号', hasEnglish: false, placeholder: '如：G221、豫S88' },
  roadName: { label: '道路名称', hasEnglish: true, placeholder: '如：京哈高速' }
}

const config = computed(() => TRACK_CONFIG[props.trackType])
const dialogTitle = computed(() => `编辑${config.value.label} (#${props.startIndex} - #${props.endIndex})`)
const hasEnglish = computed(() => config.value.hasEnglish)

// 加载数据
watch(() => props.modelValue, (visible) => {
  if (visible) {
    formData.value = {
      value: props.currentValue || '',
      valueEn: props.currentValueEn || ''
    }
  }
}, { immediate: true })

function handleSave() {
  const cleanedValue = formData.value.value.trim()
  const cleanedValueEn = hasEnglish.value ? (formData.value.valueEn?.trim() || null) : null

  if (!cleanedValue) {
    ElMessage.warning('请输入有效内容')
    return
  }

  emit('save', {
    trackType: props.trackType,
    segmentId: props.segmentId,
    value: cleanedValue,
    valueEn: cleanedValueEn
  })

  handleClose()
}

function handleClose() {
  emit('update:modelValue', false)
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="dialogTitle"
    width="400px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <el-form ref="formRef" :model="formData" label-width="80px">
      <el-form-item :label="config.label" prop="value">
        <el-input
          v-model="formData.value"
          :placeholder="config.placeholder"
          clearable
        />
      </el-form-item>

      <el-form-item v-if="hasEnglish" label="英文" prop="valueEn">
        <el-input
          v-model="formData.valueEn"
          placeholder="如：Beijing"
          clearable
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" @click="handleSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
@media (max-width: 768px) {
  :deep(.el-dialog) {
    width: 90% !important;
  }
}
</style>
```

**Step 3: 验证修改**

Run: `grep -c "trackType: 'province'" frontend/src/components/geo-editor/SegmentEditDialog.vue`
Expected: 1

**Step 4: Commit**

```bash
git add frontend/src/components/geo-editor/SegmentEditDialog.vue
git commit -m "refactor(geo-editor): rewrite dialog to single-field editing"
```

---

## Task 5: 更新 TimelineTracks 支持层级联动

**Files:**
- Modify: `frontend/src/components/geo-editor/TimelineTracks.vue`

**Step 1: 修改组件以支持层级联动**

由于文件较大，分步修改关键部分：

1. **添加层级定义和联动逻辑**

在 script 顶部添加：

```typescript
// 层级关系定义
const TRACK_HIERARCHY = {
  province: null,
  city: 'province',
  district: 'city',
  roadNumber: null,
  roadName: null
}

// 层级顺序
const LEVEL_ORDER = ['province', 'city', 'district']
```

2. **修改 handleDragMove 函数添加联动逻辑**

找到 `handleDragMove` 函数，替换为：

```typescript
// 拖拽中
function handleDragMove(e: MouseEvent) {
  if (!isDragging.value || !dragSegment.value || !dragType.value) return

  const currentTrack = tracks.value.find(t => t.segments.includes(dragSegment.value!))
  if (!currentTrack) return

  const trackContent = document.querySelector(`[data-track-id="${currentTrack.id}"] .track-content-inner`) as HTMLElement
  if (!trackContent) return

  const trackRect = trackContent.getBoundingClientRect()
  const offsetX = e.clientX - trackRect.left
  const actualX = offsetX + scrollLeft.value
  const contentWidth = totalPoints.value * PIXELS_PER_POINT * zoomLevel.value

  const percent = Math.max(0, Math.min(1, actualX / contentWidth))
  const newIndex = Math.floor(percent * totalPoints.value)

  const segments = currentTrack.segments
  const segmentIndex = segments.findIndex(s => s.id === dragSegment.value!.id)

  let newStartIndex = dragSegment.value.startIndex
  let newEndIndex = dragSegment.value.endIndex

  if (dragType.value === 'left') {
    const minIndex = segmentIndex > 0 ? segments[segmentIndex - 1].endIndex + 1 : 0
    const maxIndex = dragSegment.value.endIndex - 1
    newStartIndex = Math.max(minIndex, Math.min(maxIndex, newIndex))
  } else {
    const minIndex = dragSegment.value.startIndex + 1
    const maxIndex = segmentIndex < segments.length - 1 ? segments[segmentIndex + 1].startIndex - 1 : totalPoints.value - 1
    newEndIndex = Math.max(minIndex, Math.min(maxIndex, newIndex))
  }

  // 如果是行政区划轨道，触发联动更新
  if (currentTrack.adminLevel) {
    emit('adminResize', currentTrack.adminLevel, dragSegment.value.id, newStartIndex, newEndIndex)
  } else {
    emit('resize', dragSegment.value.id, newStartIndex, newEndIndex)
  }
}
```

3. **修改 emit 定义**

更新 interface Emits：

```typescript
interface Emits {
  (e: 'click', segmentId: string): void
  (e: 'dblclick', segmentId: string, trackType: string, adminLevel?: string): void
  (e: 'hover', segmentId: string | null): void
  (e: 'resize', segmentId: string, newStartIndex: number, newEndIndex: number): void
  (e: 'adminResize', adminLevel: string, segmentId: string, newStartIndex: number, newEndIndex: number): void
}
```

**Step 2: 验证修改**

Run: `grep "adminResize" frontend/src/components/geo-editor/TimelineTracks.vue | wc -l`
Expected: 至少 2 行

**Step 3: Commit**

```bash
git add frontend/src/components/geo-editor/TimelineTracks.vue
git commit -m "feat(geo-editor): add hierarchy cascade resize to timeline tracks"
```

---

## Task 6: 重写 GeoEditor.vue 主页面

**Files:**
- Modify: `frontend/src/views/GeoEditor.vue`

**Step 1: 备份原文件**

```bash
cp frontend/src/views/GeoEditor.vue frontend/src/views/GeoEditor.vue.bak
```

**Step 2: 重写主组件**

```vue
<!-- frontend/src/views/GeoEditor.vue -->
<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, HomeFilled, RefreshLeft, RefreshRight, DocumentChecked, ZoomIn, ZoomOut } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/api/request'
import UniversalMap from '@/components/map/UniversalMap.vue'
import TimelineTracks from '@/components/geo-editor/TimelineTracks.vue'
import SegmentEditDialog from '@/components/geo-editor/SegmentEditDialog.vue'
import GeoChartPanel from '@/components/geo-editor/GeoChartPanel.vue'
import TimeScaleRuler from '@/components/geo-editor/TimeScaleRuler.vue'
import { useGeoEditorStore, type TrackType } from '@/stores/geoEditor'
import type { TrackPoint } from '@/api/track'

const route = useRoute()
const router = useRouter()
const store = useGeoEditorStore()

const trackId = computed(() => parseInt(route.params.id as string))
const track = ref<any>(null)
const points = ref<TrackPoint[]>([])

// 加载状态
const loading = ref(true)
const error = ref<string | null>(null)

// 地图引用
const mapRef = ref<InstanceType<typeof UniversalMap> | null>(null)
const chartPanelRef = ref<InstanceType<typeof GeoChartPanel> | null>(null)

// 编辑对话框
const editDialogVisible = ref(false)
const editDialogTrackType = ref<TrackType>('province')
const editDialogSegmentId = ref('')
const editDialogStartIndex = ref(0)
const editDialogEndIndex = ref(0)
const editDialogCurrentValue = ref<string | null>(null)
const editDialogCurrentValueEn = ref<string | null>(null)

// 缩放状态
const zoomLevel = ref(1)
const scrollLeft = ref(0)
const containerWidth = ref(1000)

const PIXELS_PER_POINT = 2

// 计算属性
const hasChanges = computed(() => store.hasUnsavedChanges)
const canUndo = computed(() => store.canUndo)
const canRedo = computed(() => store.canRedo)

const isChartExpanded = computed(() => store.isChartExpanded)
const isTimelineExpanded = computed(() => store.isTimelineExpanded)
const timeScaleUnit = computed(() => store.timeScaleUnit)

const tracks = computed(() => store.tracks)
const selectedSegmentId = computed(() => store.selectedSegmentId)
const hoveredSegmentId = computed(() => store.hoveredSegmentId)

// 转换为 UniversalMap 格式
const mapTracks = computed(() => {
  if (points.value.length === 0) return []
  return [{
    id: 1,
    points: points.value.map(p => ({
      latitude: p.latitude,
      longitude: p.longitude,
      latitude_wgs84: p.latitude_wgs84,
      longitude_wgs84: p.longitude_wgs84,
      latitude_gcj02: p.latitude_gcj02,
      longitude_gcj02: p.longitude_gcj02,
      latitude_bd09: p.latitude_bd09,
      longitude_bd09: p.longitude_bd09,
      elevation: p.elevation,
      time: p.time,
      speed: p.speed,
    }))
  }]
})

// 高亮区域
const highlightSegment = computed(() => {
  const id = selectedSegmentId.value || hoveredSegmentId.value
  if (!id) return null

  // 从 ID 解析索引: trackType_startIndex_endIndex
  const match = id.match(/[^_]+_(\d+)_(\d+)$/)
  if (match) {
    return {
      start: parseInt(match[1]),
      end: parseInt(match[2])
    }
  }
  return null
})

// ==================== API ====================

async function fetchTrack() {
  loading.value = true
  error.value = null

  try {
    const response = await request.get(`/tracks/${trackId.value}`)
    track.value = response

    const pointsResponse = await request.get(`/tracks/${trackId.value}/points`)
    points.value = pointsResponse.points || pointsResponse

    // 初始化 store
    store.setTrack(trackId.value, points.value)
    store.restoreSession(trackId.value)

    // 构建轨道
    buildTracks()
  } catch (err: any) {
    error.value = err.response?.data?.detail || '加载轨迹失败'
    ElMessage.error(error.value)
  } finally {
    loading.value = false
  }
}

// 构建轨道数据
function buildTracks() {
  if (points.value.length === 0) return

  const result = store.tracks
  result.length = 0

  // 辅助函数：构建段落
  const buildSegments = (getValue: (p: TrackPoint) => string | null, trackType: TrackType): any[] => {
    const segments: any[] = []
    let startIndex = 0
    let currentValue = getValue(points.value[0])

    for (let i = 1; i < points.value.length; i++) {
      const value = getValue(points.value[i])
      if (value !== currentValue) {
        if (currentValue) {
          segments.push({
            id: `${trackType}_${startIndex}_${i - 1}`,
            startIndex,
            endIndex: i - 1,
            pointCount: i - startIndex,
            value: currentValue,
            valueEn: null,
            trackType
          })
        }
        startIndex = i
        currentValue = value
      }
    }

    if (currentValue && startIndex < points.value.length) {
      segments.push({
        id: `${trackType}_${startIndex}_${points.value.length - 1}`,
        startIndex,
        endIndex: points.value.length - 1,
        pointCount: points.value.length - startIndex,
        value: currentValue,
        valueEn: null,
        trackType
      })
    }

    return segments
  }

  // 省级
  result.push({
    type: 'province' as TrackType,
    label: '省级',
    hasEnglish: true,
    segments: buildSegments(p => p.province, 'province')
  })

  // 地级
  result.push({
    type: 'city' as TrackType,
    label: '地级',
    hasEnglish: true,
    segments: buildSegments(p => p.city, 'city')
  })

  // 县级
  result.push({
    type: 'district' as TrackType,
    label: '县级',
    hasEnglish: true,
    segments: buildSegments(p => p.district, 'district')
  })

  // 道路编号
  result.push({
    type: 'roadNumber' as TrackType,
    label: '道路编号',
    hasEnglish: false,
    segments: buildSegments(p => p.road_number, 'roadNumber')
  })

  // 道路名称
  result.push({
    type: 'roadName' as TrackType,
    label: '道路名称',
    hasEnglish: true,
    segments: buildSegments(p => p.road_name, 'roadName')
  })

  store.setTracks(result)
}

// ==================== 保存 ====================

async function handleSave() {
  if (!hasChanges.value) {
    ElMessage.info('没有需要保存的更改')
    return
  }

  // 收集所有编辑过的段落
  const segments: any[] = []

  store.tracks.forEach(track => {
    track.segments.forEach(seg => {
      if (seg.isEdited) {
        const update: any = {
          start_point_index: seg.startIndex,
          end_point_index: seg.endIndex
        }

        if (track.type === 'province') {
          update.province = seg.value
          update.province_en = seg.valueEn
        } else if (track.type === 'city') {
          update.city = seg.value
          update.city_en = seg.valueEn
        } else if (track.type === 'district') {
          update.district = seg.value
          update.district_en = seg.valueEn
        } else if (track.type === 'roadNumber') {
          update.road_number = seg.value
        } else if (track.type === 'roadName') {
          update.road_name = seg.value
          update.road_name_en = seg.valueEn
        }

        segments.push(update)
      }
    })
  })

  if (segments.length === 0) {
    ElMessage.info('没有需要保存的更改')
    return
  }

  try {
    await request.put(`/geo-editor/tracks/${trackId.value}/geo-segments`, {
      segments
    })
    ElMessage.success('保存成功')
    store.markAsSaved()
    await fetchTrack()
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || '保存失败')
  }
}

function handleCancel() {
  if (hasChanges.value) {
    ElMessageBox.confirm('您有未保存的更改，确定要离开吗？', '确认离开', { type: 'warning' })
      .then(() => router.push(`/tracks/${trackId.value}`))
      .catch(() => {})
  } else {
    router.push(`/tracks/${trackId.value}`)
  }
}

// ==================== 撤销重做 ====================

function handleUndo() {
  store.undo()
}

function handleRedo() {
  store.redo()
}

// ==================== 轨道交互 ====================

function handleSegmentClick(segmentId: string) {
  store.selectSegment(segmentId)
}

function handleSegmentDoubleClick(segmentId: string, trackType: string, adminLevel?: string) {
  store.selectSegment(segmentId)

  // 找到对应的段落
  for (const track of store.tracks) {
    const segment = track.segments.find(s => s.id === segmentId)
    if (segment) {
      editDialogTrackType.value = track.type
      editDialogSegmentId.value = segmentId
      editDialogStartIndex.value = segment.startIndex
      editDialogEndIndex.value = segment.endIndex
      editDialogCurrentValue.value = segment.value
      editDialogCurrentValueEn.value = segment.valueEn
      editDialogVisible.value = true
      break
    }
  }
}

function handleSegmentHover(segmentId: string | null) {
  store.hoverSegment(segmentId)
}

// 段落编辑保存
function handleSegmentSave(data: any) {
  // 找到并更新段落
  for (const track of store.tracks) {
    const segment = track.segments.find(s => s.id === data.segmentId)
    if (segment) {
      // 记录操作前状态
      const before = JSON.parse(JSON.stringify(store.tracks))

      segment.value = data.value
      segment.valueEn = data.valueEn
      segment.isEdited = true

      // 如果是行政区划，级联清除下级
      if (data.trackType === 'province') {
        clearChildSegments('city', segment.startIndex, segment.endIndex)
        clearChildSegments('district', segment.startIndex, segment.endIndex)
      } else if (data.trackType === 'city') {
        clearChildSegments('district', segment.startIndex, segment.endIndex)
      }

      // 记录操作
      const after = JSON.parse(JSON.stringify(store.tracks))
      store.recordAction('edit', `编辑${track.label}`, before, after)

      ElMessage.success('段落已更新')
      break
    }
  }
}

// 清除下级段落
function clearChildSegments(childType: TrackType, startIndex: number, endIndex: number) {
  const childTrack = store.tracks.find(t => t.type === childType)
  if (!childTrack) return

  const before = JSON.parse(JSON.stringify(store.tracks))

  childTrack.segments.forEach(seg => {
    // 如果段落范围与修改范围重叠，清除该段落
    if (seg.startIndex <= endIndex && seg.endIndex >= startIndex) {
      seg.value = null
      seg.valueEn = null
      seg.isEdited = true
    }
  })

  const after = JSON.parse(JSON.stringify(store.tracks))
  store.recordAction('edit', `级联清除${childTrack.label}`, before, after)
}

// 边界调整（道路轨道独立）
function handleSegmentResize(segmentId: string, newStartIndex: number, newEndIndex: number) {
  const before = JSON.parse(JSON.stringify(store.tracks))

  for (const track of store.tracks) {
    const segment = track.segments.find(s => s.id === segmentId)
    if (segment) {
      segment.startIndex = newStartIndex
      segment.endIndex = newEndIndex
      segment.pointCount = newEndIndex - newStartIndex + 1
      segment.isEdited = true
      break
    }
  }

  const after = JSON.parse(JSON.stringify(store.tracks))
  store.recordAction('resize', '调整段落边界', before, after)
}

// 行政区划联动调整
function handleAdminResize(adminLevel: string, segmentId: string, newStartIndex: number, newEndIndex: number) {
  const before = JSON.parse(JSON.stringify(store.tracks))

  // 更新当前轨道
  for (const track of store.tracks) {
    const segment = track.segments.find(s => s.id === segmentId)
    if (segment && track.type === adminLevel) {
      segment.startIndex = newStartIndex
      segment.endIndex = newEndIndex
      segment.pointCount = newEndIndex - newStartIndex + 1
      segment.isEdited = true
      break
    }
  }

  // 级联更新下级轨道
  const childTypes: TrackType[] = []
  if (adminLevel === 'province') {
    childTypes.push('city', 'district')
  } else if (adminLevel === 'city') {
    childTypes.push('district')
  }

  childTypes.forEach(childType => {
    const childTrack = store.tracks.find(t => t.type === childType)
    if (!childTrack) return

    childTrack.segments.forEach(seg => {
      // 找到对应段落（范围与原段落重叠）
      // 简化处理：按比例调整
      // TODO: 实现完整的波纹剪辑逻辑
    })
  })

  const after = JSON.parse(JSON.stringify(store.tracks))
  store.recordAction('resize', `调整${adminLevel}边界`, before, after)
}

// ==================== 图表交互 ====================

function handleChartHighlight(dataIndex: number) {
  // 高亮对应段落
  // 找到包含该点的段落
  for (const track of store.tracks) {
    for (const segment of track.segments) {
      if (dataIndex >= segment.startIndex && dataIndex <= segment.endIndex) {
        store.selectSegment(segment.id)
        return
      }
    }
  }
}

// ==================== 缩放控制 ====================

function handleZoomIn() {
  zoomLevel.value = Math.min(zoomLevel.value * 1.5, 10)
}

function handleZoomOut() {
  zoomLevel.value = Math.max(zoomLevel.value / 1.5, 0.2)
}

function handleResetZoom() {
  zoomLevel.value = 1
  scrollLeft.value = 0
}

function handleToggleChart() {
  store.toggleChart()
}

function handleToggleTimeline() {
  store.toggleTimeline()
}

function handleTimeScaleChange(unit: 'time' | 'duration' | 'index') {
  store.setTimeScaleUnit(unit)
}

// ==================== 滚动同步 ====================

function handleScroll(e: Event) {
  const target = e.target as HTMLElement
  scrollLeft.value = target.scrollLeft
}

// ==================== 键盘快捷键 ====================

function handleKeydown(e: KeyboardEvent) {
  if (e.ctrlKey || e.metaKey) {
    if (e.key === 's') {
      e.preventDefault()
      handleSave()
    } else if (e.key === 'z') {
      e.preventDefault()
      if (e.shiftKey) {
        handleRedo()
      } else {
        handleUndo()
      }
    }
  }
}

// ==================== 生命周期 ====================

onMounted(() => {
  fetchTrack()
  document.addEventListener('keydown', handleKeydown)

  // 获取容器宽度
  nextTick(() => {
    const container = document.querySelector('.timeline-scroll-container')
    if (container) {
      containerWidth.value = container.offsetWidth - 60
    }
  })
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
})

// 离页确认
onBeforeRouteLeave((to, from, next) => {
  if (hasChanges.value) {
    ElMessageBox.confirm('有未保存的更改，要保存到服务器吗？', '提示', {
      confirmButtonText: '保存',
      cancelButtonText: '放弃',
      distinguishCancelAndClose: true
    }).then(() => {
      handleSave().then(() => next())
    }).catch((action) => {
      if (action === 'cancel') next()
    })
  } else {
    next()
  }
})
</script>

<template>
  <div class="geo-editor">
    <!-- Header -->
    <el-header class="geo-editor-header">
      <div class="header-left">
        <el-button class="nav-btn home-nav-btn" :icon="ArrowLeft" @click="handleCancel">
          返回
        </el-button>
        <el-button class="nav-btn" :icon="HomeFilled" @click="router.push('/')" />
      </div>

      <div class="header-center">
        <h1 class="header-title">
          <template v-if="track">{{ track.name }}</template>
          <template v-else>地理编辑器</template>
        </h1>
      </div>

      <div class="header-right">
        <el-button :icon="RefreshLeft" :disabled="!canUndo" @click="handleUndo" title="撤销 (Ctrl+Z)" />
        <el-button :icon="RefreshRight" :disabled="!canRedo" @click="handleRedo" title="重做 (Ctrl+Shift+Z)" />
        <el-button v-if="hasChanges" :icon="DocumentChecked" type="success" @click="handleSave">
          保存 (Ctrl+S)
        </el-button>
      </div>
    </el-header>

    <!-- Main Content -->
    <el-main class="geo-editor-main">
      <!-- 加载状态 -->
      <div v-if="loading" class="loading-container">
        <el-icon class="is-loading"><RefreshRight /></el-icon>
        <p>加载轨迹数据中...</p>
      </div>

      <!-- 错误状态 -->
      <div v-else-if="error" class="error-container">
        <p>{{ error }}</p>
        <el-button @click="fetchTrack">重试</el-button>
      </div>

      <!-- 编辑器内容 -->
      <div v-else-if="track && points.length > 0" class="editor-content">
        <!-- 地图 -->
        <div class="map-panel">
          <UniversalMap
            ref="mapRef"
            :tracks="mapTracks"
            :highlight-segment="highlightSegment"
            mode="detail"
          />
        </div>

        <!-- 图表区域 -->
        <div v-show="isChartExpanded" class="chart-panel">
          <div class="panel-header">
            <span class="panel-title">▼ 图表</span>
            <div class="panel-controls">
              <el-radio-group v-model="timeScaleUnit" size="small" @change="handleTimeScaleChange">
                <el-radio-button value="time">时间</el-radio-button>
                <el-radio-button value="duration">时长</el-radio-button>
                <el-radio-button value="index">点索引</el-radio-button>
              </el-radio-group>
              <el-button :icon="isChartExpanded ? ZoomIn : ZoomOut" size="small" text @click="handleToggleChart" />
            </div>
          </div>
          <div class="panel-content">
            <GeoChartPanel
              ref="chartPanelRef"
              :points="points"
              :time-scale-unit="timeScaleUnit"
              :highlighted-range="highlightSegment"
              @highlight="handleChartHighlight"
            />
          </div>
        </div>

        <!-- 时间轴区域 -->
        <div v-show="isTimelineExpanded" class="timeline-panel">
          <div class="panel-header">
            <span class="panel-title">▼ 时间轴</span>
            <div class="panel-controls">
              <el-button :icon="ZoomOut" size="small" text @click="handleZoomOut" title="缩小" />
              <el-button size="small" text @click="handleResetZoom">重置</el-button>
              <el-button :icon="ZoomIn" size="small" text @click="handleZoomIn" title="放大" />
              <el-button :icon="isTimelineExpanded ? ZoomIn : ZoomOut" size="small" text @click="handleToggleTimeline" />
            </div>
          </div>
          <div class="timeline-content">
            <div class="timeline-scroll-container" @scroll="handleScroll">
              <div
                class="timeline-tracks-content"
                :style="{ width: `${Math.max(containerWidth, points.length * PIXELS_PER_POINT * zoomLevel)}px` }"
              >
                <!-- 刻度尺 -->
                <TimeScaleRuler
                  :points="points"
                  :time-scale-unit="timeScaleUnit"
                  :container-width="Math.max(containerWidth, points.length * PIXELS_PER_POINT * zoomLevel)"
                  :scroll-left="scrollLeft"
                />

                <!-- 轨道 -->
                <TimelineTracks
                  :points="points"
                  :selected-segment-id="selectedSegmentId"
                  :hovered-segment-id="hoveredSegmentId"
                  @click="handleSegmentClick"
                  @dblclick="handleSegmentDoubleClick"
                  @hover="handleSegmentHover"
                  @resize="handleSegmentResize"
                  @admin-resize="handleAdminResize"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-main>

    <!-- 段落编辑对话框 -->
    <SegmentEditDialog
      v-model="editDialogVisible"
      :track-type="editDialogTrackType"
      :segment-id="editDialogSegmentId"
      :start-index="editDialogStartIndex"
      :end-index="editDialogEndIndex"
      :current-value="editDialogCurrentValue"
      :current-value-en="editDialogCurrentValueEn"
      @save="handleSegmentSave"
    />
  </div>
</template>

<style scoped>
.geo-editor {
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.geo-editor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--el-border-color);
}

.header-left,
.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.nav-btn {
  padding: 8px;
}

.home-nav-btn {
  margin-left: 0;
  margin-right: 12px;
}

.header-center {
  flex: 1;
  text-align: center;
}

.header-title {
  margin: 0;
  font-size: 18px;
  font-weight: 500;
}

.geo-editor-main {
  flex: 1;
  overflow: hidden;
  padding: 0;
  display: flex;
  flex-direction: column;
}

.loading-container,
.error-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 16px;
}

.editor-content {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.map-panel {
  flex: 1;
  overflow: hidden;
}

.chart-panel,
.timeline-panel {
  border-top: 1px solid var(--el-border-color);
  background: var(--el-bg-color-page);
}

.chart-panel {
  height: 120px;
}

.timeline-panel {
  height: 160px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 12px;
  background: var(--el-fill-color-light);
  border-bottom: 1px solid var(--el-border-color);
}

.panel-title {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.panel-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.panel-content {
  height: calc(100% - 32px);
  overflow: hidden;
}

.timeline-content {
  height: calc(100% - 32px);
}

.timeline-scroll-container {
  height: 100%;
  overflow-x: auto;
  overflow-y: hidden;
}

.timeline-scroll-container::-webkit-scrollbar {
  height: 8px;
}

.timeline-scroll-container::-webkit-scrollbar-thumb {
  background: var(--el-border-color-darker);
  border-radius: 4px;
}

.timeline-tracks-content {
  min-height: 100%;
}

@media (max-width: 768px) {
  .chart-panel {
    height: 100px;
  }

  .timeline-panel {
    height: 140px;
  }

  .panel-header {
    padding: 4px 8px;
  }
}
</style>
```

**Step 3: 验证修改**

Run: `grep -c "useGeoEditorStore" frontend/src/views/GeoEditor.vue`
Expected: 1

**Step 4: Commit**

```bash
git add frontend/src/views/GeoEditor.vue
git commit -m "refactor(geo-editor): rewrite main component with store, chart panel and collapse support"
```

---

## Task 7: 添加路由配置

**Files:**
- Modify: `frontend/src/router/index.ts`

**Step 1: 检查路由配置**

Run: `grep -A 3 "GeoEditor" frontend/src/router/index.ts`
Expected: 找到 GeoEditor 路由

如果不存在，添加路由：

```typescript
{
  path: '/tracks/:id/geo-editor',
  name: 'GeoEditor',
  component: () => import('@/views/GeoEditor.vue'),
  meta: { requiresAuth: true }
}
```

**Step 2: Commit**

```bash
git add frontend/src/router/index.ts
git commit -m "chore(geo-editor): ensure GeoEditor route is configured"
```

---

## Task 8: 后端添加获取编辑器数据 API

**Files:**
- Modify: `backend/app/api/geo_editor.py`

**Step 1: 添加 GET 端点**

在 `backend/app/api/geo_editor.py` 中添加：

```python
@router.get("/tracks/{track_id}/geo-editor")
async def get_geo_editor_data(
    track_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取轨迹的地理编辑器数据

    返回轨迹点的完整信息用于编辑器初始化
    """
    # 查询轨迹并验证权限
    stmt = select(Track).where(
        Track.id == track_id,
        Track.is_valid == True
    )
    result = await db.execute(stmt)
    track = result.scalar_one_or_none()

    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="轨迹不存在"
        )

    if track.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限访问此轨迹"
        )

    # 获取所有轨迹点
    stmt = select(TrackPoint).where(
        TrackPoint.track_id == track_id,
        TrackPoint.is_valid == True
    ).order_by(TrackPoint.point_index)

    result = await db.execute(stmt)
    points = result.scalars().all()

    # 计算总时长
    total_duration = 0
    if points and len(points) >= 2:
        first_time = points[0].time
        last_time = points[-1].time
        if first_time and last_time:
            total_duration = int((last_time - first_time).total_seconds() * 1000)

    from app.schemas.geo_editor import GeoEditorDataResponse
    return GeoEditorDataResponse(
        track_id=track_id,
        points=[{
            "point_index": p.point_index,
            "time": p.time.isoformat() if p.time else None,
            "latitude": p.latitude,
            "longitude": p.longitude,
            "elevation": p.elevation,
            "speed": p.speed,
            "province": p.province,
            "city": p.city,
            "district": p.district,
            "province_en": p.province_en,
            "city_en": p.city_en,
            "district_en": p.district_en,
            "road_number": p.road_number,
            "road_name": p.road_name,
            "road_name_en": p.road_name_en,
        } for p in points],
        total_duration=total_duration
    )
```

**Step 2: 更新 Schema**

在 `backend/app/schemas/geo_editor.py` 中添加：

```python
class GeoEditorDataResponse(BaseModel):
    """地理编辑器数据响应"""
    track_id: int = Field(..., description="轨迹ID")
    points: List["TrackPointGeoData"] = Field(..., description="轨迹点列表")
    total_duration: int = Field(..., description="总时长（毫秒）")


class TrackPointGeoData(BaseModel):
    """轨迹点地理数据"""
    point_index: int
    time: str | None
    latitude: float
    longitude: float
    elevation: float | None
    speed: float | None
    province: str | None
    city: str | None
    district: str | None
    province_en: str | None
    city_en: str | None
    district_en: str | None
    road_number: str | None
    road_name: str | None
    road_name_en: str | None
```

**Step 3: 验证修改**

Run: `grep -c "get_geo_editor_data" backend/app/api/geo_editor.py`
Expected: 1

**Step 4: Commit**

```bash
git add backend/app/api/geo_editor.py backend/app/schemas/geo_editor.py
git commit -m "feat(geo-editor): add GET endpoint for editor initialization data"
```

---

## Task 9: 测试与验证

**Files:**
- None (测试步骤)

**Step 1: 启动后端**

```bash
cd backend
python -m uvicorn app.main:app --reload
```

Expected: 服务运行在 http://localhost:8000

**Step 2: 启动前端**

```bash
cd frontend
npm run dev
```

Expected: 服务运行在 http://localhost:5173

**Step 3: 手动测试清单**

1. 访问 `/tracks/{id}/geo-editor` 页面
2. 验证地图显示正常
3. 验证图表区域显示海拔和速度曲线
4. 验证时间轴显示 5 条轨道
5. 验证刻度切换（时间/时长/点索引）
6. 验证折叠功能（图表/时间轴）
7. 验证双击段落打开编辑对话框
8. 验证编辑后显示"未保存"状态
9. 验证 Ctrl+Z 撤销、Ctrl+Shift+Z 重做
10. 验证保存功能

**Step 4: 创建测试报告**

如果有问题，记录到 `docs/plans/geo-editor-test-issues.md`

**Step 5: Commit**

```bash
git commit --allow-empty -m "test(geo-editor): complete manual testing verification"
```

---

## Task 10: 更新组件类型声明

**Files:**
- Modify: `frontend/src/components.d.ts`

**Step 1: 添加新组件类型声明**

如果文件不存在或需要更新，添加：

```typescript
declare module '@/*/components/geo-editor/GeoChartPanel.vue' {
  import { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

declare module '@/*/components/geo-editor/TimeScaleRuler.vue' {
  import { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}
```

**Step 2: Commit**

```bash
git add frontend/src/components.d.ts
git commit -m "chore(geo-editor): update component type declarations"
```

---

## 总结

实施计划包含以下主要任务：

1. ✅ 创建 Pinia Store（状态管理、撤销重做）
2. ✅ 创建图表面板组件（海拔/速度曲线）
3. ✅ 创建刻度尺组件（时间/时长/点索引）
4. ✅ 重写编辑对话框（单字段编辑）
5. ✅ 更新时间轴组件（层级联动）
6. ✅ 重写主页面（集成所有功能）
7. ✅ 路由配置
8. ✅ 后端 API 扩展
9. ✅ 测试与验证
10. ✅ 类型声明更新

**预计工作量**: 约 4-6 小时
**关键风险**:
- 波纹剪辑的完整联动逻辑较复杂，可能需要额外时间
- ECharts 图表性能在大数据量下可能需要优化
- 撤销重做存储在 LocalStorage 可能有大小限制

**后续优化方向**:
- 完整的波纹剪辑逻辑（段落的拆分/合并）
- IndexedDB 替代 LocalStorage 存储历史
- 虚拟滚动优化长轨迹性能
- 批量操作功能（如"应用到后续相同段落"）
