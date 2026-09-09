// frontend/src/utils/animation/videoExport.ts

import { http } from '@/api/request'
import { useAnimationStore } from '@/stores/animation'
import { getGlobalViewState } from '@/composables/animation/useAnimationMap'
import { getBackendOrigin } from '@/utils/origin'
import type { Resolution, ExportConfig, ExportOptions } from '@/types/animation'

interface AnimationTask {
  task_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled'
  progress: number
  download_url?: string
  error?: string
}

/**
 * 检查浏览器是否支持 MediaRecorder
 */
export function checkMediaRecorderSupport(): boolean {
  return typeof MediaRecorder !== 'undefined' &&
    typeof MediaRecorder.isTypeSupported === 'function'
}

/**
 * 获取支持的媒体类型
 */
export function getSupportedMimeType(): string {
  const preferred = [
    'video/webm;codecs=vp9',
    'video/webm;codecs=vp8',
    'video/webm;codecs=h264',
    'video/mp4',
    'video/webm',
  ]

  for (const type of preferred) {
    if (MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(type)) {
      return type
    }
  }

  return 'video/webm'
}

/**
 * 将 canvas 转换为视频
 */
export async function canvasToVideo(
  canvas: HTMLCanvasElement,
  duration: number,
  config: ExportConfig,
  onProgress: (progress: number) => void
): Promise<Blob> {
  return new Promise((resolve, reject) => {
    const stream = canvas.captureStream(30)
    const mimeType = getSupportedMimeType()

    let mediaRecorder: MediaRecorder | null

    try {
      mediaRecorder = new MediaRecorder(stream, { mimeType })
    } catch (e) {
      console.warn('Failed to create MediaRecorder with mimeType:', mimeType, e)
      mediaRecorder = new MediaRecorder(stream)
    }

    const chunks: Blob[] = []

    mediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) {
        chunks.push(e.data)
        const totalSize = chunks.reduce((sum, c) => sum + c.size, 0)
        const progress = (totalSize / (duration * 1000 * 1024)) * 100
        onProgress(Math.min(100, progress))
      }
    }

    mediaRecorder.onstop = () => {
      const blob = new Blob(chunks, { type: mimeType })
      stream.getTracks().forEach(track => track.stop())
      resolve(blob)
    }

    mediaRecorder.onerror = (e) => {
      console.error('MediaRecorder error:', e)
      reject(e)
    }

    mediaRecorder.start()

    // 记录完成后停止
    setTimeout(() => {
      if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop()
      }
    }, duration + 500) // 额外 500ms 确保完整录制
  })
}

/**
 * 组装完整导出配置：对话框选项 + 当前动画/地图视图状态
 */
export function buildExportConfig(options: ExportOptions): ExportConfig {
  const animationStore = useAnimationStore()
  const view = getGlobalViewState()

  return {
    ...options,
    startTime: animationStore.currentTime,
    cameraMode: animationStore.cameraMode,
    orientationMode: animationStore.orientationMode,
    markerStyle: animationStore.markerStyle,
    showInfoPanel: animationStore.showInfoPanel,
    layerId: view.layerId || undefined,
    zoom: view.zoom,
    center: view.center,
    viewportWidth: view.width || undefined,
    viewportHeight: view.height || undefined,
  }
}

/**
 * 使用后端 Playwright 导出（推荐用于百度地图）
 */
export async function exportWithPlaywright(
  trackId: number,
  config: ExportConfig,
  onProgress: (progress: number) => void
): Promise<string> {
  const {
    resolution,
    showHUD,
    speed,
    startTime,
    cameraMode,
    orientationMode,
    markerStyle,
    showInfoPanel,
    layerId,
    zoom,
    center,
    viewportWidth,
    viewportHeight,
  } = config

  // 调用后端 API 启动导出（走统一客户端，自动携带认证头）
  const task = await http.post<AnimationTask>(
    '/animation/export',
    {
      resolution,
      show_hud: showHUD,
      speed,
      start_time: startTime,
      camera_mode: cameraMode,
      orientation_mode: orientationMode,
      marker_style: markerStyle,
      show_info_panel: showInfoPanel,
      layer_id: layerId ?? null,
      zoom: zoom ?? null,
      center_lat: center?.lat ?? null,
      center_lng: center?.lng ?? null,
      viewport_width: viewportWidth ?? null,
      viewport_height: viewportHeight ?? null,
    },
    {
      params: { track_id: trackId },
      skipProgress: true,
    },
  )

  // 轮询导出进度
  while (task.status === 'pending' || task.status === 'processing') {
    await new Promise(resolve => setTimeout(resolve, 1000))

    const progressData = await http.get<AnimationTask>(
      `/animation/export/${task.task_id}`,
      { skipProgress: true },
    )
    task.status = progressData.status
    task.progress = progressData.progress
    task.download_url = progressData.download_url
    task.error = progressData.error

    onProgress(progressData.progress)
  }

  if (task.status === 'failed') {
    throw new Error(task.error || 'Export failed')
  }

  if (task.status === 'cancelled') {
    throw new Error('导出已取消')
  }

  if (!task.download_url) {
    throw new Error('Export completed but no download URL provided')
  }

  return task.download_url
}

/**
 * 取消后端导出任务
 */
export async function cancelBackendExport(taskId: string): Promise<void> {
  await http.delete(`/animation/export/${taskId}`, { skipProgress: true })
}

/**
 * 下载文件
 *
 * 通过 fetch → Blob → 同源 URL 触发下载：
 * - 后端返回的相对路径（如 /exports/...）需拼上后端 origin，
 *   否则经前端 dev server 会被 SPA fallback 返回 HTML
 * - 跨域 URL 的 download 属性无效，且异步回调中的新标签打开会被弹窗拦截，
 *   blob 方案同源且无需新窗口
 */
export async function downloadFile(url: string, filename: string) {
  const fullUrl = url.startsWith('/') ? getBackendOrigin() + url : url
  const response = await fetch(fullUrl)
  if (!response.ok) {
    throw new Error(`下载失败: HTTP ${response.status}`)
  }
  const blob = await response.blob()
  const blobUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = blobUrl
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(blobUrl)
}

/**
 * 生成导出文件名
 */
export function generateExportFilename(trackId: number): string {
  const date = new Date()
  const dateStr = date.toISOString().slice(0, 10).replace(/T/, '-')
  return `track_${trackId}_animation_${dateStr}.webm`
}

/**
 * 检查导出前置条件
 */
export function checkExportPrerequisites(): { canExport: boolean; reason?: string } {
  const isBrowserSupported = checkMediaRecorderSupport()

  if (!isBrowserSupported) {
    return {
      canExport: false,
      reason: '浏览器不支持 MediaRecorder',
    }
  }

  return { canExport: true }
}

/**
 * 检查是否需要后端导出（百度地图、Google 地图需要）
 */
export function requiresBackendExport(mapProvider: string): boolean {
  return ['baidu', 'baidu_gl', 'baidu_legacy', 'google'].includes(mapProvider)
}
