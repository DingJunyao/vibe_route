<template>
  <div class="interpolation-container">
    <!-- Header -->
    <el-header>
      <div class="header-left">
        <el-button @click="handleBack" :icon="ArrowLeft" class="nav-btn" />
        <el-button @click="goHome" :icon="HomeFilled" class="nav-btn home-nav-btn" />
        <h1>{{ trackName || '轨迹 #' + trackId }} - 路径插值</h1>
      </div>
      <div class="header-right">
        <el-button
          type="primary"
          :loading="isApplying"
          :disabled="step !== 'preview' || !selectedSegmentKey"
          @click="handleApply"
        >
          <el-icon><Check /></el-icon>
          应用插值
        </el-button>
      </div>
    </el-header>

    <!-- 主内容区 -->
    <el-main class="interpolation-main">
      <el-empty v-if="isLoading" description="加载中..." />
      <div v-if="!isLoading && points.length === 0" class="empty-state">
        <el-empty description="暂无轨迹数据" />
      </div>
      <div v-if="!isLoading && points.length > 0" class="interpolation-content">
        <!-- 左侧/上方：地图区域 -->
        <div class="map-section" :class="{ 'map-section-full': panelCollapsed }">
          <!-- 选择区段时显示完整轨迹 -->
          <div v-if="step === 'select'" class="map-wrapper" ref="mapWrapperRef">
            <UniversalMap
              ref="mapRef"
              :tracks="[trackWithPoints]"
              :highlight-segments="highlightSegments"
              :available-segments="availableSegmentsForMap"
              mode="detail"
            />

            <!-- 轨迹信息卡片 -->
            <div class="track-info-card">
              <div class="info-row">
                <span class="label">轨迹点数：</span>
                <span class="value">{{ points.length }}</span>
              </div>
              <div v-if="availableSegments.length > 0" class="info-row highlight">
                <span class="label">符合条件的区段：</span>
                <span class="value">{{ availableSegments.length }} 个</span>
              </div>
              <div v-if="selectedSegment" class="info-row highlight">
                <span class="label">已选区段：</span>
                <span class="value">{{ selectedSegmentKey }}</span>
              </div>
            </div>
          </div>

          <!-- 绘制和预览时使用 PenToolMap -->
          <div v-if="step === 'draw' || step === 'preview'" class="map-wrapper map-draw">
            <PenToolMap
              v-if="startPointData && endPointData"
              :track-id="trackId"
              :track-points="points"
              :start-point="{
                lng: startPointData.longitude_wgs84,
                lat: startPointData.latitude_wgs84,
                index: startPointData.point_index,
                time: startPointData.time || '',
                // 多坐标系支持
                latitude_wgs84: startPointData.latitude_wgs84,
                longitude_wgs84: startPointData.longitude_wgs84,
                latitude_gcj02: startPointData.latitude_gcj02,
                longitude_gcj02: startPointData.longitude_gcj02,
                latitude_bd09: startPointData.latitude_bd09,
                longitude_bd09: startPointData.longitude_bd09
              }"
              :end-point="{
                lng: endPointData.longitude_wgs84,
                lat: endPointData.latitude_wgs84,
                index: endPointData.point_index,
                time: endPointData.time || '',
                // 多坐标系支持
                latitude_wgs84: endPointData.latitude_wgs84,
                longitude_wgs84: endPointData.longitude_wgs84,
                latitude_gcj02: endPointData.latitude_gcj02,
                longitude_gcj02: endPointData.longitude_gcj02,
                latitude_bd09: endPointData.latitude_bd09,
                longitude_bd09: endPointData.longitude_bd09
              }"
              :control-points="controlPoints"
              :editable="step === 'draw'"
              @update:control-points="handleControlPointsUpdate"
            />
          </div>
        </div>

        <!-- 右侧/下方：控制面板 -->
        <div class="control-panel" :class="{ 'panel-collapsed': panelCollapsed }">
          <!-- 折叠按钮 -->
          <div class="collapse-btn" @click="togglePanel">
            <el-icon>
              <DArrowLeft v-if="!panelCollapsed" />
              <DArrowRight v-if="panelCollapsed" />
            </el-icon>
          </div>

          <div v-if="!panelCollapsed" class="panel-content">
            <!-- 选择区段步骤 -->
            <div v-if="step === 'select'" class="step-content">
              <h3 class="step-title">
                <el-icon><Link /></el-icon>
                选择区段
              </h3>

              <!-- 最小间隔设置 -->
              <div class="interval-setting">
                <label>最小间隔：{{ minInterval }} 秒</label>
                <el-slider
                  v-model="minInterval"
                  :min="1"
                  :max="60"
                  :step="1"
                  @change="handleIntervalChange"
                  :disabled="isLoadingSegments"
                />
              </div>

              <!-- 区段列表 -->
              <div v-if="isLoadingSegments" class="loading-segments">
                <el-icon class="is-loading"><Loading /></el-icon>
                <span>加载区段中...</span>
              </div>
              <div v-if="!isLoadingSegments && availableSegments.length === 0" class="no-segments">
                <el-empty description="没有符合条件的区段" :image-size="80" />
              </div>
              <div v-if="!isLoadingSegments && availableSegments.length > 0" class="segments-table-container">
                <el-table
                  :data="tableData"
                  stripe
                  :show-header="true"
                  :row-class-name="getRowClassName"
                  max-height="400"
                  size="small"
                  :span-method="mergeRows"
                >
                  <el-table-column width="50" align="center">
                    <template #default="{ row }">
                      <el-radio
                        v-if="row.type === 'start'"
                        v-model="selectedSegmentKey"
                        :label="row.segmentKey"
                        @change="() => handleSegmentSelectByKey(row.segmentKey)"
                      >
                        <template #default>&nbsp;</template>
                      </el-radio>
                    </template>
                  </el-table-column>
                  <el-table-column label="时间" width="90">
                    <template #default="{ row }">
                      <span v-if="row.type === 'interval'" class="interval-text">
                        间隔 {{ row.interval?.toFixed(1) || '-' }}s
                      </span>
                      <span v-else>{{ row.time }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="位置" width="200">
                    <template #default="{ row }">
                      {{ row.type === 'interval' ? '' : row.location }}
                    </template>
                  </el-table-column>
                  <el-table-column label="速度 (km/h)" width="80" align="right">
                    <template #default="{ row }">
                      {{ row.type === 'interval' ? '' : formatSpeedKmh(row.speed) }}
                    </template>
                  </el-table-column>
                  <el-table-column label="方位角 (°)" width="70" align="right">
                    <template #default="{ row }">
                      {{ row.type === 'interval' ? '' : formatBearing(row.bearing) }}
                    </template>
                  </el-table-column>
                </el-table>
              </div>

              <div class="step-actions">
                <el-button
                  type="primary"
                  :disabled="!selectedSegment"
                  @click="enterDrawMode"
                  size="large"
                >
                  下一步：绘制路径
                </el-button>
              </div>
            </div>

            <!-- 绘制路径步骤 -->
            <div v-if="step === 'draw'" class="step-content">
              <div class="step-header">
                <h3 class="step-title">
                  <el-icon><Link /></el-icon>
                  绘制路径
                </h3>
                <el-button text @click="handleReset">
                  <el-icon><RefreshLeft /></el-icon>
                  返回
                </el-button>
              </div>

              <div class="draw-instructions">
                <el-alert type="info" :closable="false">
                  在地图上点击添加控制点，拖拽调整位置。控制点越多，路径越精确。
                </el-alert>
              </div>

              <div class="control-points-list" v-if="controlPoints.length > 0">
                <h4>控制点列表 ({{ controlPoints.length }})</h4>
                <div class="point-list">
                  <div
                    v-for="(cp, index) in controlPoints"
                    :key="index"
                    class="point-item"
                  >
                    <span class="point-index">{{ index + 1 }}</span>
                    <span class="point-coords">{{ cp.lat.toFixed(5) }}, {{ cp.lng.toFixed(5) }}</span>
                    <el-button
                      size="small"
                      type="danger"
                      :icon="Delete"
                      circle
                      @click="handleDeletePoint(index)"
                      class="delete-point-btn"
                    />
                  </div>
                </div>
              </div>
              <div v-if="controlPoints.length === 0" class="no-points-hint">
                <p>暂无控制点，点击地图添加</p>
              </div>

              <div class="step-actions">
                <el-button @click="handleUndo" :disabled="!canUndo">
                  <el-icon><RefreshLeft /></el-icon>
                  撤销
                </el-button>
                <el-button @click="handleRedo" :disabled="!canRedo">
                  <el-icon><RefreshRight /></el-icon>
                  重做
                </el-button>
                <el-button @click="handleClearPath">
                  <el-icon><RefreshLeft /></el-icon>
                  重置
                </el-button>
                <el-button type="primary" @click="handlePreview" size="large">
                  <el-icon><View /></el-icon>
                  预览
                </el-button>
              </div>
            </div>

            <!-- 预览步骤 -->
            <div v-if="step === 'preview'" class="step-content">
              <div class="step-header">
                <h3 class="step-title">
                  <el-icon><View /></el-icon>
                  预览结果
                </h3>
                <el-button text @click="step = 'draw'">
                  <el-icon><RefreshLeft /></el-icon>
                  返回修改
                </el-button>
              </div>

              <div class="preview-info">
                <el-alert type="success" :closable="false">
                  <template #title>
                    <div class="preview-summary">
                      <p>区段 {{ selectedSegmentKey }} 已准备就绪</p>
                      <p v-if="previewData" class="preview-count">
                        将生成 <strong>{{ previewData.total_count }}</strong> 个插值点
                      </p>
                      <p v-if="controlPoints.length > 0" class="control-point-count">
                        使用 {{ controlPoints.length }} 个控制点
                      </p>
                    </div>
                  </template>
                </el-alert>
              </div>

              <div class="preview-details" v-if="startPointData && endPointData">
                <h4>区段详情</h4>
                <div class="detail-row">
                  <span class="detail-label">起点时间：</span>
                  <span class="detail-value">{{ formatTime(startPointData.time) }}</span>
                </div>
                <div class="detail-row">
                  <span class="detail-label">终点时间：</span>
                  <span class="detail-value">{{ formatTime(endPointData.time) }}</span>
                </div>
                <div class="detail-row">
                  <span class="detail-label">起点坐标：</span>
                  <span class="detail-value coords">{{ startPointData.latitude_wgs84.toFixed(6) }}, {{ startPointData.longitude_wgs84.toFixed(6) }}</span>
                </div>
                <div class="detail-row">
                  <span class="detail-label">终点坐标：</span>
                  <span class="detail-value coords">{{ endPointData.latitude_wgs84.toFixed(6) }}, {{ endPointData.longitude_wgs84.toFixed(6) }}</span>
                </div>
              </div>

              <div class="step-actions">
                <el-button @click="handleReset">
                  <el-icon><RefreshLeft /></el-icon>
                  重置
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ArrowLeft, HomeFilled, Check, Link, Loading,
  InfoFilled, View, Delete, RefreshLeft, RefreshRight, DArrowLeft, DArrowRight
} from '@element-plus/icons-vue'
import UniversalMap from '@/components/map/UniversalMap.vue'
import PenToolMap from '@/components/interpolation/PenToolMap.vue'
import { interpolationApi, type ControlPoint, type AvailableSegment } from '@/api/interpolation'
import { trackApi } from '@/api/track'

