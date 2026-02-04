<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'

interface Props {
  points: any[]
  timeScaleUnit: 'time' | 'duration' | 'index'
  highlightedRange?: { start: number; end: number } | null
  zoomStart: number
  zoomEnd: number
  pointerPosition: number
}

const props = defineProps<Props>()

const emit = defineEmits<{
  highlight: [dataIndex: number]
}>()

const chartRef = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

// 计算图表数据（只显示当前缩放范围内的数据）
const chartData = computed(() => {
  if (props.points.length === 0) return { xAxis: [], elevation: [], speed: [] }

  const totalPoints = props.points.length
  const startIndex = Math.floor(totalPoints * props.zoomStart)
  const endIndex = Math.ceil(totalPoints * props.zoomEnd)
  const visiblePoints = props.points.slice(startIndex, endIndex)

  const xAxis: string[] = []
  const elevation: number[] = []
  const speed: number[] = []

  let startTime = props.points[0]?.time ? new Date(props.points[0].time).getTime() : 0

  visiblePoints.forEach((point, index) => {
    const actualIndex = startIndex + index

    if (props.timeScaleUnit === 'index') {
      xAxis.push(actualIndex.toString())
    } else if (props.timeScaleUnit === 'duration') {
      const pointTime = point.time ? new Date(point.time).getTime() : startTime
      const duration = pointTime - startTime
      xAxis.push(formatDuration(duration))
    } else {
      xAxis.push(point.time ? formatTime(point.time) : actualIndex.toString())
    }

    elevation.push(point.elevation ?? 0)
    speed.push(point.speed != null ? point.speed * 3.6 : 0)
  })

  return { xAxis, elevation, speed, startIndex }
})

// 格式化时长：统一使用 HH:MM:SS 格式
function formatDuration(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60

  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
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
      left: 50,   // 左侧Y轴名称和标签空间
      right: 50,  // 右侧Y轴名称和标签空间
      top: 5,
      bottom: 5,
      containLabel: false,
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
      },
      formatter: (params: any) => {
        if (!Array.isArray(params) || params.length === 0) return ''

        const dataIndex = params[0].dataIndex
        const actualIndex = chartData.value.startIndex + dataIndex
        const point = props.points[actualIndex]

        let result = `点 #${actualIndex}<br/>`
        if (point?.time) {
          result += `时间: ${formatTime(point.time)}<br/>`
        }

        for (const param of params) {
          if (param.seriesName === '海拔') {
            const value = param.value !== null && param.value !== undefined
              ? param.value.toFixed(1)
              : '-'
            result += `${param.marker}${param.seriesName}: ${value} m<br/>`
          } else if (param.seriesName === '速度') {
            const value = param.value !== null && param.value !== undefined
              ? param.value.toFixed(1)
              : '-'
            result += `${param.marker}${param.seriesName}: ${value} km/h<br/>`
          }
        }

        return result
      },
    },
    xAxis: {
      type: 'category',
      data: chartData.value.xAxis,
      show: false,  // 隐藏 x 轴，由时间刻度组件负责显示
    },
    yAxis: [
      {
        type: 'value',
        name: '海拔 (m)',
        position: 'left',
        nameLocation: 'middle',
        nameGap: 40,
        nameTextStyle: {
          fontSize: 10,
          padding: [0, 0, 0, 0],
        },
        axisLabel: {
          formatter: '{value}',
          fontSize: 10,
        },
        splitLine: {
          show: true,
          lineStyle: { type: 'dashed', color: '#e0e0e0' },
        },
      },
      {
        type: 'value',
        name: '速度 (km/h)',
        position: 'right',
        nameLocation: 'middle',
        nameGap: 32,
        nameTextStyle: {
          fontSize: 10,
          padding: [0, 0, 0, 0],
        },
        axisLabel: {
          formatter: '{value}',
          fontSize: 10,
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
      const actualIndex = chartData.value.startIndex + params.dataIndex
      emit('highlight', actualIndex)
    }
  })
}

// 监听变化
watch(() => [chartData.value, props.timeScaleUnit, props.highlightedRange], () => {
  updateChart()
}, { deep: true })

// 监听指针位置变化，同步显示 tooltip
watch(() => props.pointerPosition, (newPosition) => {
  if (!chart || !chartData.value || chartData.value.xAxis.length === 0) return

  // 计算指针对应的可见数据索引
  const totalPoints = props.points.length
  const startIndex = Math.floor(totalPoints * props.zoomStart)
  const endIndex = Math.ceil(totalPoints * props.zoomEnd)
  const visibleCount = endIndex - startIndex

  // 指针在可见区域中的位置 (0-1)
  const visiblePosition = (newPosition - props.zoomStart) / (props.zoomEnd - props.zoomStart)
  const visibleIndex = Math.floor(visiblePosition * visibleCount)

  // 限制在有效范围内
  const clampedIndex = Math.max(0, Math.min(visibleIndex, visibleCount - 1))

  // 显示 tooltip
  chart.dispatchAction({
    type: 'showTip',
    seriesIndex: 0,
    dataIndex: clampedIndex,
  })
})

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
defineExpose({ refresh: () => { nextTick(() => initChart()) } })
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
  padding-left: var(--geo-editor-label-width);
  padding-right: 0;
  box-sizing: border-box;
  touch-action: none;
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
