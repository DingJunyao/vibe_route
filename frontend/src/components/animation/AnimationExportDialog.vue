<!-- frontend/src/components/animation/AnimationExportDialog.vue -->
<template>
  <el-dialog
    v-model="visible"
    title="导出动画视频"
    width="500px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
      <el-form-item label="分辨率" prop="resolution">
        <el-select v-model="form.resolution" placeholder="选择分辨率">
          <el-option label="720p" value="720p" />
          <el-option label="1080p" value="1080p" />
          <el-option label="4K" value="4k" />
        </el-select>
      </el-form-item>

      <el-form-item label="帧率" prop="fps">
        <el-select v-model="form.fps" placeholder="选择帧率">
          <el-option label="30 fps" :value="30" />
          <el-option label="60 fps" :value="60" />
        </el-select>
      </el-form-item>

      <el-form-item label="显示 HUD">
        <el-switch v-model="form.showHUD" />
      </el-form-item>

      <el-form-item label="导出速度">
        <el-input-number
          v-model="form.speed"
          :min="0.5"
          :max="4"
          :step="0.5"
          :precision="1"
          controls-position="right"
        />
        </el-form-item>

      <el-form-item label="视频格式" prop="format">
        <el-select v-model="form.format" placeholder="选择格式">
          <el-option label="WebM" value="webm" />
          <el-option label="MP4" value="mp4" />
        </el-select>
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleClose">取消</el-button>
        <el-button type="primary" :loading="exporting" @click="handleExport">
          {{ exporting ? '导出中...' : '开始导出' }}
        </el-button>
      </div>
    </template>

    <!-- 进度条 -->
    <div v-if="exporting" class="progress-container">
      <el-progress :percentage="exportProgress" :status="exportStatus" />
      <div class="progress-text">{{ exportProgress }}% - {{ exportStatusText }}</div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { Resolution, ExportConfig } from '@/types/animation'
import { RESOLUTION_DIMENSIONS } from '@/types/animation'

interface Props {
  modelValue: boolean
  trackId: number
  mapProvider: string  // 用于判断是否需要后端导出
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'export', config: ExportConfig): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

// 表单数据
const form = ref({
  resolution: '1080p' as Resolution,
  fps: 30 as 30 | 60,
  showHUD: true,
  speed: 1.0,
  format: 'webm' as 'webm' | 'mp4',
})

const exporting = ref(false)
const exportProgress = ref(0)
const exportStatus = ref<'success' | 'exception' | ''>('')
const formRef = ref()

// 表单验证规则
const rules = {
  resolution: [{ required: true, message: '请选择分辨率', trigger: 'change' }],
  fps: [{ required: true, message: '请选择帧率', trigger: 'change' }],
  format: [{ required: true, message: '请选择视频格式', trigger: 'change' }],
}

// 计算导出状态文本
const exportStatusText = computed(() => {
  if (exportStatus.value === 'success') return '导出完成'
  if (exportStatus.value === 'exception') return '导出失败'
  return '正在处理...'
})

// 监听 visible 变化，重置状态
watch(visible, (newVal) => {
  if (!newVal) {
    exporting.value = false
    exportProgress.value = 0
    exportStatus.value = ''
  }
})

function handleClose() {
  visible.value = false
}

async function handleExport() {
  const valid = await formRef.value?.validate()
  if (!valid) return

  exporting.value = true
  exportProgress.value = 0
  exportStatus.value = ''

  try {
    emit('export', {
      resolution: form.value.resolution,
      fps: form.value.fps,
      showHUD: form.value.showHUD,
      format: form.value.format,
      speed: form.value.speed,
    })
  } catch (e) {
    console.error('Export error:', e)
    exportStatus.value = 'exception'
  } finally {
    exporting.value = false
  }
}
</script>

<style scoped>
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.progress-container {
  margin-top: 20px;
}

.progress-text {
  text-align: center;
  font-size: 12px;
  margin-top: 8px;
  color: var(--el-text-color-secondary);
}

:deep(.el-dialog__body) {
  padding-bottom: 0;
}
</style>