const route = useRoute()
const router = useRouter()

const trackId = ref<number>(parseInt(route.params.id as string))
const isLoading = ref(true)
const isApplying = ref(false)
const isLoadingSegments = ref(false)

// 轨迹数据
const trackName = ref('')
const points = ref<Array<{
  point_index: number
  time: string | null
  latitude: number
  longitude: number
  latitude_wgs84: number
  longitude_wgs84: number
  latitude_gcj02: number
  longitude_gcj02: number
  latitude_bd09: number
  longitude_bd09: number
  elevation: number | null
  speed: number | null
  bearing: number | null
  province: string | null
  city: string | null
  district: string | null
}>>([])

// 面板状态
const panelCollapsed = ref(false)

// 地图引用
const mapRef = ref()
const mapWrapperRef = ref<HTMLElement | null>(null)

// 插值步骤
const step = ref<'select' | 'draw' | 'preview'>('select')
const minInterval = ref(3)
const selectedSegmentKey = ref<string>('')
const hoveredSegmentKey = ref<string | null>(null)
const controlPoints = ref<ControlPoint[]>([])
const isPreviewing = ref(false)
const previewData = ref<{ total_count: number } | null>(null)

// 撤销/重做历史
const history: ControlPoint[][] = []
const historyIndex = ref(0)
const isUndoRedoOperation = ref(false)  // 标记是否正在进行撤销/重做操作

