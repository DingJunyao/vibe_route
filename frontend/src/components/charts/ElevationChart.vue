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

  // 判断是否为移动端
  const isMobile = window.innerWidth <= 1366

  // 移动端数据采样：数据点过多时进行降采样
  let sampledData = props.data
  let highlightOffset = 0

  if (isMobile && props.data.length > 80) {
    // 移动端使用更激进的采样：目标约 40-50 个点
    const targetPoints = 45
    const step = Math.ceil(props.data.length / targetPoints)
    sampledData = props.data.filter((_p: DataPoint, index: number) => index % step === 0)

    // 计算高亮索引的偏移量
    if (props.highlightIndex !== null) {
      highlightOffset = Math.floor(props.highlightIndex / step)
    }
  }

  // 提取数据
  const elevations = sampledData.map((p: DataPoint) => p.elevation)
  const speeds = sampledData.map((p: DataPoint) => p.speed)

  // 计算最小和最大海拔
  const validElevations = elevations.filter((e: number | null) => e !== null)
  const minElevation = Math.min(...validElevations)
  const maxElevation = Math.max(...validElevations)

  // 构建图表配置
  const option: EChartsOption = {
    grid: {
      left: isMobile ? '30px' : '50px',
      right: isMobile ? '15px' : '50px',
      top: '15px',
      bottom: isMobile ? '20px' : '30px',
      containLabel: false,
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
      },
      formatter: (params: any) => {
        if (!Array.isArray(params)) return ''
        const point = sampledData[params[0].dataIndex]
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
      type: 'value',
      min: 0,
      max: sampledData.length - 1,
      show: false, // 完全隐藏 x 轴
    },
    yAxis: [
      {
        type: 'value',
        name: isMobile ? 'm' : '海拔 (m)',
        scale: true,
        splitLine: {
          lineStyle: {
            color: '#e5e7eb',
          },
        },
        axisLabel: {
          formatter: '{value}',
          fontSize: isMobile ? 9 : 12,
        },
        min: (minElevation - 50).toFixed(0),
        max: (maxElevation + 50).toFixed(0),
        splitNumber: isMobile ? 3 : 5,
      },
    ],
    series: [
      {
        name: '海拔',
        type: 'line',
        data: elevations,
        smooth: !isMobile,
        sampling: isMobile ? 'lttb' : null, // 移动端使用 LTTB 降采样算法
        symbol: 'none',
        lineStyle: {
          color: '#3b82f6',
          width: isMobile ? 1 : 2,
        },
        areaStyle: isMobile ? undefined : {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(59, 130, 246, 0.3)' },
            { offset: 1, color: 'rgba(59, 130, 246, 0.05)' },
          ]),
        },
        markPoint: props.highlightIndex !== null
          ? [
              {
                xAxis: highlightOffset,
                yAxis: elevations[highlightOffset],
                symbol: 'circle',
                symbolSize: 8,
                itemStyle: {
                  color: '#ef4444',
                },
              },
            ]
          : undefined,
      },
    ],
    dataZoom: isMobile
      ? [
          {
            type: 'inside',
            start: 0,
            end: 100,
            zoomOnMouseWheel: true,
            moveOnMouseMove: true,
          },
        ]
      : [
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
        name: isMobile ? 'km/h' : '速度 (km/h)',
        position: 'right',
        splitLine: { show: false },
        axisLabel: {
          formatter: '{value}',
          fontSize: isMobile ? 9 : 12,
        },
        splitNumber: isMobile ? 3 : 5,
      },
    ]
    option.series!.push({
      name: '速度',
      type: 'line',
      data: speeds.map((s) => (s !== null ? s * 3.6 : null)),
      smooth: !isMobile,
      sampling: isMobile ? 'lttb' : null,
      symbol: 'none',
      lineStyle: {
        color: '#10b981',
        width: isMobile ? 1 : 2,
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
