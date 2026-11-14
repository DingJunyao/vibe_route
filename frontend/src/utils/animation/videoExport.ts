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
 * 录屏产物可达数 GB：fetch → Blob 会把整包压进内存，
 * 且在响应体传输完成前 fetch 一直 pending、无任何进度反馈，观感像挂死。
 * 改走浏览器原生下载：先向后端换取任务作用域的短时下载令牌（POST download-token），
 * 再以 <a download> 触发系统下载管理器流式落盘——有原生进度、可暂停续传。
 * 令牌放 URL 查询参数是因为 <a> 导航无法携带 Bearer 头。
 */
export async function downloadFile(url: string, filename: string) {
  const fullUrl = url.startsWith('/') ? getBackendOrigin() + url : url
  const token = localStorage.getItem('token')
  const tokenRes = await fetch(fullUrl.replace(/\/download$/, '/download-token'), {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  })
  if (!tokenRes.ok) {
    throw new Error(`获取下载凭证失败: HTTP ${tokenRes.status}`)
  }
  const { download_token: downloadToken } = await tokenRes.json()

  const link = document.createElement('a')
  link.href = `${fullUrl}?download_token=${encodeURIComponent(downloadToken)}`
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
}

/**
 * 生成导出文件名（逐帧合成 H.264 MP4）
 */
export function generateExportFilename(trackId: number): string {
  const date = new Date()
  const dateStr = date.toISOString().slice(0, 10).replace(/T/, '-')
  return `track_${trackId}_animation_${dateStr}.mp4`
}
