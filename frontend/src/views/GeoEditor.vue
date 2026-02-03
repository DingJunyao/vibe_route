<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, HomeFilled, RefreshLeft, RefreshRight, Check, WarningFilled, ZoomIn, ZoomOut, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useGeoEditorStore, type TrackType } from '@/stores/geoEditor'
import UniversalMap from '@/components/map/UniversalMap.vue'
import GeoChartPanel from '@/components/geo-editor/GeoChartPanel.vue'
import TimelineScale from '@/components/geo-editor/TimelineScale.vue'
import TimelineTracks from '@/components/geo-editor/TimelineTracks.vue'

const route = useRoute()
const router = useRouter()
const geoEditorStore = useGeoEditorStore()

const trackId = ref<number>(parseInt(route.params.id as string))
const isLoading = ref(true)
const isSaving = ref(false)
const trackName = ref('')

// 地图引用
const mapRef = ref<InstanceType<typeof UniversalMap> | null>(null)

// 高亮区域（基于选中的段落）
const highlightedSegment = computed(() => {
  const id = geoEditorStore.selectedSegmentId || geoEditorStore.hoveredSegmentId
  if (!id) return null

  for (const track of geoEditorStore.tracks) {
    const segment = track.segments.find(s => s.id === id)
    if (segment) {
      return {
        start: segment.startIndex,
        end: segment.endIndex,
      }
    }
  }
  return null
})

// 转换点数据为 UniversalMap 格式（tracks 数组）
const mapTracks = computed(() => {
  return [
    {
      id: trackId.value,
      points: geoEditorStore.points.map(p => ({
        latitude: p.latitude,
        longitude: p.longitude,
        latitude_wgs84: p.latitude,
        longitude_wgs84: p.longitude,
        latitude_gcj02: null,
        longitude_gcj02: null,
        latitude_bd09: null,
        longitude_bd09: null,
        elevation: p.elevation,
        time: p.time,
        speed: p.speed,
      })),
    },
  ]
})

// 轨道数据（用于时间轴显示）
const tracksData = computed(() => geoEditorStore.tracks)

// 计算指针对应的点索引（用于地图 tooltip 同步）
const highlightPointIndex = computed(() => {
  if (geoEditorStore.points.length === 0) return undefined
  const position = geoEditorStore.pointerPosition
  return Math.floor(position * geoEditorStore.points.length)
})

// 计算指针在可见区域的位置
const isPointerVisible = computed(() => {
  return geoEditorStore.pointerPosition >= geoEditorStore.zoomStart &&
         geoEditorStore.pointerPosition <= geoEditorStore.zoomEnd
})

const playheadXPosition = computed(() => {
  if (!isPointerVisible.value) return '65px'
  const percent = (geoEditorStore.pointerPosition - geoEditorStore.zoomStart) /
                  (geoEditorStore.zoomEnd - geoEditorStore.zoomStart)
  // 0% 时在 65px（内容起始位置），100% 时在 100%
  return `calc(65px + (100% - 65px) * ${percent})`
})

// 指针时间文本
const pointerTimeText = computed(() => {
  if (geoEditorStore.points.length === 0) return '--:--:--'
  const startTime = geoEditorStore.points[0]?.time ? new Date(geoEditorStore.points[0].time).getTime() : 0
  const endTime = geoEditorStore.points[geoEditorStore.points.length - 1]?.time
    ? new Date(geoEditorStore.points[geoEditorStore.points.length - 1].time).getTime()
    : startTime + 3600000
  const totalDuration = endTime - startTime || 3600000

  const pointerTimeMs = startTime + totalDuration * geoEditorStore.pointerPosition
  const date = new Date(pointerTimeMs)
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')
  return `${hours}:${minutes}:${seconds}`
})

// 拖动指针
const isDraggingPlayhead = ref(false)

