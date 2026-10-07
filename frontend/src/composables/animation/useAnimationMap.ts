// frontend/src/composables/animation/useAnimationMap.ts

import type { MarkerPosition, MarkerStyle } from '@/types/animation'

// 日志收集器（方便移动端复制）
const animationLogs: string[] = []
const MAX_LOGS = 200  //最多保留 200 条日志

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

// 调试按钮功能（已注释）
// if (typeof window !== 'undefined') {
//   // ... 调试按钮代码已注释
// }

/**
 * 动画地图适配接口
 */
export interface AnimationMapAdapter {
  // 设置双色轨迹
  setPassedSegment(start: number, end: number): void

  // 设置移动标记
  setMarkerPosition(position: MarkerPosition, style: MarkerStyle): void

  // 设置地图中心（targetZoom 提供时同步校正缩放，仅在与当前 zoom 不同时生效）
  setCameraToMarker(position: MarkerPosition, targetZoom?: number): void

  // 设置地图旋转
  setMapRotation(bearing: number): void

  // 获取当前旋转角度
  getMapRotation(): number

  // 设置动画播放状态（避免双色轨迹闪烁）
  setAnimationPlaying(playing: boolean): void

  // 调整地图视野以适应整条轨迹：四周各留 10% 空间（bottomPaddingPx 为额外底部像素）
  fitTrackWithPadding?(bottomPaddingPx: number): void
}

// 全局适配器（真正的单例）
let globalAdapter: AnimationMapAdapter | null = null
let currentRotation = 0

// 全局视图状态提供者（UniversalMap 注册，导出动画时收集地图状态）
export interface MapViewState {
  center: { lat: number; lng: number } | null
  zoom: number | null
  layerId: string
  engine?: 'sdk' | 'leaflet'  // 当前底图使用的引擎（SDK 或 Leaflet 瓦片）
  width: number  // 地图画幅宽度（像素），用于导出画幅变化时的 zoom 修正
  height: number  // 地图画幅高度（像素）
}

let globalViewStateProvider: (() => MapViewState) | null = null

/**
 * 注册视图状态提供者（由 UniversalMap 调用）
 */
export function registerViewStateProvider(provider: () => MapViewState) {
  globalViewStateProvider = provider
}

/**
 * 获取当前地图视图状态（未注册时返回空状态）
 */
export function getGlobalViewState(): MapViewState {
  return globalViewStateProvider?.() ?? { center: null, zoom: null, layerId: '', width: 0, height: 0 }
}

// 最近一次直接应用的目标朝向（避免每帧重复设置相同角度）
let lastAppliedRotation: number | null = null

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

  // 设置地图中心（targetZoom 提供时同步校正缩放）
  function setCameraToMarker(position: MarkerPosition, targetZoom?: number) {
    if (globalAdapter) {
      // 适配器已注册，直接调用
      globalAdapter.setCameraToMarker(position, targetZoom)
    } else {
      // 适配器未注册，加入队列
      addLog('useAnimationMap', 'Adapter not registered, queuing setCameraToMarker')
      cameraPositionQueue.push({ position })
    }
  }

  // 直接设置地图旋转（无过渡动画，播放中每帧调用、模式切换时一次性调用）
  // bearing 语义：应指向画面正上方的罗盘方位角（0 = 正北朝上）
  function applyMapRotation(targetBearing: number) {
    if (!globalAdapter) {
      lastAppliedRotation = null
      return
    }
    const normalized = normalizeAngle(targetBearing)
    if (lastAppliedRotation !== null && Math.abs(calculateShortestRotation(lastAppliedRotation, normalized)) < 0.01) {
      return
    }
    globalAdapter.setMapRotation(normalized)
    lastAppliedRotation = normalized
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
    applyMapRotation,
    setAnimationPlaying,
    fitTrackWithPadding,
  }
}
