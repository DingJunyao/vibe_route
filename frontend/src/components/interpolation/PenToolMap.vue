<template>
  <div class="pen-tool-map">
    <UniversalMap
      ref="mapRef"
      :tracks="[]"
      :custom-overlays="mapOverlays"
      mode="detail"
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
import { ref, computed, watch } from 'vue'
import UniversalMap from '@/components/map/UniversalMap.vue'
import { CubicBezierCurve, type BezierControlPoint } from '@/utils/bezierCurve'
import { Lock, Unlock, Delete } from '@element-plus/icons-vue'

interface PointData {
  lng: number
  lat: number
  index: number
  time: string
}

interface ControlPointData {
  lng: number
  lat: number
  inHandle: { dx: number; dy: number }
  outHandle: { dx: number; dy: number }
  handlesLocked: boolean
}

interface Props {
  trackId: number
  startPoint: PointData
  endPoint: PointData
  controlPoints: ControlPointData[]
  modelValue: boolean
}

interface Emits {
  (e: 'update:controlPoints', points: ControlPointData[]): void
  (e: 'update:modelValue', value: boolean): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// 状态
const mapRef = ref()
const selectedPointIndex = ref<number | null>(null)
const handlesLocked = ref(true)

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

  // 起点标记（蓝色圆点）
  overlays.push({
    type: 'marker',
    position: [props.startPoint.lat, props.startPoint.lng],
    icon: {
      type: 'circle',
      radius: 6,
      fillColor: '#409eff',
      fillOpacity: 1,
      strokeColor: '#fff',
      strokeWeight: 2
    },
    label: 'A'
  })

  // 终点标记（绿色圆点）
  overlays.push({
    type: 'marker',
    position: [props.endPoint.lat, props.endPoint.lng],
    icon: {
      type: 'circle',
      radius: 6,
      fillColor: '#67c23a',
      fillOpacity: 1,
      strokeColor: '#fff',
      strokeWeight: 2
    },
    label: 'B'
  })

  // 控制点标记
  props.controlPoints.forEach((cp, index) => {
    const isSelected = index === selectedPointIndex.value
    overlays.push({
      type: 'marker',
      position: [cp.lat, cp.lng],
      icon: {
        type: 'circle',
        radius: isSelected ? 8 : 5,
        fillColor: isSelected ? '#e6a23c' : '#f56c6c',
        fillOpacity: 0.9,
        strokeColor: '#fff',
        strokeWeight: 2
      },
      label: String(index + 1)
    })
  })

  // 曲线路径
  if (previewPoints.value.length > 1) {
    overlays.push({
      type: 'polyline',
      positions: previewPoints.value.map(p => [p.lat, p.lng]),
      color: '#409eff',
      weight: 3,
      opacity: 0.7,
      dashArray: '5, 5'
    })
  }

  return overlays
})

// 添加控制点
function addControlPoint(lng: number, lat: number) {
  const newPoint: ControlPointData = {
    lng,
    lat,
    inHandle: { dx: -0.001, dy: 0 },
    outHandle: { dx: 0.001, dy: 0 },
    handlesLocked: true
  }
  emit('update:controlPoints', [...props.controlPoints, newPoint])
  selectedPointIndex.value = props.controlPoints.length
}

// 更新控制点位置
function updateControlPoint(index: number, lng: number, lat: number) {
  const updated = [...props.controlPoints]
  updated[index] = { ...updated[index], lng, lat }
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

// 监听控制点变化，重建曲线
watch(() => props.controlPoints, () => {
  // 曲线会自动重建
}, { deep: true })
</script>

<style scoped>
.pen-tool-map {
  position: relative;
  width: 100%;
  height: 100%;
}

.pen-toolbar {
  position: absolute;
  top: 12px;
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