function handlePlayheadMouseDown(e: MouseEvent) {
  e.preventDefault()
  isDraggingPlayhead.value = true
  geoEditorStore.startPointerDrag()

  const handleMouseMove = (e: MouseEvent) => {
    if (!isDraggingPlayhead.value) return
    const container = (e.currentTarget as HTMLElement).parentElement
    if (!container) return
    const rect = container.getBoundingClientRect()

    // 计算相对于内容区域的 x 坐标（从 65px 开始）
    const CONTENT_START = 65
    const x = Math.max(0, Math.min(rect.width - CONTENT_START, e.clientX - rect.left - CONTENT_START))
    const contentWidth = rect.width - CONTENT_START
    const position = geoEditorStore.zoomStart + (x / contentWidth) * (geoEditorStore.zoomEnd - geoEditorStore.zoomStart)
    geoEditorStore.setPointerPosition(position)
  }

  const handleMouseUp = () => {
    isDraggingPlayhead.value = false
    geoEditorStore.stopPointerDrag()
    window.removeEventListener('mousemove', handleMouseMove)
    window.removeEventListener('mouseup', handleMouseUp)
  }

  window.addEventListener('mousemove', handleMouseMove)
  window.addEventListener('mouseup', handleMouseUp)
}

// 加载数据
onMounted(async () => {
  try {
    await geoEditorStore.loadEditorData(trackId.value)
    trackName.value = `轨迹 #${trackId.value}`
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '加载编辑器数据失败')
    router.back()
  } finally {
    isLoading.value = false
  }

  // 添加离页提示
  window.addEventListener('beforeunload', handleBeforeUnload)
  // 添加滚轮缩放监听
  window.addEventListener('wheel', handleWheel, { passive: false })
})

onUnmounted(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
  window.removeEventListener('wheel', handleWheel)
})

// 离页提示
function handleBeforeUnload(e: BeforeUnloadEvent) {
  if (geoEditorStore.hasUnsavedChanges) {
    e.preventDefault()
    e.returnValue = ''
  }
}

// 滚轮缩放（需要按 Ctrl 或 Alt）
function handleWheel(e: WheelEvent) {
  if (e.ctrlKey || e.altKey) {
    e.preventDefault()
    if (e.deltaY < 0) {
      geoEditorStore.zoomIn()
    } else {
      geoEditorStore.zoomOut()
    }
  }
}

// 返回
function handleBack() {
  if (geoEditorStore.hasUnsavedChanges) {
    ElMessageBox.confirm(
      '有未保存的更改，要保存吗？',
      '提示',
      {
        distinguishCancelAndClose: true,
        confirmButtonText: '保存',
        cancelButtonText: '放弃',
      }
    )
      .then(() => handleSave())
      .then(() => router.back())
      .catch((action) => {
        if (action === 'cancel') {
          router.back()
        }
      })
  } else {
    router.back()
  }
}

// 返回主页
function goHome() {
  if (geoEditorStore.hasUnsavedChanges) {
    ElMessageBox.confirm(
      '有未保存的更改，要保存吗？',
      '提示',
      {
        distinguishCancelAndClose: true,
        confirmButtonText: '保存',
        cancelButtonText: '放弃',
      }
    )
      .then(() => handleSave())
      .then(() => router.push('/home'))
      .catch((action) => {
        if (action === 'cancel') {
          router.push('/home')
        }
      })
  } else {
    router.push('/home')
  }
}

// 撤销
function handleUndo() {
  geoEditorStore.undo()
}

// 重做
function handleRedo() {
  geoEditorStore.redo()
}

