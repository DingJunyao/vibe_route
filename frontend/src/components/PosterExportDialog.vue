<template>
  <el-dialog
    v-model="dialogVisible"
    title="导出海报"
    :width="isMobile ? '90%' : '600px'"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <!-- 配置区域 -->
    <div class="poster-config">
      <!-- 模板选择 -->
      <el-form-item label="模板">
        <el-radio-group v-model="config.template">
          <el-radio value="simple">简洁模板</el-radio>
          <el-radio value="rich">丰富模板</el-radio>
          <el-radio value="geo">地理模板</el-radio>
        </el-radio-group>
      </el-form-item>

      <!-- 尺寸预设 -->
      <el-form-item label="尺寸">
        <el-select v-model="config.sizePreset" placeholder="选择尺寸" style="width: 100%">
          <el-option label="竖版 1080P" value="portrait_1080" />
          <el-option label="竖版 4K" value="portrait_4k" />
          <el-option label="横版 1080P" value="landscape_1080" />
          <el-option label="横版 4K" value="landscape_4k" />
        </el-select>
      </el-form-item>

      <!-- 水印开关 -->
      <el-form-item label="水印">
        <el-switch v-model="config.showWatermark" />
      </el-form-item>
    </div>

    <!-- 预览区域 -->
    <div v-if="previewUrl" class="poster-preview">
      <img :src="previewUrl" alt="预览" />
    </div>

    <!-- 进度显示 -->
    <div v-if="progress.stage !== 'idle'" class="poster-progress">
      <el-progress
        :percentage="progress.percent"
        :status="progress.stage === 'error' ? 'exception' : progress.stage === 'done' ? 'success' : undefined"
      />
      <p class="progress-text">{{ progress.message }}</p>
    </div>

    <!-- 按钮区域 -->
    <template #footer>
      <span class="dialog-footer">
        <el-button @click="handleClose" :disabled="isGenerating">取消</el-button>
        <el-button type="primary" @click="handlePreview" :disabled="isGenerating" plain>
          预览
        </el-button>
        <el-button type="primary" @click="handleExport" :loading="isGenerating">
          导出
        </el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
/**
 * 海报导出对话框
 * 用于配置和生成轨迹海报
 */
import { ref, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { PosterGenerator } from '@/utils/posterGenerator'
import type { PosterConfig, PosterProgress } from '@/types/poster'
import type { Track, TrackPoint, RegionNode } from '@/api/track'

// Props
interface Props {
  visible: boolean
  track: Track | null
  points: TrackPoint[]
  regions?: RegionNode[]
  mapElement: HTMLElement | null
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
  points: () => [],
  regions: () => [],
  mapElement: null,
})

// Emits
const emit = defineEmits<{
  'update:visible': [value: boolean]
}>()

// 对话框可见性
const dialogVisible = ref(props.visible)

// 配置
const config = ref<PosterConfig>({
  template: 'simple',
  sizePreset: 'portrait_1080',
  showWatermark: true,
  infoLevel: 'basic',
})

// 预览图片
const previewUrl = ref('')

// 进度
const progress = ref<PosterProgress>({
  stage: 'idle',
  message: '',
  percent: 0,
})

// 是否正在生成
const isGenerating = ref(false)

// 计算是否移动端
const isMobile = computed(() => window.innerWidth <= 1366)

// 监听 visible 变化
watch(() => props.visible, (newVal) => {
  dialogVisible.value = newVal
  if (!newVal) {
    // 关闭时清空预览
    previewUrl.value = ''
    progress.value = { stage: 'idle', message: '', percent: 0 }
  }
})

watch(dialogVisible, (newVal) => {
  if (newVal !== props.visible) {
    emit('update:visible', newVal)
  }
})

/**
 * 关闭对话框
 */
function handleClose(): void {
  if (isGenerating.value) {
    ElMessage.warning('正在生成海报，请稍候...')
    return
  }
  dialogVisible.value = false
}

