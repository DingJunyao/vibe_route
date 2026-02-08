<template>
  <div class="pen-tool-map">
    <UniversalMap
      ref="mapRef"
      :tracks="[fullTrack]"
      :custom-overlays="mapOverlays"
      :disable-point-hover="true"
      mode="detail"
      @map-click="handleMapClick"
    />

    <!-- 工具栏 -->
    <div class="pen-toolbar">
      <el-button-group>
        <el-button
          :type="handlesLocked ? 'primary' : ''"
          size="small"
          @click="toggleHandlesLocked"
        >
          <el-icon><Lock v-if="handlesLocked" /><Unlock v-else /></el-icon>
          <span class="btn-text">手柄锁定</span>
        </el-button>
        <el-button
          size="small"
          :disabled="selectedPointIndex === null"
          @click="deleteSelectedPoint"
        >
          <el-icon><Delete /></el-icon>
          <span class="btn-text">删除点</span>
        </el-button>
      </el-button-group>
    </div>

    <!-- 提示信息 -->
    <div class="pen-hint">
      点击地图添加控制点，拖拽调整位置
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import UniversalMap from '@/components/map/UniversalMap.vue'
import { CubicBezierCurve, type BezierControlPoint } from '@/utils/bezierCurve'
import { Lock, Unlock, Delete } from '@element-plus/icons-vue'
import { wgs84ToGcj02, wgs84ToBd09 } from '@/utils/coordTransform'

interface PointData {
  lng: number
  lat: number
  index: number
  time: string
  // 多坐标系支持（用于地图覆盖层）
  latitude_wgs84?: number
  longitude_wgs84?: number
  latitude_gcj02?: number | null
  longitude_gcj02?: number | null
  latitude_bd09?: number | null
  longitude_bd09?: number | null
}

interface TrackPoint {
  point_index: number
  latitude_wgs84: number
  longitude_wgs84: number
  latitude: number
  longitude: number
  elevation: number | null
  time: string | null
  speed: number | null
}

interface ControlPointData {
  lng: number
  lat: number
  inHandle: { dx: number; dy: number }
  outHandle: { dx: number; dy: number }
  handlesLocked: boolean
  // 多坐标系支持（用于地图覆盖层）
  latitude_wgs84?: number
  longitude_wgs84?: number
  latitude_gcj02?: number | null
  longitude_gcj02?: number | null
  latitude_bd09?: number | null
  longitude_bd09?: number | null
}

interface Props {
  trackId: number
  startPoint: PointData
  endPoint: PointData
  controlPoints: ControlPointData[]
  trackPoints?: TrackPoint[]  // 完整轨迹点数据
  editable?: boolean  // 是否可编辑（预览模式下禁用）
}

interface Emits {
  (e: 'update:controlPoints', points: ControlPointData[]): void
}

const props = withDefaults(defineProps<Props>(), {
  trackPoints: () => [],
  editable: true
})
const emit = defineEmits<Emits>()

// 状态
const mapRef = ref()
const selectedPointIndex = ref<number | null>(null)
const handlesLocked = ref(true)
const hasAutoFocused = ref(false)  // 标记是否已自动聚焦过