const canUndo = computed(() => historyIndex.value > 0)
const canRedo = computed(() => historyIndex.value < history.length - 1)

// 可用区段（扩展信息）
interface ExtendedSegment extends AvailableSegment {
  key: string
  startLabel: string
  endLabel: string
  startLocation: string
  endLocation: string
  startSpeed: number | null
  endSpeed: number | null
  startBearing: number | null
  endBearing: number | null
  startPoint: any
  endPoint: any
}

const availableSegments = ref<ExtendedSegment[]>([])

// 表格数据：每段展开为三行（起点行、终点行、间隔行）
interface TableRow {
  key: string
  segmentKey: string  // 所属区段的 key
  type: 'start' | 'end' | 'interval'
  time: string
  location: string
  speed: number | null
  bearing: number | null
  interval?: number  // 间隔行包含此字段
}

const tableData = computed<TableRow[]>(() => {
  const rows: TableRow[] = []
  for (const seg of availableSegments.value) {
    // 起点行
    rows.push({
      key: `${seg.key}-start`,
      segmentKey: seg.key,
      type: 'start',
      time: seg.startLabel || '-',
      location: formatLocation(seg.startLocation),
      speed: seg.startSpeed,
      bearing: seg.startBearing
    })
    // 终点行
    rows.push({
      key: `${seg.key}-end`,
      segmentKey: seg.key,
      type: 'end',
      time: seg.endLabel || '-',
      location: formatLocation(seg.endLocation),
      speed: seg.endSpeed,
      bearing: seg.endBearing
    })
    // 间隔行
    rows.push({
      key: `${seg.key}-interval`,
      segmentKey: seg.key,
      type: 'interval',
      time: '',
      location: '',
      speed: null,
      bearing: null,
      interval: seg.interval_seconds
    })
  }
  return rows
})

