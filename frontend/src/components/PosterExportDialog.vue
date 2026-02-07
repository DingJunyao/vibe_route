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
    <div v-if="!exportDisabled" class="poster-config">
      <!-- 生成方式（移动设备隐藏，百度地图也隐藏，配置禁用服务器生成时也隐藏） -->
      <el-form-item v-if="showGenerationMode" label="生成方式">
        <el-radio-group v-model="config.generationMode" @change="onConfigChange">
          <el-radio value="frontend">浏览器生成</el-radio>
          <el-radio value="backend">服务器生成</el-radio>
        </el-radio-group>
        <div class="radio-hint">
          <template v-if="config.generationMode === 'frontend'">
            浏览器本地生成，无需服务器，推荐使用
          </template>
          <template v-else>
            服务器生成，适合复杂场景
          </template>
        </div>
      </el-form-item>

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
          @change="onConfigChange"
        />
        <div class="radio-hint scale-radio-hint">放大地图要素，适用于大尺寸海报</div>
      </el-form-item>

      <!-- 水印开关 -->
      <el-form-item label="水印">
        <el-switch v-model="config.showWatermark" @change="onConfigChange" />
      </el-form-item>
    </div>

    <!-- 禁用导出时的提示 -->
    <div v-else class="poster-disabled-hint">
      <div class="map-adjust-hint">
        如果要导出海报，你可以
        <el-link
          :href="mapOnlyUrl"
          target="_blank"
          type="primary"
          :underline="false"
        >
          打开地图
        </el-link>
        手动调整截图。
      </div>
    </div>

    <!-- 预览区域 -->
    <div v-if="previewUrl" class="poster-preview">
      <div class="preview-header">
        <span>地图预览</span>
        <el-button link type="danger" @click="clearPreview">清除</el-button>
      </div>
      <div class="preview-image-container">
        <img :src="previewUrl" alt="预览" class="preview-image" />
      </div>
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
        <!-- 未禁用时显示完整按钮区域 -->
        <template v-if="!exportDisabled">
          <div class="map-adjust-hint">
            <template v-if="config.generationMode === 'frontend'">
              预览地图效果，确认无误后再导出。或者
            </template>
            <template v-else>
              如果对生成效果不满意，也可以
            </template>
            <el-link
              :href="mapOnlyUrl"
              target="_blank"
              type="primary"
              :underline="false"
            >
              打开地图
            </el-link>
            手动调整截图。
          </div>
          <div class="dialog-footer-buttons">
            <el-button
              v-if="config.generationMode === 'frontend'"
              @click="handlePreview"
              :loading="isPreviewing"
              :disabled="!canPreview"
            >
              预览
            </el-button>
            <el-button @click="handleClose" :disabled="isGenerating">取消</el-button>
            <el-button type="primary" @click="handleExport" :loading="isGenerating">
              导出
            </el-button>
          </div>
        </template>
        <!-- 禁用时只显示取消按钮 -->
        <template v-else>
          <div class="dialog-footer-buttons dialog-footer-buttons-center">
            <el-button @click="handleClose">取消</el-button>
          </div>
        </template>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, computed, watchEffect } from 'vue'
import { ElMessage } from 'element-plus'
import html2canvas from 'html2canvas'
import { generatePoster, type PosterGenerateRequest } from '@/api/poster'
import { generateFrontendPoster, type PosterConfig as FrontendPosterConfig } from '@/utils/frontendPosterGenerator'
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

// 检测移动设备（iOS/Android，非屏幕尺寸）
function isMobileDevice(): boolean {
  const ua = navigator.userAgent
  return /iPad|iPhone|iPod/.test(ua) || /Android/.test(ua)
}

