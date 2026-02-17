// frontend/src/composables/animation/useAnimationMap.ts

import type { MarkerPosition, MarkerStyle } from '@/types/animation'

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

/**
 * 动画地图 composable
 */
export function useAnimationMap() {
  // 注册适配器
  function registerAdapter(adapter: AnimationMapAdapter) {
    globalAdapter = adapter
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
    globalAdapter?.setMarkerPosition(position, style)
  }

  // 设置地图中心
  function setCameraToMarker(position: MarkerPosition) {
    globalAdapter?.setCameraToMarker(position)
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
