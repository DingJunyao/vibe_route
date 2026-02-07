<template>
  <el-dialog
    v-model="dialogVisible"
    title="导出海报"
    :width="isMobile ? '95%' : '500px'"
    :close-on-click-modal="false"
    class="responsive-dialog"
    @close="handleClose"
  >
    <!-- 配置区域 -->
    <div class="poster-config">
      <!-- 模板选择 -->
      <el-form-item label="模板">
        <el-radio-group v-model="config.template">
          <el-radio value="minimal">极简</el-radio>
          <el-radio value="simple">简洁</el-radio>
          <el-radio value="rich">丰富</el-radio>
          <el-radio value="geo">地理</el-radio>
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

      <!-- 地图缩放 -->
      <el-form-item label="地图缩放">
        <el-slider
          v-model="config.mapScale"
          :min="100"
          :max="200"
          :step="10"
          show-input
          :input-size="'small'"
        />
        <div class="radio-hint scale-radio-hint">放大地图要素，适用于大尺寸海报</div>
      </el-form-item>

      <!-- 水印开关 -->
      <el-form-item label="水印">
        <el-switch v-model="config.showWatermark" />
      </el-form-item>
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
      <div class="dialog-footer">
        <div class="map-adjust-hint">
          如果你对轨迹相对尺寸和位置不满意，也可以
          <el-link
            :href="mapOnlyUrl"
            target="_blank"
            type="primary"
            :underline="false"
          >
            打开地图
          </el-link>
          ，手动调整并自行截图。
        </div>
        <div class="dialog-footer-buttons">
          <el-button @click="handleClose" :disabled="isGenerating">取消</el-button>
          <el-button type="primary" @click="handleExport" :loading="isGenerating">
            导出
          </el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { generatePoster, type PosterGenerateRequest } from '@/api/poster'
import type { Track, TrackPoint } from '@/api/track'
import { useConfigStore } from '@/stores/config'

interface Props {
  visible: boolean
  track: Track | null
  points: TrackPoint[]
  mapRef?: any
  posterSecret?: string  // 海报访问密钥，用于构建地图链接
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
  points: () => [],
  mapRef: undefined,
  posterSecret: '',
})

const emit = defineEmits<{
  'update:visible': [value: boolean]
}>()

const configStore = useConfigStore()
const dialogVisible = ref(props.visible)

const config = ref({
  template: 'minimal',
  sizePreset: 'landscape_1080',
  mapScale: 100,
  showWatermark: true,
})

const progress = ref({
  stage: 'idle',
  message: '',
  percent: 0,
})
const isGenerating = ref(false)
const isMobile = computed(() => window.innerWidth <= 1366)

// 纯地图页面 URL（不携带 secret，由地图页面处理权限）
const mapOnlyUrl = computed(() => {
  if (!props.track) return '#'
  const baseUrl = `/tracks/${props.track.id}/map-only`
  const provider = getCurrentProvider()
  const params = new URLSearchParams({
    provider,
  })
  return `${baseUrl}?${params.toString()}`
})

// 获取当前使用的地图提供商
function getCurrentProvider(): string {
  if (props.mapRef?.getCurrentLayerId) {
    return props.mapRef.getCurrentLayerId()
  }
  // 降级：使用配置的默认地图
  return configStore.getMapProvider() || 'osm'
}

watch(() => props.visible, (newVal) => {
  dialogVisible.value = newVal
  if (!newVal) {
    progress.value = { stage: 'idle', message: '', percent: 0 }
  }
})

watch(dialogVisible, (newVal) => {
  if (newVal !== props.visible) {
    emit('update:visible', newVal)
  }
})

function handleClose(): void {
  if (isGenerating.value) {
    ElMessage.warning('正在生成海报，请稍候...')
    return
  }
  dialogVisible.value = false
}

function getMapBounds(): { minLat: number; maxLat: number; minLon: number; maxLon: number } {
  if (props.points.length === 0) {
    throw new Error('轨迹点为空')
  }

  let minLat = Infinity, maxLat = -Infinity
  let minLon = Infinity, maxLon = -Infinity

  for (const point of props.points) {
    const lat = point.latitude_gcj02 || point.latitude || 0
    const lon = point.longitude_gcj02 || point.longitude || 0

    if (lat < minLat) minLat = lat
    if (lat > maxLat) maxLat = lat
    if (lon < minLon) minLon = lon
    if (lon > maxLon) maxLon = lon
  }

  return { minLat, maxLat, minLon, maxLon }
}

function getSizeConfig() {
  const presets: Record<string, { width: number; height: number }> = {
    portrait_1080: { width: 1080, height: 1920 },
    portrait_4k: { width: 2160, height: 3840 },
    landscape_1080: { width: 1920, height: 1080 },
    landscape_4k: { width: 3840, height: 2160 },
  }
  return presets[config.value.sizePreset] || presets.landscape_1080
}

async function handleExport(): Promise<void> {
  if (!props.track) {
    ElMessage.error('轨迹数据不存在')
    return
  }

  isGenerating.value = true
  progress.value = { stage: 'idle', message: '', percent: 0 }

  try {
    progress.value = { stage: 'capturing', message: '正在生成海报...', percent: 20 }

    const size = getSizeConfig()
    const bounds = getMapBounds()
    const provider = getCurrentProvider()

    const request: PosterGenerateRequest = {
      config: {
        template: config.value.template,
        width: size.width,
        height: size.height,
        show_watermark: config.value.showWatermark,
        map_scale: config.value.mapScale,
      },
      track: {
        track_id: props.track.id,
        name: props.track.name,
        points: props.points,
        distance: props.track.distance,
        duration: props.track.duration,
        elevation_gain: props.track.elevation_gain,
        elevation_loss: props.track.elevation_loss,
        start_time: props.track.start_time,
        end_time: props.track.end_time,
      },
      bounds: {
        min_lat: bounds.minLat,
        max_lat: bounds.maxLat,
        min_lon: bounds.minLon,
        max_lon: bounds.maxLon,
      },
      provider,
    }

    progress.value = { stage: 'drawing', message: '服务器正在渲染...', percent: 50 }

    const blob = await generatePoster(request)

    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${props.track.name}_海报.png`
    link.click()
    URL.revokeObjectURL(url)

    progress.value = { stage: 'done', message: '导出完成', percent: 100 }
    ElMessage.success('海报导出成功')
  } catch (error) {
    console.error('海报导出失败:', error)
    const errorMsg = error instanceof Error ? error.message : '海报导出失败'
    ElMessage.error(errorMsg)
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

.poster-config :deep(.el-form-item__label) {
  width: 70px;
}

.radio-hint {
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.4;
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
  flex-direction: column;
  gap: 12px;
  align-items: stretch;
}

.map-adjust-hint {
  padding: 10px;
  background-color: var(--el-color-info-light-9);
  border-radius: 4px;
  font-size: 13px;
  color: var(--el-text-color-regular);
  line-height: 1.5;
  text-align: left;
}

.map-adjust-hint .el-link {
  font-size: inherit;
  line-height: inherit;
  vertical-align: baseline;
}

.dialog-footer-buttons {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

/* 移动端样式 */
@media (max-width: 1366px) {
  .map-adjust-hint {
    font-size: 12px;
  }
}
</style>
