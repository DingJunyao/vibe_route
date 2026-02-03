<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, HomeFilled, RefreshLeft, RefreshRight, Check, WarningFilled } from '@element-plus/icons-vue'
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
    elevation: null,
    time: p.time,
    speed: null,
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
})

onUnmounted(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
})

// 离页提示
function handleBeforeUnload(e: BeforeUnloadEvent) {
  if (geoEditorStore.hasUnsavedChanges) {
    e.preventDefault()
    e.returnValue = ''
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

        <!-- 图表区域 -->
        <div class="chart-section">
          <div class="section-header">
            <span class="section-title">▼ 图表</span>
            <el-button size="small" @click="geoEditorStore.isChartExpanded = !geoEditorStore.isChartExpanded">
              {{ geoEditorStore.isChartExpanded ? '折叠' : '展开' }}
            </el-button>
          </div>
          <div v-show="geoEditorStore.isChartExpanded" class="chart-content">
            <GeoChartPanel
              :points="geoEditorStore.points"
              :time-scale-unit="geoEditorStore.timeScaleUnit"
              :highlighted-range="highlightedSegment"
              @highlight="handleChartHighlight"
            />
          </div>
        </div>

        <!-- 时间轴区域 -->
        <div class="timeline-section">
          <div class="section-header">
            <span class="section-title">▼ 时间轴</span>
            <el-select v-model="geoEditorStore.timeScaleUnit" size="small" style="width: 100px; margin-right: 8px;">
              <el-option value="time" label="时间" />
              <el-option value="duration" label="时长" />
              <el-option value="index" label="索引" />
            </el-select>
            <el-button size="small" @click="geoEditorStore.isTimelineExpanded = !geoEditorStore.isTimelineExpanded">
              {{ geoEditorStore.isTimelineExpanded ? '折叠' : '展开' }}
            </el-button>
          </div>
          <div v-show="geoEditorStore.isTimelineExpanded" class="timeline-content">
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

.chart-section,
.timeline-section {
  border-top: 1px solid var(--el-border-color);
}

.chart-section {
  height: 160px;
}

.timeline-section {
  height: 180px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 16px;
  background: var(--el-bg-color-page);
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.section-title {
  font-size: 12px;
  font-weight: 500;
  color: var(--el-text-color-secondary);
}

.chart-content,
.timeline-content {
  height: calc(100% - 36px);
  overflow: hidden;
}
</style>
