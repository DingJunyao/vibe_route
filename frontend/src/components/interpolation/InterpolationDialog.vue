<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="emit('update:visible', $event)"
    title="路径插值"
    width="800px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <!-- 选择区段步骤 -->
    <div v-if="step === 'select'" class="interpolation-step">
      <h3 class="step-title">
        <el-icon><Link /></el-icon>
        选择区段
      </h3>

      <div class="segment-selector">
        <div class="selector-row">
          <label>起点：</label>
          <el-select
            v-model="startPointIndex"
            placeholder="选择起点"
            @change="handleStartPointChange"
            style="width: 280px"
          >
            <el-option
              v-for="seg in availableSegments"
              :key="seg.start_index"
              :label="`点 #${seg.start_index} - ${formatTime(seg.start_time)}`"
              :value="seg.start_index"
            />
          </el-select>
        </div>

        <div class="selector-row">
          <label>终点：</label>
          <el-select
            v-model="endPointIndex"
            placeholder="选择终点"
            @change="handleEndPointChange"
            :disabled="!startPointIndex"
            style="width: 280px"
          >
            <el-option
              v-for="seg in filteredEndSegments"
              :key="seg.end_index"
              :label="`点 #${seg.end_index} - ${formatTime(seg.end_time)}`"
              :value="seg.end_index"
            />
          </el-select>
        </div>

        <div class="selector-row">
          <label>最小间隔：</label>
          <el-slider
            v-model="minInterval"
            :min="1"
            :max="60"
            :step="1"
            style="width: 200px"
          />
          <span class="interval-value">{{ minInterval }} 秒</span>
        </div>
      </div>

      <!-- 区段信息 -->
      <div v-if="selectedSegment" class="segment-info">
        <el-alert type="info" :closable="false">
          <template #title>
            <div class="info-content">
              <span>
                <el-icon><Timer /></el-icon>
                间隔：{{ selectedSegment.interval_seconds.toFixed(1) }} 秒
              </span>
              <span>
                <el-icon><InfoFilled /></el-icon>
                预计插入：约 {{ estimatedPointCount }} 个点
              </span>
            </div>
          </template>
        </el-alert>
      </div>

      <div class="step-actions">
        <el-button @click="handleClose">
          <el-icon><Close /></el-icon>
          取消
        </el-button>
        <el-button
          type="primary"
          :disabled="!selectedSegment"
          @click="enterDrawMode"
        >
          下一步：绘制路径
        </el-button>
      </div>
    </div>

    <!-- 绘制路径步骤 -->
    <div v-else-if="step === 'draw'" class="interpolation-step">
      <div class="step-header">
        <h3 class="step-title">
          <el-icon><Link /></el-icon>
          绘制路径
        </h3>
        <el-button size="small" text @click="step = 'select'">
          <el-icon><RefreshLeft /></el-icon>
          返回
        </el-button>
      </div>

      <div class="map-container">
        <PenToolMap
          v-if="startPointData && endPointData"
          :track-id="trackId"
          :start-point="{
            lng: startPointData.longitude,
            lat: startPointData.latitude,
            index: startPointData.point_index,
            time: startPointData.time || ''
          }"
          :end-point="{
            lng: endPointData.longitude,
            lat: endPointData.latitude,
            index: endPointData.point_index,
            time: endPointData.time || ''
          }"
          :control-points="controlPoints"
          v-model:control-points="controlPoints"
          :model-value="true"
        />
      </div>

      <div class="step-actions">
        <el-button @click="handleClearPath">
          <el-icon><Delete /></el-icon>
          清除路径
        </el-button>
        <el-button @click="handleReset">
          <el-icon><RefreshLeft /></el-icon>
          重置
        </el-button>
        <el-button type="primary" @click="handlePreview">
          <el-icon><View /></el-icon>
          预览
        </el-button>
      </div>
    </div>

    <!-- 预览步骤 -->
    <div v-else-if="step === 'preview'" class="interpolation-step">
      <div class="step-header">
        <h3 class="step-title">
          <el-icon><View /></el-icon>
          预览结果
        </h3>
        <el-button size="small" text @click="step = 'draw'">
          <el-icon><RefreshLeft /></el-icon>
          返回修改
        </el-button>
      </div>

      <div class="preview-info">
        <el-alert type="success" :closable="false">
          <template #title>
            区段 #{{ startPointIndex }} → #{{ endPointIndex }} 已准备就绪
            <template v-if="previewData">
              ，将生成 {{ previewData.total_count }} 个插值点
            </template>
          </template>
        </el-alert>
      </div>

      <div class="step-actions">
        <el-button @click="handleReset">
          <el-icon><RefreshLeft /></el-icon>
          重置
        </el-button>
        <el-button
          type="primary"
          :loading="isApplying"
          @click="handleApply"
        >
          <el-icon><Check /></el-icon>
          应用
        </el-button>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Close, Check, RefreshLeft, Link, Timer,
  InfoFilled, View, Delete
} from '@element-plus/icons-vue'
import PenToolMap from './PenToolMap.vue'
import { interpolationApi, type ControlPoint, type AvailableSegment } from '@/api/interpolation'