const config = ref({
  generationMode: isMobileDevice() ? 'backend' : 'frontend',  // 移动设备强制使用后端
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
const isPreviewing = ref(false)
const isMobile = computed(() => window.innerWidth <= 1366)
const isMobileDeviceComputed = computed(() => isMobileDevice())

// 检测是否是百度地图
const isBaiduMap = computed(() => {
  const provider = getCurrentProvider()
  return provider === 'baidu' || provider === 'baidu_legacy'
})

// 当前地图提供商（用于监听变化）
const currentProvider = computed(() => getCurrentProvider())

// 监听地图切换，清除预览
watch(currentProvider, () => {
  clearPreview()
})

// 是否显示生成方式选择（百度地图隐藏，移动设备也隐藏，配置禁用服务器生成时也隐藏）
const showGenerationMode = computed(() => {
  const allowServerPoster = configStore.publicConfig?.allow_server_poster ?? true
  return !isMobileDeviceComputed.value && !isBaiduMap.value && allowServerPoster
})

// 是否禁用导出（配置禁用服务器生成 且 (百度地图 或 移动设备)）
const exportDisabled = computed(() => {
  const allowServerPoster = configStore.publicConfig?.allow_server_poster ?? true
  return !allowServerPoster && (isBaiduMap.value || isMobileDeviceComputed.value)
})

// 预览相关
const previewUrl = ref('')
const previewIframe = ref<HTMLIFrameElement | null>(null)
const lastPreviewConfig = ref('')

// 配置变化时清除预览
function onConfigChange() {
  clearPreview()
}

// 是否可以预览（仅前端生成支持预览）
const canPreview = computed(() => {
  return config.value.generationMode === 'frontend' && !isPreviewing.value && !isGenerating.value
})

// 清除预览
function clearPreview() {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = ''
  }
  // 清理 iframe
  if (previewIframe.value) {
    try {
      document.body.removeChild(previewIframe.value)
    } catch (e) {
      // 忽略
    }
    previewIframe.value = null
  }
  lastPreviewConfig.value = ''
  // 确保预览状态重置
  isPreviewing.value = false
  progress.value = { stage: 'idle', message: '', percent: 0 }
}

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
  if (newVal) {
    // 对话框打开时，检测当前地图提供商
    const provider = getCurrentProvider()
    const isBaidu = provider === 'baidu' || provider === 'baidu_legacy'
    const allowServerPoster = configStore.publicConfig?.allow_server_poster ?? true

    // 百度地图强制使用服务器端生成
    if (isBaidu) {
      config.value.generationMode = 'backend'
      console.log('[PosterExportDialog] 百度地图强制使用服务器端生成')
    }
    // 配置禁用服务器生成时，强制使用浏览器生成
    else if (!allowServerPoster) {
      config.value.generationMode = 'frontend'
      console.log('[PosterExportDialog] 配置禁用服务器生成，强制使用浏览器生成')
    }
  } else {
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

/**
 * 前端生成海报
 */
async function generatePosterFrontend(): Promise<void> {
  if (!props.track) {
    throw new Error('轨迹数据不存在')
  }

  const provider = getCurrentProvider()
  const isBaidu = provider === 'baidu' || provider === 'baidu_legacy'

  // 百度地图存在 CORS 跨域问题，自动切换到服务器端生成
  if (isBaidu) {
    console.log('[Export] 百度地图自动切换到服务器端生成')
    config.value.generationMode = 'backend'
    await generatePosterBackend()
    return
  }

  const size = getSizeConfig()
  const secret = props.posterSecret || 'vibe-route-poster-secret'

  const frontendConfig: FrontendPosterConfig = {
    template: config.value.template as any,
    width: size.width,
    height: size.height,
    showWatermark: config.value.showWatermark,
    mapScale: config.value.mapScale,
  }

  const trackData = {
    name: props.track.name,
    distance: props.track.distance,
    duration: props.track.duration,
    elevation_gain: props.track.elevation_gain,
    elevation_loss: props.track.elevation_loss,
  }

  const blob = await generateFrontendPoster(
    frontendConfig,
    props.track.id,
    provider,
    secret,
    trackData,
    (stage, message, percent) => {
      progress.value = { stage, message, percent }
    }
  )

  // 下载图片
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${props.track.name}_海报.png`
  link.click()
  URL.revokeObjectURL(url)
}

/**
 * 后端生成海报
 */
async function generatePosterBackend(): Promise<void> {
  if (!props.track) {
    throw new Error('轨迹数据不存在')
  }

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

  const blob = await generatePoster(request)

  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${props.track.name}_海报.png`
  link.click()
  URL.revokeObjectURL(url)
}

/**
 * 生成预览
 */
async function handlePreview(): Promise<void> {
  if (!props.track) {
    ElMessage.error('轨迹数据不存在')
    return
  }

  if (exportDisabled.value) {
    return
  }

  // 检查配置是否变化，如果没变化且有缓存则使用缓存
  const currentConfig = JSON.stringify({
    template: config.value.template,
    sizePreset: config.value.sizePreset,
    mapScale: config.value.mapScale,
  })

  if (lastPreviewConfig.value === currentConfig && previewUrl.value) {
    return
  }

  isPreviewing.value = true
  progress.value = { stage: 'previewing', message: '正在生成预览...', percent: 0 }

  try {
    const provider = getCurrentProvider()
    const isBaidu = provider === 'baidu' || provider === 'baidu_legacy'

    // 百度地图存在 CORS 跨域问题，自动切换到服务器端生成
    if (isBaidu) {
      console.log('[Preview] 百度地图自动切换到服务器端生成')
      config.value.generationMode = 'backend'
      await generatePosterBackend()
      progress.value = { stage: 'done', message: '预览生成完成', percent: 100 }
      return
    }

    const size = getSizeConfig()
    const secret = props.posterSecret || 'vibe-route-poster-secret'

    // 创建 iframe 并加载地图
    const iframe = await loadMapInIframe(props.track.id, provider, secret, config.value.mapScale, size)

    try {
      // 等待地图就绪
      await waitForMapReady(iframe)

      // 截取地图
      const mapCanvas = await captureMap(iframe)

      // 转换为预览图片
      previewUrl.value = mapCanvas.toDataURL('image/png', 0.9)
      lastPreviewConfig.value = currentConfig

      progress.value = { stage: 'done', message: '预览生成完成', percent: 100 }
      ElMessage.success('预览生成成功')

      // 1秒后清除进度
      setTimeout(() => {
        if (progress.value.stage === 'done') {
          progress.value = { stage: 'idle', message: '', percent: 0 }
        }
      }, 1000)
    } finally {
      // 清理 iframe
      if (iframe && iframe.parentNode) {
        document.body.removeChild(iframe)
      }
    }
  } catch (error) {
    console.error('预览生成失败:', error)
    const errorMsg = error instanceof Error ? error.message : '预览生成失败'
    ElMessage.error(errorMsg)
    progress.value = { stage: 'error', message: '预览失败', percent: 0 }
  } finally {
    isPreviewing.value = false
  }
}

/**
 * 加载地图到隐藏的 iframe
 */
async function loadMapInIframe(
  trackId: number,
  provider: string,
  secret: string,
  mapScale: number,
  size: { width: number; height: number }
): Promise<HTMLIFrameElement> {
  return new Promise((resolve, reject) => {
    const iframe = document.createElement('iframe')
    iframe.style.position = 'absolute'
    iframe.style.left = '-9999px'
    iframe.style.top = '0'
    iframe.style.width = `${size.width}px`
    iframe.style.height = `${size.height}px`
    iframe.style.border = 'none'

    // 百度地图统一使用 Legacy 版本（非 WebGL，避免截图问题）
    const mapProvider = provider === 'baidu' ? 'baidu_legacy' : provider
    const url = `/tracks/${trackId}/map-only?provider=${mapProvider}&secret=${secret}&map_scale=${mapScale}&width=${size.width}&height=${size.height}`

    // 超时处理
    const timeout = setTimeout(() => {
      if (iframe.parentNode) {
        document.body.removeChild(iframe)
      }
      reject(new Error('iframe 加载超时'))
    }, 30000)  // 30 秒超时

    iframe.onload = () => {
      clearTimeout(timeout)
      resolve(iframe)
    }
    iframe.onerror = () => {
      clearTimeout(timeout)
      reject(new Error('iframe 加载失败'))
    }

    iframe.src = url
    document.body.appendChild(iframe)
  })
}

/**
 * 等待地图就绪
 */
async function waitForMapReady(iframe: HTMLIFrameElement): Promise<void> {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      reject(new Error('等待地图就绪超时'))
    }, 60000)

    const checkReady = () => {
      try {
        if ((iframe.contentWindow as any)?.mapReady === true) {
          clearTimeout(timeout)
          // 额外等待确保渲染完成
          const baseWait = 500
          const scaleWait = (config.value.mapScale - 100) * 30
          setTimeout(resolve, baseWait + scaleWait)
        } else {
          setTimeout(checkReady, 100)
        }
      } catch (e) {
        // 跨域错误，继续检查
        setTimeout(checkReady, 100)
      }
    }

    checkReady()
  })
}