/**
 * 准备海报数据
 */
function preparePosterData() {
  if (!props.track) {
    throw new Error('轨迹数据不存在')
  }

  const { regions } = props
  let regionNames: string[] = []

  // 提取区域名称
  if (regions && regions.length > 0) {
    const extractNames = (nodes: RegionNode[]): string[] => {
      const names: string[] = []
      for (const node of nodes) {
        if (node.type === 'province' || node.type === 'city' || node.type === 'district') {
          names.push(node.name)
        }
        if (node.children && node.children.length > 0) {
          names.push(...extractNames(node.children))
        }
      }
      return names
    }
    regionNames = extractNames(regions)
  }

  return {
    name: props.track.name,
    date: props.track.start_time ? new Date(props.track.start_time).toLocaleDateString('zh-CN') : '',
    startTime: props.track.start_time || '',
    endTime: props.track.end_time || '',
    distance: props.track.distance,
    duration: props.track.duration,
    elevationGain: props.track.elevation_gain,
    elevationLoss: props.track.elevation_loss,
    regions: regionNames.length > 0 ? regionNames : undefined,
  }
}

/**
 * 预览海报
 */
async function handlePreview(): Promise<void> {
  if (!props.mapElement) {
    ElMessage.error('地图未加载完成')
    return
  }

  isGenerating.value = true
  progress.value = { stage: 'idle', message: '', percent: 0 }

  try {
    const generator = new PosterGenerator(config.value, (p) => {
      progress.value = p
    })

    // 捕获地图（使用低 scale 预览）
    const mapImage = await generator.captureMap(props.mapElement!, 1)

    // 准备数据
    const data = preparePosterData()
    data.mapImage = mapImage

    // 生成海报
    const canvas = await generator.generate(data)
    previewUrl.value = canvas.toDataURL('image/png')

    progress.value = { stage: 'done', message: '预览生成完成', percent: 100 }
  } catch (error) {
    console.error('预览生成失败:', error)
    ElMessage.error(error instanceof Error ? error.message : '预览生成失败')
    progress.value = { stage: 'error', message: '预览生成失败', percent: 0 }
  } finally {
    isGenerating.value = false
  }
}

/**
 * 导出海报
 */
async function handleExport(): Promise<void> {
  if (!props.mapElement) {
    ElMessage.error('地图未加载完成')
    return
  }

  if (!props.track) {
    ElMessage.error('轨迹数据不存在')
    return
  }

  isGenerating.value = true
  progress.value = { stage: 'idle', message: '', percent: 0 }
  previewUrl.value = ''

  try {
    const generator = new PosterGenerator(config.value, (p) => {
      progress.value = p
    })

    // 获取 scale
    const scale = config.value.sizePreset.includes('4k') ? 4 : 2

    // 捕获地图
    const mapImage = await generator.captureMap(props.mapElement, scale)

    // 准备数据
    const data = preparePosterData()
    data.mapImage = mapImage

    // 生成海报
    const canvas = await generator.generate(data)

    // 下载
    generator.downloadPoster(canvas, props.track.name)

    ElMessage.success('海报导出成功')
  } catch (error) {
    console.error('海报导出失败:', error)
    ElMessage.error(error instanceof Error ? error.message : '海报导出失败')
    progress.value = { stage: 'error', message: '导出失败', percent: 0 }
  } finally {
    isGenerating.value = false
  }
}
</script>

<style scoped>
.poster-config {
  margin-bottom: 20px;
}

.poster-config .el-form-item {
  margin-bottom: 16px;
}

.poster-preview {
  margin: 20px 0;
  text-align: center;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  padding: 10px;
  background: var(--el-fill-color-lighter);
}

.poster-preview img {
  max-width: 100%;
  max-height: 400px;
  border-radius: 4px;
}

.poster-progress {
  margin: 20px 0;
}

.progress-text {
  margin-top: 10px;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
