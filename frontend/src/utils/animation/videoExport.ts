// frontend/src/utils/animation/videoExport.ts

import type { Resolution, ExportConfig } from '@/types/animation'

interface AnimationTask {
  task_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
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
 * 使用后端 Playwright 导出（推荐用于百度地图）
 */
export async function exportWithPlaywright(
  trackId: number,
  config: ExportConfig,
  onProgress: (progress: number) => void
): Promise<string> {
  const { resolution, fps, showHUD, speed } = config

  // 调用后端 API 启动导出
  const response = await fetch(`/api/v1/animation/export?track_id=${trackId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      resolution,
      fps,
      show_hud: showHUD,
      speed,
    }),
  })

  if (!response.ok) {
    const error = await response.text()
    throw new Error(error || 'Failed to export animation')
  }

  const task: AnimationTask = await response.json()

  // 轮询导出进度
  while (task.status === 'pending' || task.status === 'processing') {
    await new Promise(resolve => setTimeout(resolve, 1000))

    const progressResponse = await fetch(`/api/v1/animation/export/${task.task_id}`)
    if (!progressResponse.ok) {
      throw new Error('Failed to get export progress')
    }

    const progressData: AnimationTask = await progressResponse.json()
    task.status = progressData.status
    task.progress = progressData.progress
    task.download_url = progressData.download_url
    task.error = progressData.error

    onProgress(progressData.progress)
  }

  if (task.status === 'failed') {
    throw new Error(task.error || 'Export failed')
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
  const response = await fetch(`/api/v1/animation/export/${taskId}`, {
    method: 'DELETE',
  })

  if (!response.ok) {
    throw new Error('Failed to cancel export')
  }
}

/**
 * 下载文件
 */
export function downloadFile(url: string, filename: string) {
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.target = '_blank'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

/**
 * 生成导出文件名
 */
export function generateExportFilename(trackId: number, format: string): string {
  const date = new Date()
  const dateStr = date.toISOString().slice(0, 10).replace(/T/, '-')
  return `track_${trackId}_animation_${dateStr}.${format}`
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
 * 检查是否需要后端导出（百度地图需要）
 */
export function requiresBackendExport(mapProvider: string): boolean {
  return ['baidu', 'baidu_gl', 'baidu_legacy'].includes(mapProvider)
}
