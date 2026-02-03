<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, HomeFilled, RefreshLeft, RefreshRight, Check, WarningFilled, ZoomIn, ZoomOut, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useGeoEditorStore, type TrackType } from '@/stores/geoEditor'
import UniversalMap from '@/components/map/UniversalMap.vue'
import GeoChartPanel from '@/components/geo-editor/GeoChartPanel.vue'
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
// 图表引用
const chartRef = ref<InstanceType<typeof GeoChartPanel> | null>(null)

// 高亮区域（基于选中的段落）
const highlightedSegment = computed(() => {
  const id = geoEditorStore.selectedSegmentId || geoEditorStore.hoveredSegmentId
  if (!id) return null

  // 从所有轨道中查找段落
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

// 转换点数据为 UniversalMap 格式
const mapPoints = computed(() => {
  return geoEditorStore.points.map(p => ({
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
  }))
})

// 轨道数据（用于时间轴显示）
const tracksData = computed(() => geoEditorStore.tracks)

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
      chartRef.value?.zoomIn()
    } else {
      chartRef.value?.zoomOut()
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
  chartRef.value?.zoomIn()
}

function handleZoomOut() {
  chartRef.value?.zoomOut()
}

function handleResetZoom() {
  chartRef.value?.resetZoom()
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
  // 找到包含该点的段落
  for (const track of geoEditorStore.tracks) {
    for (const segment of track.segments) {
      if (dataIndex >= segment.startIndex && dataIndex <= segment.endIndex) {
        geoEditorStore.selectSegment(segment.id)
        return
      }
    }
  }
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
      <div v-else-if="geoEditorStore.points.length > 0" class="editor-content">
        <!-- 地图区域 -->
        <div class="map-section">
          <UniversalMap
            ref="mapRef"
            :points="mapPoints"
            :highlight-segment="highlightedSegment"
            mode="detail"
          />
        </div>

        <!-- 图表和时间轴控制栏 -->
        <div class="controls-bar">
          <!-- 左侧：缩放控制 -->
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

          <!-- 中间：时间单位选择 -->
          <div class="controls-center">
            <el-select v-model="geoEditorStore.timeScaleUnit" size="small" style="width: 80px;">
              <el-option value="time" label="时间" />
              <el-option value="duration" label="时长" />
              <el-option value="index" label="索引" />
            </el-select>
          </div>

          <!-- 右侧：折叠按钮 -->
          <div class="controls-right">
            <el-button size="small" @click="geoEditorStore.isChartExpanded = !geoEditorStore.isChartExpanded">
              {{ geoEditorStore.isChartExpanded ? '▼' : '▲' }}
            </el-button>
            <el-button size="small" @click="geoEditorStore.isTimelineExpanded = !geoEditorStore.isTimelineExpanded">
              {{ geoEditorStore.isTimelineExpanded ? '▼' : '▲' }}
            </el-button>
          </div>
        </div>

        <!-- 图表区域 -->
        <div v-show="geoEditorStore.isChartExpanded" class="chart-section">
          <GeoChartPanel
            ref="chartRef"
            :points="geoEditorStore.points"
            :time-scale-unit="geoEditorStore.timeScaleUnit"
            :highlighted-range="highlightedSegment"
            @highlight="handleChartHighlight"
          />
        </div>

        <!-- 时间轴区域 -->
        <div v-show="geoEditorStore.isTimelineExpanded" class="timeline-section">
          <TimelineTracks
            :tracks="tracksData"
            :selected-segment-id="geoEditorStore.selectedSegmentId"
            :hovered-segment-id="geoEditorStore.hoveredSegmentId"
            @select="handleSegmentSelect"
            @hover="handleSegmentHover"
            @save="handleSegmentSave"
          />
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

.map-section {
  flex: 1;
  border-bottom: 1px solid var(--el-border-color);
  overflow: hidden;
}

.controls-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 16px;
  background: var(--el-bg-color-page);
  border-bottom: 1px solid var(--el-border-color-lighter);
  gap: 12px;
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
  height: 140px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.timeline-section {
  flex: 1;
  min-height: 150px;
  max-height: 200px;
  overflow: hidden;
}
</style>