// 转换后的轨迹数据（用于地图显示）
const trackWithPoints = computed(() => ({
  id: trackId.value,
  points: points.value.map(p => ({
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
}))

// 传给地图的高亮区段
const highlightSegments = computed(() => {
  const segments: Array<{ start: number; end: number; color: string }> = []

  // 添加所有符合条件的区段（绿色）
  for (const seg of availableSegments.value) {
    segments.push({
      start: seg.start_index,
      end: seg.end_index,
      color: '#67c23a'  // 绿色（备选区段）
    })
  }

  // 悬停的区段（蓝色，优先级更高）
  if (hoveredSegmentKey.value) {
    const seg = availableSegments.value.find(s => s.key === hoveredSegmentKey.value)
    if (seg) {
      segments.push({
        start: seg.start_index,
        end: seg.end_index,
        color: '#409eff'  // 蓝色（悬停时）
      })
    }
  }

  // 选中的区段（蓝色，最优先）
  if (selectedSegmentKey.value) {
    const seg = availableSegments.value.find(s => s.key === selectedSegmentKey.value)
    if (seg) {
      segments.push({
        start: seg.start_index,
        end: seg.end_index,
        color: '#409eff'  // 蓝色（选中时）
      })
    }
  }

  return segments.length > 0 ? segments : null
})

// 传给地图的可用区段（用于地图上的区段交互）
const availableSegmentsForMap = computed(() => {
  return availableSegments.value.map(seg => ({
    start: seg.start_index,
    end: seg.end_index,
    key: seg.key
  }))
})

// 选中的区段
const selectedSegment = computed(() => {
  if (!selectedSegmentKey.value) return null
  return availableSegments.value.find(s => s.key === selectedSegmentKey.value)
})

// 起点和终点数据
const startPointData = computed(() => {
  if (!selectedSegment.value) return null
  return points.value.find(p => p.point_index === selectedSegment.value!.start_index)
})

const endPointData = computed(() => {
  if (!selectedSegment.value) return null
  return points.value.find(p => p.point_index === selectedSegment.value!.end_index)
})

// 起点/终点索引（用于兼容原有逻辑）
const startPointIndex = computed(() => selectedSegment.value?.start_index ?? null)
const endPointIndex = computed(() => selectedSegment.value?.end_index ?? null)

// 格式化时间
function formatTime(time: string | null): string {
  if (!time) return '-'
  return new Date(time).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

// 格式化位置信息
function formatLocation(point: any): string {
  if (!point) return '-'
  const parts = []
  if (point.province) parts.push(point.province)
  if (point.city && point.city !== point.province) parts.push(point.city)
  if (point.district) parts.push(point.district)
  return parts.length > 0 ? parts.join(' ') : '-'
}

// 格式化速度（后端返回的是 m/s，转换为 km/h）
function formatSpeedKmh(speed: number | null): string {
  if (speed === null || speed === undefined) return '-'
  const kmh = speed * 3.6
  return `${kmh.toFixed(1)}`
}

// 格式化方位角（单位在表头显示）
function formatBearing(bearing: number | null): string {
  if (bearing === null || bearing === undefined) return '-'
  return `${bearing.toFixed(0)}`
}

// 获取行类名
function getRowClassName({ row }: { row: TableRow }): string {
  if (row.segmentKey === selectedSegmentKey.value) return 'selected-row'
  if (row.type === 'interval') return 'interval-row'
  return ''
}

// 合并行（选择框列跨越三行）
function mergeRows({ row, column, columnIndex }: { row: TableRow; column: any; columnIndex: number }): number | { rowspan: number; colspan: number } {
  // 第一列（选择框列， columnIndex = 0）
  if (columnIndex === 0) {
    if (row.type === 'start') {
      return { rowspan: 3, colspan: 1 }
    } else {
      return { rowspan: 0, colspan: 0 }
    }
  }
  return 1
}

// 通过 key 选择区段
function handleSegmentSelectByKey(key: string) {
  selectedSegmentKey.value = key
}

// 加载轨迹数据
async function loadTrackData() {
  isLoading.value = true
  try {
    // 并行获取轨迹点和轨迹详情
    const [pointsResponse, detailResponse] = await Promise.all([
      trackApi.getPoints(trackId.value),
      trackApi.getDetail(trackId.value)
    ])
    points.value = pointsResponse.points
    trackName.value = detailResponse.name
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '加载轨迹数据失败')
  } finally {
    isLoading.value = false
  }
}

// 加载可用区段
async function loadAvailableSegments() {
  isLoadingSegments.value = true
  try {
    const segments = await interpolationApi.getAvailableSegments(
      trackId.value,
      minInterval.value
    )

    // 扩展区段信息
    availableSegments.value = segments.map(seg => {
      const startPoint = points.value.find(p => p.point_index === seg.start_index)
      const endPoint = points.value.find(p => p.point_index === seg.end_index)
      const key = `${seg.start_index}-${seg.end_index}`

      return {
        ...seg,
        key,
        startLabel: formatTime(seg.start_time),
        endLabel: formatTime(seg.end_time),
        startLocation: startPoint || null,
        endLocation: endPoint || null,
        startSpeed: startPoint?.speed ?? null,
        endSpeed: endPoint?.speed ?? null,
        startBearing: startPoint?.bearing ?? null,
        endBearing: endPoint?.bearing ?? null,
        startPoint,
        endPoint
      }
    })
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '加载区段失败')
    availableSegments.value = []
  } finally {
    isLoadingSegments.value = false
  }
}

// 最小间隔变化
function handleIntervalChange() {
  selectedSegmentKey.value = ''
  loadAvailableSegments()
}

// 区段选择
function handleSegmentSelect(row: ExtendedSegment | null) {
  if (!row) {
    selectedSegmentKey.value = ''
    return
  }
  selectedSegmentKey.value = row.key
}

// 区段悬停
function handleSegmentHover(row: ExtendedSegment) {
  hoveredSegmentKey.value = row.key
}

// 区段离开
function handleSegmentLeave() {
  hoveredSegmentKey.value = null
}

// 进入绘制模式
function enterDrawMode() {
  if (!selectedSegment.value) {
    ElMessage.warning('请先选择有效的区段')
    return
  }
  // 初始化历史记录
  history.length = 0
  history.push([])
  historyIndex.value = 0
  console.log('[Interpolation] enterDrawMode - 初始化历史记录, historyIndex.value:', historyIndex.value)
  step.value = 'draw'
}

// 处理控制点更新
function handleControlPointsUpdate(points: ControlPoint[]) {
  console.log('[Interpolation] handleControlPointsUpdate - points.length:', points.length, 'current controlPoints.value.length:', controlPoints.value.length)
  console.log('[Interpolation] handleControlPointsUpdate - isUndoRedoOperation:', isUndoRedoOperation.value)

  // 如果正在进行撤销/重做操作，不保存历史记录
  if (isUndoRedoOperation.value) {
    controlPoints.value = points
    return
  }

  // 检查是否真的发生了变化
  const currentJson = JSON.stringify(controlPoints.value)
  const newJson = JSON.stringify(points)
  console.log('[Interpolation] handleControlPointsUpdate - currentJson === newJson:', currentJson === newJson)
  if (currentJson === newJson) return

  // 保存到历史记录
  saveToHistory(points)
  controlPoints.value = points
}

// 保存到历史记录
function saveToHistory(points: ControlPoint[]) {
  // 如果当前不在历史记录末尾，删除后面的记录
  if (historyIndex.value < history.length - 1) {
    history.splice(historyIndex.value + 1)
  }
  // 添加新状态
  history.push([...points])
  historyIndex.value = history.length - 1
  // 限制历史记录数量
  if (history.length > 50) {
    history.shift()
    historyIndex.value--
  }
  console.log('[Interpolation] saveToHistory - historyIndex.value:', historyIndex.value, 'history.length:', history.length, 'points:', points.length)
}

// 撤销
function handleUndo() {
  console.log('[Interpolation] handleUndo - historyIndex.value:', historyIndex.value, 'canUndo:', canUndo.value)
  if (historyIndex.value > 0) {
    isUndoRedoOperation.value = true
    historyIndex.value--
    controlPoints.value = [...history[historyIndex.value]]
    console.log('[Interpolation] handleUndo - 撤销后 historyIndex.value:', historyIndex.value, 'points:', controlPoints.value.length)
    // 下一帧重置标志
    nextTick(() => {
      isUndoRedoOperation.value = false
    })
  }
}

// 重做
function handleRedo() {
  console.log('[Interpolation] handleRedo - historyIndex.value:', historyIndex.value, 'canRedo:', canRedo.value)
  if (historyIndex.value < history.length - 1) {
    isUndoRedoOperation.value = true
    historyIndex.value++
    controlPoints.value = [...history[historyIndex.value]]
    console.log('[Interpolation] handleRedo - 重做后 historyIndex.value:', historyIndex.value, 'points:', controlPoints.value.length)
    // 下一帧重置标志
    nextTick(() => {
      isUndoRedoOperation.value = false
    })
  }
}

// 删除指定控制点
function handleDeletePoint(index: number) {
  const updated = controlPoints.value.filter((_, i) => i !== index)
  saveToHistory(updated)
  controlPoints.value = updated
}

// 预览插值
async function handlePreview() {
  if (!startPointData.value || !endPointData.value) return

  isPreviewing.value = true
  try {
    // 过滤控制点数据，只保留后端需要的字段
    const filteredControlPoints = controlPoints.value.map(cp => ({
      lng: cp.lng,
      lat: cp.lat,
      in_handle: cp.inHandle,
      out_handle: cp.outHandle,
      handles_locked: cp.handlesLocked
    }))

    const result = await interpolationApi.preview({
      track_id: trackId.value,
      start_point_index: startPointIndex.value!,
      end_point_index: endPointIndex.value!,
      control_points: filteredControlPoints,
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
    // 过滤控制点数据，只保留后端需要的字段
    const filteredControlPoints = controlPoints.value.map(cp => ({
      lng: cp.lng,
      lat: cp.lat,
      in_handle: cp.inHandle,
      out_handle: cp.outHandle,
      handles_locked: cp.handlesLocked
    }))

    await interpolationApi.create(trackId.value, {
      start_point_index: startPointIndex.value!,
      end_point_index: endPointIndex.value!,
      control_points: filteredControlPoints,
      interpolation_interval_seconds: 1,
      algorithm: 'cubic_bezier'
    })
    ElMessage.success('插值已应用')
    // 返回轨迹详情页
    router.push(`/tracks/${trackId.value}`)
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '应用失败')
  } finally {
    isApplying.value = false
  }
}

// 重置（清空控制点和历史记录）
function handleClearPath() {
  controlPoints.value = []
  // 清空历史记录
  history.length = 0
  history.push([])
  historyIndex.value = 0
  console.log('[Interpolation] handleClearPath - 历史记录已清空')
}

// 重置选择（返回选择区段阶段）
function handleReset() {
  step.value = 'select'
  selectedSegmentKey.value = ''
  controlPoints.value = []
  previewData.value = null
  // 清空历史记录
  history.length = 0
  history.push([])
  historyIndex.value = 0
}

// 切换面板折叠
function togglePanel() {
  panelCollapsed.value = !panelCollapsed.value
  nextTick(() => {
    if (mapRef.value?.resize) {
      mapRef.value.resize()
    }
  })
}

// 导航
function handleBack() {
  router.push(`/tracks/${trackId.value}`)
}

function goHome() {
  router.push('/home')
}

// 初始化
loadTrackData()
loadAvailableSegments()

// 键盘快捷键
function handleKeydown(e: KeyboardEvent) {
  // Ctrl+Z 撤销
  if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
    e.preventDefault()
    if (canUndo.value) {
      handleUndo()
    }
    return
  }
  // Ctrl+Y 或 Ctrl+Shift+Z 重做
  if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) {
    e.preventDefault()
    if (canRedo.value) {
      handleRedo()
    }
    return
  }
}

onMounted(async () => {
  window.addEventListener('keydown', handleKeydown)
  // 加载轨迹数据
  await loadTrackData()
  // 加载可用区段
  loadAvailableSegments()
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
.interpolation-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.el-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-left h1 {
  margin: 0;
  font-size: 18px;
  font-weight: 500;
}

.nav-btn {
  padding: 8px;
}

.home-nav-btn {
  margin-left: 0;
  margin-right: 12px;
}

.interpolation-main {
  flex: 1;
  overflow: hidden;
  padding: 0;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.interpolation-content {
  display: flex;
  height: 100%;
}

/* 地图区域 */
.map-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
  transition: all 0.3s ease;
  min-width: 0;
}

.map-section-full {
  flex: 1;
}

.map-wrapper {
  flex: 1;
  position: relative;
  background: #f5f5f5;
  min-height: 0;
}

.map-draw {
  height: 100%;
}

.track-info-card {
  position: absolute;
  top: 12px;
  left: 12px;
  background: rgba(255, 255, 255, 0.95);
  padding: 12px 16px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  z-index: 1000;
  min-width: 200px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 8px;
  font-size: 14px;
}

.info-row:last-child {
  margin-bottom: 0;
}

.info-row .label {
  color: #606266;
}

.info-row .value {
  font-weight: 500;
  color: #303133;
}

.info-row.highlight {
  padding-top: 8px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.info-row.highlight .value {
  color: #409eff;
}

/* 控制面板 */
.control-panel {
  width: 550px;
  background: white;
  border-left: 1px solid var(--el-border-color-lighter);
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
  position: relative;
  z-index: 100;
  flex-shrink: 0;
}

.panel-collapsed {
  width: 48px;
}

.collapse-btn {
  position: absolute;
  top: 50%;
  left: 0;
  transform: translateY(-50%);
  width: 24px;
  height: 48px;
  background: white;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 0 8px 8px 0;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 10;
  transition: all 0.3s ease;
}

.collapse-btn:hover {
  background: #f5f5f5;
}

.panel-collapsed .collapse-btn {
  left: auto;
  right: 0;
  border-radius: 8px 0 0 8px;
}

.panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.panel-collapsed .panel-content {
  display: none;
}

.step-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.step-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 16px;
  font-weight: 500;
}

.step-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* 最小间隔设置 */
.interval-setting {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.interval-setting label {
  font-weight: 500;
  font-size: 14px;
  color: #606266;
}

/* 加载区段 */
.loading-segments {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px 20px;
  color: #909399;
}

.loading-segments .el-icon {
  font-size: 20px;
}

/* 无区段 */
.no-segments {
  padding: 20px;
}

/* 区段表格 */
.segments-table-container {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  overflow: hidden;
}

.segments-table-container :deep(.el-table) {
  font-size: 13px;
}

.segments-table-container :deep(.el-table__row) {
  cursor: pointer;
}

.segments-table-container :deep(.selected-row) {
  background-color: #ecf5ff !important;
}

.segments-table-container :deep(.el-table__row:hover) {
  background-color: #f5f7fa !important;
}

.segments-table-container :deep(.selected-row:hover) {
  background-color: #d9ecff !important;
}

/* 间隔行样式 */
.segments-table-container :deep(.interval-row) {
  background-color: #fafafa !important;
}

.segments-table-container :deep(.interval-row td) {
  border-top: 1px dashed var(--el-border-color-light) !important;
  border-bottom: 2px solid var(--el-border-color) !important;
}

/* 间隔文本样式 */
.interval-text {
  font-weight: 500;
  color: var(--el-text-color-regular);
}

/* 绘制路径 */
.draw-instructions {
  margin-top: 8px;
}

.control-points-list {
  margin-top: 16px;
}

.control-points-list h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 500;
}

.point-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 200px;
  overflow-y: auto;
}

.point-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background: #f5f5f5;
  border-radius: 6px;
}

.point-index {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #e6a23c;
  color: white;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 500;
  flex-shrink: 0;
}

.point-coords {
  flex: 1;
  font-size: 12px;
  font-family: monospace;
  color: #666;
}

.delete-point-btn {
  flex-shrink: 0;
}

.no-points-hint {
  margin-top: 16px;
  text-align: center;
  color: #909399;
  padding: 20px;
  background: #f5f5f5;
  border-radius: 8px;
}

.no-points-hint p {
  margin: 0;
}

/* 预览 */
.preview-info {
  margin-top: 8px;
}

.preview-summary {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.preview-summary p {
  margin: 0;
}

.preview-count {
  font-size: 16px;
}

.preview-count strong {
  color: #67c23a;
  font-size: 20px;
}

.control-point-count {
  color: #909399;
  font-size: 14px;
}

.preview-details {
  margin-top: 20px;
  padding: 16px;
  background: #f5f5f5;
  border-radius: 8px;
}

.preview-details h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 500;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 14px;
}

.detail-row:last-child {
  margin-bottom: 0;
}

.detail-label {
  color: #606266;
}

.detail-value {
  font-weight: 500;
  color: #303133;
}

.detail-value.coords {
  font-family: monospace;
  font-size: 12px;
}

.step-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 16px;
  flex-wrap: wrap;
}

/* 移动端响应式 */
@media (max-width: 1366px) {
  .interpolation-content {
    flex-direction: column;
  }

  .map-section {
    height: 50vh;
  }

  .control-panel {
    width: 100%;
    height: 50vh;
    border-left: none;
    border-top: 1px solid var(--el-border-color-lighter);
  }

  .panel-collapsed {
    width: 100%;
    height: 48px;
  }

  .collapse-btn {
    top: 0;
    left: 50%;
    transform: translateX(-50%);
    width: 48px;
    height: 24px;
    border-radius: 0 0 8px 8px;
  }

  .panel-collapsed .collapse-btn {
    top: auto;
    bottom: 0;
    border-radius: 8px 8px 0 0;
  }

  .track-info-card {
    top: 8px;
    left: 8px;
    right: 8px;
    min-width: auto;
  }

  .control-panel {
    width: 100%;
  }
}
</style>
