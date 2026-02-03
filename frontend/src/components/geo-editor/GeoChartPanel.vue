<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'

interface Props {
  points: any[]
  timeScaleUnit: 'time' | 'duration' | 'index'
  highlightedRange?: { start: number; end: number } | null
}

const props = defineProps<Props>()

const emit = defineEmits<{
  highlight: [dataIndex: number]
}>()

const chartRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

// 缩放范围 (0-1)
const zoomStart = ref(0)
const zoomEnd = ref(1)

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
      label = point.time ? formatTime(point.time) : index.toString()
    }

    xAxis.push(label)
    elevation.push(point.elevation ?? 0)
    // 速度从 m/s 转换为 km/h
    speed.push(point.speed != null ? point.speed * 3.6 : 0)
  })

  return { xAxis, elevation, speed }
})

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

// 初始化图表
function initChart() {
  if (!chartRef.value) return

  if (chart) {
    chart.dispose()
    chart = null
  }

  chart = echarts.init(chartRef.value)
  updateChart()
  setupChartEvents()
}

// 更新图表
function updateChart() {
  if (!chart) return

  const option: EChartsOption = {
    grid: {
      left: 60,
      right: 20,
      top: 10,
      bottom: 30,
      containLabel: false,
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
      },
    },
    dataZoom: [
      {
        type: 'inside',
        start: Math.round(zoomStart.value * 100),
        end: Math.round(zoomEnd.value * 100),
        zoomOnMouseWheel: false,  // 禁用鼠标滚轮缩放，改为手动控制
        moveOnMouseMove: false,
        moveOnMouseWheel: false,
      },
    ],
    xAxis: {
      type: 'category',
      data: chartData.value.xAxis,
      axisLabel: {
        formatter: (value: string, index: number) => {
          // 简化显示，只显示部分标签
          if (chartData.value.xAxis.length > 20) {
            const step = Math.ceil(chartData.value.xAxis.length / 10)
            return index % step === 0 ? value : ''
          }
          return value
        },
      },
    },
    yAxis: [
      {
        type: 'value',
        name: '海拔 (m)',
        position: 'left',
        axisLabel: {
          formatter: '{value}',
        },
        splitLine: {
          show: true,
          lineStyle: { type: 'dashed', color: '#e0e0e0' },
        },
      },
      {
        type: 'value',
        name: '速度 (km/h)',
        position: 'left',
        offset: 50,  // 向右偏移，避免与海拔轴重叠
        axisLabel: {
          formatter: '{value}',
        },
        splitLine: {
          show: false,
        },
      },
    ],
    series: [
      {
        name: '海拔',
        type: 'line',
        yAxisIndex: 0,
        data: chartData.value.elevation,
        showSymbol: false,
        lineStyle: {
          width: 2,
          color: '#409eff',
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(64, 158, 255, 0.3)' },
              { offset: 1, color: 'rgba(64, 158, 255, 0.05)' },
            ],
          },
        },
      },
      {
        name: '速度',
        type: 'line',
        yAxisIndex: 1,
        data: chartData.value.speed,
        showSymbol: false,
        lineStyle: {
          width: 2,
          color: '#67c23a',
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(103, 194, 58, 0.3)' },
              { offset: 1, color: 'rgba(103, 194, 58, 0.05)' },
            ],
          },
        },
      },
    ],
  }

  chart.setOption(option, true)
}

// 图表事件处理
function setupChartEvents() {
  if (!chart) return

  chart.on('click', (params: any) => {
    if (params.dataIndex !== undefined) {
      emit('highlight', params.dataIndex)
    }
  })
}

// 缩放控制
function zoomIn() {
  const range = zoomEnd.value - zoomStart.value
  const center = (zoomStart.value + zoomEnd.value) / 2
  const newRange = range * 0.8
  zoomStart.value = Math.max(0, center - newRange / 2)
  zoomEnd.value = Math.min(1, center + newRange / 2)
  updateChart()
}

function zoomOut() {
  const range = zoomEnd.value - zoomStart.value
  const center = (zoomStart.value + zoomEnd.value) / 2
  const newRange = Math.min(1, range * 1.25)
  zoomStart.value = Math.max(0, center - newRange / 2)
  zoomEnd.value = Math.min(1, center + newRange / 2)
  updateChart()
}

function resetZoom() {
  zoomStart.value = 0
  zoomEnd.value = 1
  updateChart()
}

// 监听变化
watch(() => [chartData.value, props.timeScaleUnit, props.highlightedRange], () => {
  updateChart()
}, { deep: true })

// 窗口大小变化
function handleResize() {
  chart?.resize()
}

onMounted(() => {
  nextTick(() => {
    initChart()
  })
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  chart?.dispose()
  window.removeEventListener('resize', handleResize)
})

// 暴露方法
defineExpose({ refresh: () => { nextTick(() => initChart()) }, zoomIn, zoomOut, resetZoom })
</script>

<template>
  <div v-if="points.length > 0" ref="chartRef" class="geo-chart-panel" />
  <div v-else class="chart-empty">
    <span>无数据</span>
  </div>
</template>

<style scoped>
.geo-chart-panel {
  width: 100%;
  height: 100%;
}

.chart-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--el-text-color-placeholder);
  font-size: 12px;
}
</style>