/**
 * 截取地图
 */
async function captureMap(iframe: HTMLIFrameElement): Promise<HTMLCanvasElement> {
  const iframeDoc = iframe.contentDocument
  if (!iframeDoc) {
    throw new Error('无法访问 iframe 内容')
  }

  // 截取整个页面，包含缩放后的地图
  const mapElement = iframeDoc.querySelector('.map-only-page') as HTMLElement
  if (!mapElement) {
    throw new Error('找不到地图容器')
  }

  // 获取实际渲染尺寸（考虑 CSS scale）
  const mapWrapper = iframeDoc.querySelector('.map-wrapper-container') as HTMLElement
  const actualWidth = mapWrapper ? mapWrapper.offsetWidth : parseInt(iframeDoc.documentElement.style.width || '0')
  const actualHeight = mapWrapper ? mapWrapper.offsetHeight : parseInt(iframeDoc.documentElement.style.height || '0')

  console.log('[Capture] 地图容器尺寸:', {
    mapOnlyPage: { w: mapElement.offsetWidth, h: mapElement.offsetHeight },
    mapWrapper: { w: actualWidth, h: actualHeight }
  })

  // 使用 html2canvas 截图
  const canvas = await html2canvas(mapElement, {
    useCORS: true,
    allowTaint: true,
    scale: 1,
    logging: false,
    backgroundColor: '#e5e5e5',
    foreignObjectRendering: false,
    removeContainer: true,
    imageTimeout: 15000,
  })

  console.log('[Capture] 截图完成，canvas 尺寸:', { w: canvas.width, h: canvas.height })
  return canvas
}

