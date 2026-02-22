// frontend/src/composables/animation/useAnimationMap.ts

import type { MarkerPosition, MarkerStyle } from '@/types/animation'

// 日志收集器（方便移动端复制）
const animationLogs: string[] = []
const MAX_LOGS = 200  // 最多保留 200 条日志

function addLog(category: string, message: string, data?: any) {
  const timestamp = new Date().toLocaleTimeString('zh-CN')
  const logEntry = `[${timestamp}][${category}] ${message}${data ? ' ' + JSON.stringify(data) : ''}`
  animationLogs.push(logEntry)
  if (animationLogs.length > MAX_LOGS) {
    animationLogs.shift()
  }
  // 同时输出到控制台
  console.log(`[${category}] ${message}`, data || '')
}

// 暴露给全局，方便调试
;(window as any).__animationLogs = animationLogs
;(window as any).__copyAnimationLogs = () => {
  const logs = animationLogs.join('\n')
  console.log('=== ANIMATION LOGS ===')
  console.log(logs)
  console.log('=== END OF LOGS ===')
  return logs
}

// 添加一个按钮到页面，方便一键复制日志
if (typeof window !== 'undefined') {
  const createLogButtons = () => {
    // 先移除已存在的按钮
    const existing = document.getElementById('animation-log-buttons')
    if (existing) {
      existing.remove()
    }

    const container = document.createElement('div')
    container.id = 'animation-log-buttons'
    container.style.cssText = `
      position: fixed !important;
      bottom: 10px !important;
      left: 10px !important;
      z-index: 2147483647 !important;
      display: flex !important;
      flex-direction: row !important;
      gap: 8px !important;
      pointer-events: auto !important;
      touch-action: manipulation !important;
    `

    // 复制日志按钮
    const copyButton = document.createElement('button')
    copyButton.textContent = '📋 复制日志'
    copyButton.style.cssText = `
      padding: 12px 20px !important;
      background: rgba(0, 0, 0, 0.9) !important;
      color: white !important;
      border: 2px solid rgba(255, 255, 255, 0.5) !important;
      border-radius: 8px !important;
      font-size: 16px !important;
      font-weight: 600 !important;
      cursor: pointer !important;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5) !important;
      min-width: 120px !important;
      min-height: 50px !important;
      user-select: none !important;
      -webkit-user-select: none !important;
    `

    // 下载日志按钮
    const downloadButton = document.createElement('button')
    downloadButton.textContent = '⬇️ 下载'
    downloadButton.style.cssText = `
      padding: 12px 20px !important;
      background: rgba(22, 163, 74, 0.9) !important;
      color: white !important;
      border: 2px solid rgba(255, 255, 255, 0.5) !important;
      border-radius: 8px !important;
      font-size: 16px !important;
      font-weight: 600 !important;
      cursor: pointer !important;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5) !important;
      min-width: 120px !important;
      min-height: 50px !important;
      user-select: none !important;
      -webkit-user-select: none !important;
    `

    // 复制功能
    const doCopy = () => {
      const animationLogs = (window as any).__animationLogs || []
      const tencentLogs = (window as any).__tencentMapLogs || []
      const allLogs = [
        '=== ANIMATION LOGS (' + new Date().toLocaleString('zh-CN') + ') ===',
        ...animationLogs,
        '=== TENCENT MAP LOGS ===',
        ...tencentLogs,
        '=== LOG COUNT: ' + (animationLogs.length + tencentLogs.length) + ' ===',
        '=== END OF LOGS ==='
      ].join('\n')

      console.log('=== COPYING LOGS ===')
      console.log(allLogs)
      console.log('=== END OF LOGS ===')

      // 尝试使用 clipboard API
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(allLogs).then(() => {
          copyButton.textContent = '✅ 已复制'
          copyButton.style.background = 'rgba(22, 163, 74, 0.9) !important'
          setTimeout(() => {
            copyButton.textContent = '📋 复制日志'
            copyButton.style.background = 'rgba(0, 0, 0, 0.9) !important'
          }, 2000)
        }).catch(() => {
          // Clipboard API 失败，使用备用方法
          fallbackCopy(allLogs)
        })
      } else {
        // Clipboard API 不可用，使用备用方法
        fallbackCopy(allLogs)
      }
    }

    // 备用复制方法（创建 textarea）
    const fallbackCopy = (text: string) => {
      const textarea = document.createElement('textarea')
      textarea.value = text
      textarea.style.cssText = `
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        width: 100% !important;
        height: 100% !important;
        z-index: 2147483646 !important;
        opacity: 0 !important;
      `
      document.body.appendChild(textarea)
      textarea.select()
      textarea.setSelectionRange(0, text.length)
      document.execCommand('copy')
      document.body.removeChild(textarea)

      copyButton.textContent = '✅ 已复制'
      copyButton.style.background = 'rgba(22, 163, 74, 0.9) !important'
      setTimeout(() => {
        copyButton.textContent = '📋 复制日志'
        copyButton.style.background = 'rgba(0, 0, 0, 0.9) !important'
      }, 2000)
    }

    // 下载功能
    const doDownload = () => {
      const animationLogs = (window as any).__animationLogs || []
      const tencentLogs = (window as any).__tencentMapLogs || []
      const allLogs = [
        '=== ANIMATION LOGS (' + new Date().toLocaleString('zh-CN') + ') ===',
        ...animationLogs,
        '=== TENCENT MAP LOGS ===',
        ...tencentLogs,
        '=== LOG COUNT: ' + (animationLogs.length + tencentLogs.length) + ' ===',
        '=== END OF LOGS ==='
      ].join('\n')

      const blob = new Blob([allLogs], { type: 'text/plain;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `animation-logs-${Date.now()}.txt`
      a.style.display = 'none'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)

      downloadButton.textContent = '✅ 已下载'
      setTimeout(() => {
        downloadButton.textContent = '⬇️ 下载'
      }, 2000)
    }

    // 添加点击事件（支持 touch 和 mouse）
    const addClick = (btn: HTMLButtonElement, handler: () => void) => {
      btn.addEventListener('click', handler)
      btn.addEventListener('touchend', (e) => {
        e.preventDefault()
        handler()
      })
    }

    addClick(copyButton, doCopy)
    addClick(downloadButton, doDownload)

    container.appendChild(copyButton)
    container.appendChild(downloadButton)

    // 确保在 document.body 上
    document.body.appendChild(container)

    // 添加样式
    const style = document.createElement('style')
    style.textContent = `
      #animation-log-buttons button:active {
        transform: scale(0.95) !important;
        opacity: 0.8 !important;
      }
    `
    document.head.appendChild(style)

    console.log('[AnimationLogs] Log buttons created successfully')
  }

  // 在 DOM 加载完成后创建按钮
  if (document.readyState === 'loading') {
    window.addEventListener('DOMContentLoaded', createLogButtons)
  } else {
    // DOM 已加载，立即创建
    createLogButtons()
  }

  // 页面完全加载后再次尝试创建按钮
  window.addEventListener('load', () => {
    setTimeout(createLogButtons, 100)
  })

  // 添加全局快捷键
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'L') {
      e.preventDefault()
      const copyBtn = document.querySelector('#animation-log-buttons button:first-child') as HTMLButtonElement
      if (copyBtn) {
        copyBtn.click()
      }
    }
  })
}