// 保存
async function handleSave() {
  isSaving.value = true
  try {
    await geoEditorStore.saveToServer()
    ElMessage.success('保存成功')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally {
    isSaving.value = false
  }
}

// 缩放控制
function handleZoomIn() {
  geoEditorStore.zoomIn()
}

function handleZoomOut() {
  geoEditorStore.zoomOut()
}

function handleResetZoom() {
  geoEditorStore.resetZoom()
}

// 时间轴段落选择
function handleSegmentSelect(segmentId: string) {
  geoEditorStore.selectSegment(segmentId)
}

function handleSegmentHover(segmentId: string | null) {
  geoEditorStore.hoverSegment(segmentId)
}

// 时间轴段落保存
function handleSegmentSave(data: { trackType: TrackType; segmentId: string; value: string; valueEn: string | null }) {
  geoEditorStore.updateSegmentValue(data.trackType, data.segmentId, data.value, data.valueEn)
}

// 图表高亮
function handleChartHighlight(dataIndex: number) {
  for (const track of geoEditorStore.tracks) {
    for (const segment of track.segments) {
      if (dataIndex >= segment.startIndex && dataIndex <= segment.endIndex) {
        geoEditorStore.selectSegment(segment.id)
        // 同步设置指针位置
        geoEditorStore.setPointerPosition(dataIndex / geoEditorStore.points.length)
        return
      }
    }
  }
}

// 指针位置变化
function handlePointerChange(position: number) {
  geoEditorStore.setPointerPosition(position)
}
</script>

<template>
  <div class="geo-editor-container">
    <!-- Header -->
    <el-header class="geo-editor-header">
      <div class="header-left">
        <el-button :icon="ArrowLeft" @click="handleBack" circle />
        <el-button :icon="HomeFilled" @click="goHome" circle />
        <h1 class="track-title">{{ trackName }}</h1>
      </div>
      <div class="header-right">
        <el-button
          :icon="RefreshLeft"
          :disabled="!geoEditorStore.canUndo"
          @click="handleUndo"
          circle
        />
        <el-button
          :icon="RefreshRight"
          :disabled="!geoEditorStore.canRedo"
          @click="handleRedo"
          circle
        />
        <div v-if="geoEditorStore.hasUnsavedChanges" class="unsaved-indicator">
          <el-icon :size="16" color="#f56c6c">
            <WarningFilled />
          </el-icon>
          <span>未保存</span>
        </div>
        <el-button
          type="primary"
          :icon="Check"
          :loading="isSaving"
          :disabled="!geoEditorStore.hasUnsavedChanges"
          @click="handleSave"
        >
          保存
        </el-button>
      </div>
    </el-header>

    <!-- 主内容区 -->
    <el-main class="geo-editor-main">
      <el-empty v-if="isLoading" description="加载中..." />
      <div v-else-if="geoEditorStore.points.length === 0" class="empty-state">
        <el-empty description="暂无轨迹数据" />
      </div>
      <div v-else class="editor-content">
        <!-- 地图区域 -->
        <div class="map-section">
          <UniversalMap
            ref="mapRef"
            :tracks="mapTracks"
            :highlight-segment="highlightedSegment"
            :highlight-point-index="highlightPointIndex"
            mode="detail"
          />
        </div>

        <!-- 图表和时间轴区域 -->
        <div v-show="geoEditorStore.isChartExpanded || geoEditorStore.isTimelineExpanded" class="timeline-container">
          <!-- 控制栏 -->
          <div class="controls-bar">
            <div class="controls-left">
              <el-button-group>
                <el-tooltip content="放大 (Ctrl+滚轮)" placement="top">
                  <el-button :icon="ZoomIn" @click="handleZoomIn" size="small" />
                </el-tooltip>
                <el-tooltip content="缩小 (Ctrl+滚轮)" placement="top">
                  <el-button :icon="ZoomOut" @click="handleZoomOut" size="small" />
                </el-tooltip>
                <el-tooltip content="重置" placement="top">
                  <el-button :icon="Refresh" @click="handleResetZoom" size="small" />
                </el-tooltip>
              </el-button-group>
            </div>
            <div class="controls-center">
              <el-select v-model="geoEditorStore.timeScaleUnit" size="small" style="width: 70px;">
                <el-option value="time" label="时间" />
                <el-option value="duration" label="时长" />
                <el-option value="index" label="索引" />
              </el-select>
            </div>
            <div class="controls-right">
              <el-button size="small" @click="geoEditorStore.isChartExpanded = !geoEditorStore.isChartExpanded">
                {{ geoEditorStore.isChartExpanded ? '图表▼' : '图表▲' }}
              </el-button>
              <el-button size="small" @click="geoEditorStore.isTimelineExpanded = !geoEditorStore.isTimelineExpanded">
                {{ geoEditorStore.isTimelineExpanded ? '时间轴▼' : '时间轴▲' }}
              </el-button>
            </div>
          </div>

          <!-- 内容区域（图表+时间刻度+时间轴） -->
          <div class="timeline-content">
            <!-- 图表区域 -->
            <div v-show="geoEditorStore.isChartExpanded" class="chart-section">
              <GeoChartPanel
                :points="geoEditorStore.points"
                :time-scale-unit="geoEditorStore.timeScaleUnit"
                :highlighted-range="highlightedSegment"
                :zoom-start="geoEditorStore.zoomStart"
                :zoom-end="geoEditorStore.zoomEnd"
                :pointer-position="geoEditorStore.pointerPosition"
                @highlight="handleChartHighlight"
              />
            </div>

            <!-- 时间刻度 -->
            <div v-show="geoEditorStore.isTimelineExpanded" class="scale-section">
              <TimelineScale
                :points="geoEditorStore.points"
                :zoom-start="geoEditorStore.zoomStart"
                :zoom-end="geoEditorStore.zoomEnd"
                @pointer-change="handlePointerChange"
              />
            </div>

            <!-- 时间轴区域 -->
            <div v-show="geoEditorStore.isTimelineExpanded" class="tracks-section">
              <TimelineTracks
                :tracks="tracksData"
                :selected-segment-id="geoEditorStore.selectedSegmentId"
                :hovered-segment-id="geoEditorStore.hoveredSegmentId"
                :zoom-start="geoEditorStore.zoomStart"
                :zoom-end="geoEditorStore.zoomEnd"
                @select="handleSegmentSelect"
                @hover="handleSegmentHover"
                @save="handleSegmentSave"
              />
            </div>

            <!-- 全局指针线（贯穿图表和时间轴） -->
            <div
              v-if="isPointerVisible"
              class="global-playhead"
              :style="{ left: playheadXPosition }"
              @mousedown="handlePlayheadMouseDown"
            >
              <div class="playhead-line"></div>
              <div class="playhead-top"></div>
              <div class="playhead-time">{{ pointerTimeText }}</div>
              <div class="playhead-bottom"></div>
            </div>
          </div>
        </div>
      </div>
    </el-main>
  </div>
</template>

<style scoped>
.geo-editor-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.geo-editor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--el-border-color);
  padding: 0 20px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.track-title {
  margin: 0;
  font-size: 18px;
  font-weight: 500;
}

