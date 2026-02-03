<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, HomeFilled, Undo, Redo, Check, WarningFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useGeoEditorStore } from '@/stores/geoEditor'

const route = useRoute()
const router = useRouter()
const geoEditorStore = useGeoEditorStore()

const trackId = ref<number>(parseInt(route.params.id as string))
const isLoading = ref(true)
const isSaving = ref(false)

// 加载数据
onMounted(async () => {
  try {
    await geoEditorStore.loadEditorData(trackId.value)
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
</script>

<template>
  <div class="geo-editor-container">
    <!-- Header -->
    <el-header class="geo-editor-header">
      <div class="header-left">
        <el-button :icon="ArrowLeft" @click="handleBack" circle />
        <el-button :icon="HomeFilled" @click="goHome" circle />
        <h1 class="track-title">地理信息编辑器 #{{ trackId }}</h1>
      </div>
      <div class="header-right">
        <el-button
          :icon="Undo"
          :disabled="!geoEditorStore.canUndo"
          @click="handleUndo"
          circle
        />
        <el-button
          :icon="Redo"
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
      <div v-else class="editor-content">
        <!-- 地图区域 -->
        <div class="map-section">
          <p>地图区域（待集成 UniversalMap）</p>
        </div>

        <!-- 图表区域 -->
        <div class="chart-section">
          <div class="section-header">
            <span class="section-title">▼ 图表</span>
            <el-button size="small" @click="geoEditorStore.isChartExpanded = !geoEditorStore.isChartExpanded">
              {{ geoEditorStore.isChartExpanded ? '折叠' : '展开' }}
            </el-button>
          </div>
          <div v-if="geoEditorStore.isChartExpanded" class="chart-content">
            <p>海拔/速度图表（待集成 ECharts）</p>
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
          <div v-if="geoEditorStore.isTimelineExpanded" class="timeline-content">
            <!-- 时间轴轨道（待集成） -->
            <p>时间轴轨道（待实现）</p>
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
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
}

.chart-section,
.timeline-section {
  border-top: 1px solid var(--el-border-color);
}

.chart-section {
  height: 180px;
}

.timeline-section {
  height: 200px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: var(--el-bg-color-page);
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.section-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-secondary);
}

.chart-content,
.timeline-content {
  padding: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--el-text-color-placeholder);
}
</style>