async function handleExport(): Promise<void> {
  if (!props.track) {
    ElMessage.error('轨迹数据不存在')
    return
  }

  if (exportDisabled.value) {
    return
  }

  isGenerating.value = true
  progress.value = { stage: 'idle', message: '', percent: 0 }

  try {
    if (config.value.generationMode === 'frontend') {
      progress.value = { stage: 'capturing', message: '正在生成海报...', percent: 10 }
      await generatePosterFrontend()
    } else {
      progress.value = { stage: 'capturing', message: '正在生成海报...', percent: 20 }
      progress.value = { stage: 'drawing', message: '服务器正在渲染...', percent: 50 }
      await generatePosterBackend()
    }

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
  width: 80px;
}

.poster-config :deep(.el-form-item__content) {
  flex-direction: column;
  align-items: flex-start;
}

.radio-hint {
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.4;
}

.scale-radio-hint {
  /* 地图缩放提示的特殊样式（如果需要） */
}

/* 预览区域 */
.poster-preview {
  margin: 16px 0;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  overflow: hidden;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  background-color: var(--el-fill-color-light);
  border-bottom: 1px solid var(--el-border-color);
  font-size: 14px;
  font-weight: 500;
}

.preview-image-container {
  width: 100%;
  max-height: 400px;
  overflow: hidden;
  background-color: #f5f5f5;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-image {
  max-width: 100%;
  max-height: 400px;
  object-fit: contain;
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

.dialog-footer-buttons-center {
  justify-content: center;
}

.poster-disabled-hint {
  margin-bottom: 20px;
}

/* 移动端样式 */
@media (max-width: 1366px) {
  .map-adjust-hint {
    font-size: 12px;
  }
}
</style>