.unsaved-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #f56c6c;
  font-size: 14px;
}

.geo-editor-main {
  flex: 1;
  overflow: hidden;
  padding: 0;
}

.editor-content {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.empty-state {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.map-section {
  flex: 1;
  border-bottom: 1px solid var(--el-border-color);
  overflow: hidden;
}

.timeline-container {
  border-top: 1px solid var(--el-border-color);
}

.controls-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 12px;
  background: var(--el-bg-color-page);
  border-bottom: 1px solid var(--el-border-color-lighter);
  gap: 8px;
}

.controls-left,
.controls-center,
.controls-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.controls-right {
  margin-left: auto;
}

.chart-section {
  height: 120px;
  position: relative;
}

.scale-section {
  height: 32px;
  position: relative;
}

.tracks-section {
  flex: 1;
  min-height: 160px;
  max-height: 180px;
  overflow: hidden;
  position: relative;
}

.timeline-content {
  position: relative;
}

.chart-section {
  margin-left: 10px;  /* 为 Y 轴标签留出 55px 空间 */
}

.scale-section {
  /* 不需要 margin，内部的 .timeline-scale 有 margin-left: -65px */
}

.tracks-section {
  /* 不需要 margin，内部的 .timeline-tracks 有 margin-left: -65px */
}

.global-playhead {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 2px;
  z-index: 100;
  cursor: ew-resize;
  pointer-events: auto;
}

.global-playhead .playhead-line {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 2px;
  background: #f56c6c;
  transform: translateX(-1px);
}

.global-playhead .playhead-top,
.global-playhead .playhead-bottom {
  position: absolute;
  left: -5px;
  width: 0;
  height: 0;
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
}

.global-playhead .playhead-top {
  top: -4px;
  border-top: 8px solid #f56c6c;
}

.global-playhead .playhead-bottom {
  bottom: -4px;
  border-bottom: 8px solid #f56c6c;
}

.global-playhead .playhead-time {
  position: absolute;
  top: -22px;
  left: 50%;
  transform: translateX(-50%);
  background: #f56c6c;
  color: white;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
  white-space: nowrap;
}
</style>
