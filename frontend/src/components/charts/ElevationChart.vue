<template>
  <div ref="chartContainer" class="elevation-chart"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'

interface DataPoint {
  index: number
  time: string | null
  elevation: number | null
  distance: number | null
  speed: number | null
}

interface Props {
  data: DataPoint[]
  height?: string
  showSpeed?: boolean
  highlightIndex?: number | null
}

const props = withDefaults(defineProps<Props>(), {
  height: '300px',
  showSpeed: false,
  highlightIndex: null,
})

const chartContainer = ref<HTMLElement>()
let chart: echarts.ECharts | null = null

function initChart() {
  if (!chartContainer.value) return

  chart = echarts.init(chartContainer.value)
  updateChart()

  // 监听窗口大小变化
  window.addEventListener('resize', () => {
    chart?.resize()
  })
}

function updateChart() {
  if (!chart || !props.data || props.data.length === 0) return

  // 提取数据
  const distances = props.data.map((p) => p.distance)
  const elevations = props.data.map((p) => p.elevation)
  const speeds = props.data.map((p) => p.speed)

  // 计算最小和最大海拔
  const minElevation = Math.min(...elevations.filter((e) => e !== null))
  const maxElevation = Math.max(...elevations.filter((e) => e !== null))

  // 构建图表配置
  const option: EChartsOption = {
    grid: {
      left: '50px',
      right: '50px',
      top: '30px',
      bottom: '30px',
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
      },
      formatter: (params: any) => {
        if (!Array.isArray(params)) return ''
        const point = props.data[params[0].dataIndex]
        let html = `<strong>点 ${point.index}</strong><br/>`
        if (point.time) {
          html += `时间: ${point.time}<br/>`
        }
        if (point.elevation !== null) {
          html += `海拔: ${point.elevation.toFixed(1)} m<br/>`
        }
        if (point.distance !== null) {
          html += `距离: ${(point.distance / 1000).toFixed(2)} km<br/>`
        }
        if (point.speed !== null) {
          html += `速度: ${(point.speed * 3.6).toFixed(1)} km/h`
        }
        return html
      },
    },
    xAxis: {
      type: 'category',
      data: props.data.map((p) => p.index),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { show: false },
    },
    yAxis: [
      {
        type: 'value',
        name: '海拔 (m)',
        scale: true,
        splitLine: {
          lineStyle: {
            color: '#e5e7eb',
          },
        },
        axisLabel: {
          formatter: '{value}',
        },
        min: (minElevation - 50).toFixed(0),
        max: (maxElevation + 50).toFixed(0),
      },
    ],
    series: [
      {
        name: '海拔',
        type: 'line',
        data: elevations,
        smooth: true,
        symbol: 'none',
        lineStyle: {
          color: '#3b82f6',
          width: 2,
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(59, 130, 246, 0.3)' },
            { offset: 1, color: 'rgba(59, 130, 246, 0.05)' },
          ]),
        },
        markPoint: props.highlightIndex !== null
          ? [
              {
                coord: [props.highlightIndex, elevations[props.highlightIndex]],
                symbol: 'circle',
                symbolSize: 10,
                itemStyle: {
                  color: '#ef4444',
                },
              },
            ]
          : undefined,
      },
    ],
    dataZoom: [
      {
        type: 'inside',
        start: 0,
        end: 100,
      },
      {
        start: 0,
        end: 100,
        height: 20,
        bottom: 0,
      },
    ],
  }

  // 如果显示速度，添加第二个 Y 轴
  if (props.showSpeed) {
    option.yAxis = [
      option.yAxis![0],
      {
        type: 'value',
        name: '速度 (km/h)',
        position: 'right',
        splitLine: { show: false },
        axisLabel: {
          formatter: '{value}',
        },
      },
    ]
    option.series!.push({
      name: '速度',
      type: 'line',
      data: speeds.map((s) => (s !== null ? s * 3.6 : null)), // 转换为 km/h
      smooth: true,
      symbol: 'none',
      lineStyle: {
        color: '#10b981',
        width: 2,
      },
    })
  }

  chart.setOption(option)
}

// 监听数据变化
watch(
  () => [props.data, props.highlightIndex],
  () => {
    updateChart()
  },
  { deep: true }
)

onMounted(() => {
  initChart()
})

onUnmounted(() => {
  if (chart) {
    chart.dispose()
    chart = null
  }
  window.removeEventListener('resize', () => {})
})

// 暴露方法
defineExpose({
  resize: () => {
    chart?.resize()
  },
  highlightPoint: (index: number) => {
    if (chart && props.data.length > 0) {
      chart.dispatchAction({
        type: 'downplay',
        seriesIndex: 0,
        dataIndex: index,
      })
      chart.dispatchAction({
        type: 'highlight',
        seriesIndex: 0,
        dataIndex: index,
      })
    }
  },
  downplayPoint: (index: number) => {
    if (chart) {
      chart.dispatchAction({
        type: 'downplay',
        seriesIndex: 0,
        dataIndex: index,
      })
    }
  },
})
</script>

<style scoped>
.elevation-chart {
  width: 100%;
  height: v-bind(height);
}
</style>