/**
 * 动画地图适配接口
 */
export interface AnimationMapAdapter {
  // 设置双色轨迹
  setPassedSegment(start: number, end: number): void

  // 设置移动标记
  setMarkerPosition(position: MarkerPosition, style: MarkerStyle): void

  // 设置地图中心
  setCameraToMarker(position: MarkerPosition): void

  // 设置地图旋转
  setMapRotation(bearing: number): void

  // 获取当前旋转角度
  getMapRotation(): number

  // 设置动画播放状态（避免双色轨迹闪烁）
  setAnimationPlaying(playing: boolean): void

  // 调整地图视野以适应轨迹（添加底部 padding）
  fitTrackWithPadding?(bottomPaddingPx: number): void
}

// 全局适配器（真正的单例）
let globalAdapter: AnimationMapAdapter | null = null
let currentRotation = 0

// 等待队列（在适配器注册之前存储调用）
let markerPositionQueue: Array<{ position: MarkerPosition; style: MarkerStyle }> = []
let cameraPositionQueue: Array<{ position: MarkerPosition }> = []

/**
 * 动画地图 composable
 */
export function useAnimationMap() {
  // 注册适配器
  function registerAdapter(adapter: AnimationMapAdapter) {
    addLog('useAnimationMap', 'Registering adapter', { hasAdapter: !!adapter })
    globalAdapter = adapter
    addLog('useAnimationMap', 'Adapter registered', { globalAdapterExists: !!globalAdapter })

    // 处理队列中的标记位置调用
    if (markerPositionQueue.length > 0) {
      addLog('useAnimationMap', 'Processing marker position queue', { size: markerPositionQueue.length })
      for (const { position, style } of markerPositionQueue) {
        adapter.setMarkerPosition(position, style)
      }
      markerPositionQueue = []
    }

    // 处理队列中的相机位置调用
    if (cameraPositionQueue.length > 0) {
      addLog('useAnimationMap', 'Processing camera position queue', { size: cameraPositionQueue.length })
      for (const { position } of cameraPositionQueue) {
        adapter.setCameraToMarker(position)
      }
      cameraPositionQueue = []
    }
  }

  // 取消注册
  function unregisterAdapter() {
    globalAdapter = null
  }

  // 设置双色轨迹
  function setPassedSegment(start: number, end: number) {
    globalAdapter?.setPassedSegment(start, end)
  }

  // 设置移动标记
  function setMarkerPosition(position: MarkerPosition, style: MarkerStyle = 'arrow') {
    if (globalAdapter) {
      // 适配器已注册，直接调用
      globalAdapter.setMarkerPosition(position, style)
    } else {
      // 适配器未注册，加入队列
      addLog('useAnimationMap', 'Adapter not registered, queuing setMarkerPosition')
      markerPositionQueue.push({ position, style })
    }
  }

  // 设置地图中心
  function setCameraToMarker(position: MarkerPosition) {
    if (globalAdapter) {
      // 适配器已注册，直接调用
      globalAdapter.setCameraToMarker(position)
    } else {
      // 适配器未注册，加入队列
      addLog('useAnimationMap', 'Adapter not registered, queuing setCameraToMarker')
      cameraPositionQueue.push({ position })
    }
  }

  // 设置地图旋转（平滑过渡）
  function setMapRotation(targetBearing: number) {
    if (!globalAdapter) return

    const current = globalAdapter.getMapRotation()
    const delta = calculateShortestRotation(current, targetBearing)

    // 平滑过渡（分5步完成）
    const steps = 5
    const stepDelta = delta / steps
    let currentStep = 0

    function animate() {
      if (currentStep < steps) {
        const newRotation = current + stepDelta * (currentStep + 1)
        globalAdapter.setMapRotation(normalizeAngle(newRotation))
        currentStep++
        requestAnimationFrame(animate)
      }
    }

    animate()
  }

  // 设置动画播放状态
  function setAnimationPlaying(playing: boolean) {
    globalAdapter?.setAnimationPlaying(playing)
  }

  // 调整地图视野以适应轨迹（添加底部 padding）
  function fitTrackWithPadding(bottomPaddingPx: number) {
    globalAdapter?.fitTrackWithPadding?.(bottomPaddingPx)
  }

  // 辅助函数
  function calculateShortestRotation(from: number, to: number): number {
    let delta = to - from
    while (delta > 180) delta -= 360
    while (delta < -180) delta += 360
    return delta
  }

  function normalizeAngle(angle: number): number {
    let normalized = angle % 360
    if (normalized < 0) normalized += 360
    return normalized
  }

  return {
    globalAdapter,
    currentRotation,
    registerAdapter,
    unregisterAdapter,
    setPassedSegment,
    setMarkerPosition,
    setCameraToMarker,
    setMapRotation,
    setAnimationPlaying,
    fitTrackWithPadding,
  }
}