interface Props {
  visible: boolean
  trackId: number
  points: Array<{
    point_index: number
    time: string | null
    latitude: number
    longitude: number
    speed: number | null
    bearing: number | null
  }>
}

interface Emits {
  (e: 'update:visible', value: boolean): void
  (e: 'applied'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// 状态
const step = ref<'select' | 'draw' | 'preview'>('select')
const minInterval = ref(3)
const startPointIndex = ref<number | null>(null)
const endPointIndex = ref<number | null>(null)
const controlPoints = ref<ControlPoint[]>([])
const isPreviewing = ref(false)
const isApplying = ref(false)
const previewData = ref<{ total_count: number } | null>(null)

// 可用区段
const availableSegments = ref<AvailableSegment[]>([])

// 过滤后的终点区段（起点之后的区段）
const filteredEndSegments = computed(() => {
  if (startPointIndex.value === null) return []
  return availableSegments.value.filter(s =>
    s.start_index >= startPointIndex.value!
  )
})

// 选中的区段信息
const selectedSegment = computed(() => {
  if (startPointIndex.value === null || endPointIndex.value === null) return null
  return availableSegments.value.find(s =>
    s.start_index === startPointIndex.value &&
    s.end_index === endPointIndex.value
  )
})

// 起点和终点数据
const startPointData = computed(() => {
  if (startPointIndex.value === null) return null
  return props.points.find(p => p.point_index === startPointIndex.value)
})

const endPointData = computed(() => {
  if (endPointIndex.value === null) return null
  return props.points.find(p => p.point_index === endPointIndex.value)
})

// 预计插入的点数
const estimatedPointCount = computed(() => {
  if (!selectedSegment.value) return 0
  return Math.floor(selectedSegment.value.interval_seconds)
})

// 格式化时间
function formatTime(time: string | null): string {
  if (!time) return '-'
  return new Date(time).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

// 加载可用区段
async function loadAvailableSegments() {
  try {
    availableSegments.value = await interpolationApi.getAvailableSegments(
      props.trackId,
      minInterval.value
    )
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '加载区段失败')
  }
}

// 选择起点
function handleStartPointChange(index: number) {
  startPointIndex.value = index
  if (endPointIndex.value !== null && endPointIndex.value <= index) {
    endPointIndex.value = null
  }
}

// 选择终点
function handleEndPointChange(index: number) {
  if (startPointIndex.value === null) {
    ElMessage.warning('请先选择起点')
    return
  }
  if (index <= startPointIndex.value) {
    ElMessage.warning('终点必须在起点之后')
    return
  }
  endPointIndex.value = index
}

// 进入绘制模式
function enterDrawMode() {
  if (!selectedSegment.value) {
    ElMessage.warning('请先选择有效的区段')
    return
  }
  step.value = 'draw'
}

// 预览插值
async function handlePreview() {
  if (!startPointData.value || !endPointData.value) return

  isPreviewing.value = true
  try {
    const result = await interpolationApi.preview({
      track_id: props.trackId,
      start_point_index: startPointIndex.value!,
      end_point_index: endPointIndex.value!,
      control_points: controlPoints.value,
      interpolation_interval_seconds: 1
    })
    previewData.value = result
    step.value = 'preview'
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '预览失败')
  } finally {
    isPreviewing.value = false
  }
}

// 应用插值
async function handleApply() {
  if (!startPointData.value || !endPointData.value) return

  isApplying.value = true
  try {
    await interpolationApi.create(props.trackId, {
      start_point_index: startPointIndex.value!,
      end_point_index: endPointIndex.value!,
      control_points: controlPoints.value,
      interpolation_interval_seconds: 1,
      algorithm: 'cubic_bezier'
    })
    ElMessage.success('插值已应用')
    emit('applied')
    handleClose()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '应用失败')
  } finally {
    isApplying.value = false
  }
}

// 清除路径
function handleClearPath() {
  controlPoints.value = []
  step.value = 'draw'
}

// 重置
function handleReset() {
  step.value = 'select'
  startPointIndex.value = null
  endPointIndex.value = null
  controlPoints.value = []
  previewData.value = null
}

// 关闭对话框
function handleClose() {
  handleReset()
  emit('update:visible', false)
}

// 监听对话框打开
watch(() => props.visible, (visible) => {
  if (visible) {
    handleReset()
    loadAvailableSegments()
  }
})

// 监听最小间隔变化
watch(minInterval, () => {
  loadAvailableSegments()
  startPointIndex.value = null
  endPointIndex.value = null
})
</script>

<style scoped>
.interpolation-step {
  padding: 0;
}

.step-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 20px 0;
  font-size: 16px;
  font-weight: 500;
}

.step-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.segment-selector {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 20px;
}

.selector-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.selector-row label {
  width: 80px;
  font-weight: 500;
}

.interval-value {
  margin-left: 12px;
  font-weight: 500;
  min-width: 60px;
}

.segment-info {
  margin-bottom: 20px;
}

.info-content {
  display: flex;
  gap: 24px;
}

.info-content span {
  display: flex;
  align-items: center;
  gap: 4px;
}

.map-container {
  height: 400px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 20px;
}

.preview-info {
  margin-bottom: 20px;
}

.step-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