// 完整轨迹数据（用于显示完整路径，淡色 60%）
const fullTrack = computed(() => {
  if (!props.trackPoints || props.trackPoints.length === 0) {
    return { id: 'full-track', points: [] }
  }

  return {
    id: 'full-track',
    opacity: 0.4,  // 整个轨迹淡 60%
    color: '#999999',  // 灰色，与蓝色插值连线区分
    points: props.trackPoints.map(p => ({
      // 主坐标使用 WGS84（Leaflet/OSM 会用这个）
      latitude: p.latitude_wgs84,
      longitude: p.longitude_wgs84,
      // 各坐标系坐标
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
  }
})

// 区段轨迹数据（用于聚焦缩放，不实际显示）
const segmentTrack = computed(() => {
  if (!props.trackPoints || props.trackPoints.length === 0) {
    return { id: 'segment-track', points: [] }
  }

  // 只包含区段内的点
  const startIndex = props.startPoint?.index ?? 0
  const endIndex = props.endPoint?.index ?? props.trackPoints.length - 1

  const segmentPoints = props.trackPoints
    .filter(p => p.point_index >= startIndex && p.point_index <= endIndex)
    .map(p => ({
      latitude: p.latitude_wgs84,
      longitude: p.longitude_wgs84,
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

  return {
    id: String(props.trackId),
    points: segmentPoints
  }
})

// 转换后的轨迹数据（兼容旧代码）
const trackWithPoints = computed(() => segmentTrack.value)

// 聚焦边界（用于自动缩放到区段）
const focusBounds = computed(() => {
  if (!props.trackPoints || props.trackPoints.length === 0) return null

  const startIndex = props.startPoint?.index ?? 0
  const endIndex = props.endPoint?.index ?? props.trackPoints.length - 1

  // 获取区段内的点
  const segmentPoints = props.trackPoints
    .filter(p => p.point_index >= startIndex && p.point_index <= endIndex)

  if (segmentPoints.length === 0) return null

  // 计算边界
  let minLat = Infinity, maxLat = -Infinity
  let minLon = Infinity, maxLon = -Infinity

  for (const p of segmentPoints) {
    const lat = p.latitude_wgs84
    const lon = p.longitude_wgs84
    minLat = Math.min(minLat, lat)
    maxLat = Math.max(maxLat, lat)
    minLon = Math.min(minLon, lon)
    maxLon = Math.max(maxLon, lon)
  }

  return { minLat, maxLat, minLon, maxLon }
})

// 构建曲线点序列
const curvePoints = computed(() => {
  const points: Array<{ lng: number; lat: number }> = [
    { lng: props.startPoint.lng, lat: props.startPoint.lat }
  ]

  for (const cp of props.controlPoints) {
    points.push({ lng: cp.lng, lat: cp.lat })
  }

  points.push({ lng: props.endPoint.lng, lat: props.endPoint.lat })
  return points
})

// 曲线实例
const curve = computed(() => {
  return new CubicBezierCurve(curvePoints.value)
})

// 预览点（用于显示曲线路径）
const previewPoints = computed(() => {
  if (props.controlPoints.length === 0) {
    // 无控制点时，显示直线
    return [
      { lng: props.startPoint.lng, lat: props.startPoint.lat },
      { lng: props.endPoint.lng, lat: props.endPoint.lat }
    ]
  }
  return curve.value.generatePoints(50)
})

// 地图覆盖层
const mapOverlays = computed(() => {
  const overlays: any[] = []

  // 调试：记录起点和终点数据
  console.log('[PenToolMap] mapOverlays computed - startPoint:', props.startPoint, 'endPoint:', props.endPoint, 'controlPoints:', props.controlPoints.length)

  // 起点标记（蓝色圆点）
  overlays.push({
    type: 'marker',
    position: [props.startPoint.lat, props.startPoint.lng],  // 默认 WGS84
    // 多坐标系支持
    latitude_wgs84: props.startPoint.lat,
    longitude_wgs84: props.startPoint.lng,
    latitude_gcj02: props.startPoint.latitude_gcj02,
    longitude_gcj02: props.startPoint.longitude_gcj02,
    latitude_bd09: props.startPoint.latitude_bd09,
    longitude_bd09: props.startPoint.longitude_bd09,
    icon: {
      type: 'circle',
      radius: 8,
      fillColor: '#409eff',
      fillOpacity: 1,
      strokeColor: '#fff',
      strokeWidth: 2
    },
    label: 'A'
  })

  // 终点标记（绿色圆点）
  overlays.push({
    type: 'marker',
    position: [props.endPoint.lat, props.endPoint.lng],  // 默认 WGS84
    // 多坐标系支持
    latitude_wgs84: props.endPoint.lat,
    longitude_wgs84: props.endPoint.lng,
    latitude_gcj02: props.endPoint.latitude_gcj02,
    longitude_gcj02: props.endPoint.longitude_gcj02,
    latitude_bd09: props.endPoint.latitude_bd09,
    longitude_bd09: props.endPoint.longitude_bd09,
    icon: {
      type: 'circle',
      radius: 8,
      fillColor: '#67c23a',
      fillOpacity: 1,
      strokeColor: '#fff',
      strokeWidth: 2
    },
    label: 'B'
  })

  // 控制点标记
  props.controlPoints.forEach((cp, index) => {
    const isSelected = index === selectedPointIndex.value
    overlays.push({
      type: 'marker',
      position: [cp.lat, cp.lng],  // 默认 WGS84
      // 多坐标系支持
      latitude_wgs84: cp.latitude_wgs84 ?? cp.lat,
      longitude_wgs84: cp.longitude_wgs84 ?? cp.lng,
      latitude_gcj02: cp.latitude_gcj02,
      longitude_gcj02: cp.longitude_gcj02,
      latitude_bd09: cp.latitude_bd09,
      longitude_bd09: cp.longitude_bd09,
      icon: {
        type: 'circle',
        radius: isSelected ? 8 : 6,
        fillColor: isSelected ? '#e6a23c' : '#f56c6c',
        fillOpacity: 0.9,
        strokeColor: '#fff',
        strokeWidth: 2
      },
      label: String(index + 1)
    })
  })

  // 曲线路径（为多坐标系支持，转换 WGS84 坐标到 GCJ02/BD09）
  if (previewPoints.value.length > 1) {
    const wgs84Positions = previewPoints.value.map(p => [p.lat, p.lng] as [number, number])
    const gcj02Positions: Array<[number, number]> = []
    const bd09Positions: Array<[number, number]> = []

    // 转换坐标
    for (const p of previewPoints.value) {
      const [gcjLng, gcjLat] = wgs84ToGcj02(p.lng, p.lat)
      const [bdLng, bdLat] = wgs84ToBd09(p.lng, p.lat)
      gcj02Positions.push([gcjLat, gcjLng])
      bd09Positions.push([bdLat, bdLng])
    }

    overlays.push({
      type: 'polyline',
      positions: wgs84Positions,  // WGS84（Leaflet/OSM）
      positions_gcj02: gcj02Positions,  // GCJ02（高德、腾讯）
      positions_bd09: bd09Positions,  // BD09（百度）
      color: '#409eff',
      weight: 3,
      opacity: 0.8
    })
  }

  return overlays
})

// 添加控制点
function addControlPoint(lng: number, lat: number) {
  // 转换为其他坐标系
  const [gcjLng, gcjLat] = wgs84ToGcj02(lng, lat)
  const [bdLng, bdLat] = wgs84ToBd09(lng, lat)

  const newPoint: ControlPointData = {
    lng,
    lat,
    inHandle: { dx: -0.001, dy: 0 },
    outHandle: { dx: 0.001, dy: 0 },
    handlesLocked: true,
    // 多坐标系支持
    latitude_wgs84: lat,
    longitude_wgs84: lng,
    latitude_gcj02: gcjLat,
    longitude_gcj02: gcjLng,
    latitude_bd09: bdLat,
    longitude_bd09: bdLng
  }
  emit('update:controlPoints', [...props.controlPoints, newPoint])
  selectedPointIndex.value = props.controlPoints.length
}

// 处理地图点击事件
function handleMapClick(lng: number, lat: number) {
  if (!props.editable) return  // 预览模式下禁用
  addControlPoint(lng, lat)
}

// 更新控制点位置
function updateControlPoint(index: number, lng: number, lat: number) {
  // 转换为其他坐标系
  const [gcjLng, gcjLat] = wgs84ToGcj02(lng, lat)
  const [bdLng, bdLat] = wgs84ToBd09(lng, lat)

  const updated = [...props.controlPoints]
  updated[index] = {
    ...updated[index],
    lng,
    lat,
    latitude_wgs84: lat,
    longitude_wgs84: lng,
    latitude_gcj02: gcjLat,
    longitude_gcj02: gcjLng,
    latitude_bd09: bdLat,
    longitude_bd09: bdLng
  }
  emit('update:controlPoints', updated)
}

// 删除选中的控制点
function deleteSelectedPoint() {
  if (selectedPointIndex.value === null) return
  const updated = props.controlPoints.filter((_, i) => i !== selectedPointIndex.value)
  emit('update:controlPoints', updated)
  selectedPointIndex.value = null
}

// 切换手柄锁定
function toggleHandlesLocked() {
  handlesLocked.value = !handlesLocked.value
}

// 居中到选中区段
function fitToSegment() {
  // 使用较长的延迟确保地图完全初始化
  setTimeout(() => {
    if (mapRef.value?.fitToBounds && focusBounds.value) {
      // 使用 focusBounds 直接设置视野
      mapRef.value.fitToBounds(focusBounds.value, 15)
    } else if (mapRef.value?.fitBounds) {
      // 回退到 fitBounds
      mapRef.value.fitBounds(15)
    }
  }, 500)
}

// 监听控制点变化，重建曲线
watch(() => props.controlPoints, () => {
  // 曲线会自动重建
}, { deep: true })

// 监听起点终点变化，重新聚焦到区段（仅首次）
watch(() => [props.startPoint, props.endPoint], () => {
  // 只在首次加载时自动聚焦
  if (!hasAutoFocused.value) {
    // 使用较长延迟确保地图完全切换
    setTimeout(() => {
      fitToSegment()
      hasAutoFocused.value = true
    }, 800)
  }
}, { deep: true })

// 组件挂载后居中
onMounted(() => {
  if (!hasAutoFocused.value) {
    fitToSegment()
    hasAutoFocused.value = true
  }
})

// 组件卸载时清理
onUnmounted(() => {
  // 清理任何 pending 的操作
})

// 暴露方法
defineExpose({
  fitToSegment
})
</script>

<style scoped>
.pen-tool-map {
  position: relative;
  width: 100%;
  height: 100%;
}

.pen-toolbar {
  position: absolute;
  top: 60px;
  right: 12px;
  z-index: 1000;
  background: white;
  padding: 8px;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
}

.btn-text {
  margin-left: 4px;
}

.pen-hint {
  position: absolute;
  bottom: 12px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 1000;
  background: rgba(0, 0, 0, 0.7);
  color: white;
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 14px;
  pointer-events: none;
}
</style>
