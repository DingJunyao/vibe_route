// frontend/src/utils/animation/videoExport.ts

import { http } from '@/api/request'
import { useAnimationStore } from '@/stores/animation'
import { getGlobalViewState } from '@/composables/animation/useAnimationMap'
import { getBackendOrigin } from '@/utils/origin'
import type { ExportConfig, ExportOptions } from '@/types/animation'

interface AnimationTask {
  task_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled' | 'expired'
  progress: number
  download_url?: string
  error?: string
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
    engine: view.engine,
    zoom: view.zoom,
    center: view.center,
    viewportWidth: view.width || undefined,
    viewportHeight: view.height || undefined,
  }
}

/**
 * 提交导出任务：进入后端录屏任务队列后立即返回，
 * 不在当前页面等待与轮询——进度、下载、取消在「录屏任务」页进行
 */
export async function startExportTask(
  trackId: number,
  config: ExportConfig
): Promise<AnimationTask> {
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
    engine,
    zoom,
    center,
    viewportWidth,
    viewportHeight,
  } = config

  // 调用后端 API 启动导出（走统一客户端，自动携带认证头）
  return await http.post<AnimationTask>(
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
      engine: engine ?? null,
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
}

/**
 * 下载任务结果文件
 *
 * 通过 fetch → Blob → 同源 URL 触发下载：
 * - 后端返回的受保护下载路径需拼上后端 origin，
 *   否则经前端 dev server 会被 SPA fallback 返回 HTML
 * - 跨域 URL 的 download 属性无效，且异步回调中的新标签打开会被弹窗拦截，
 *   blob 方案同源且无需新窗口
 */
export async function downloadFile(url: string, filename: string) {
  const fullUrl = url.startsWith('/') ? getBackendOrigin() + url : url
  const token = localStorage.getItem('token')
  const response = await fetch(fullUrl, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  })
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
 * 生成导出文件名（逐帧合成 H.264 MP4）
 */
export function generateExportFilename(trackId: number): string {
  const date = new Date()
  const dateStr = date.toISOString().slice(0, 10).replace(/T/, '-')
  return `track_${trackId}_animation_${dateStr}.mp4`
}
