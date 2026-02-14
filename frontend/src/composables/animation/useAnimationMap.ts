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
    console.log('[AnimationMap] Adapter registered:', adapter)
  }

  // 取消注册
  function unregisterAdapter() {
    globalAdapter = null
    console.log('[AnimationMap] Adapter unregistered')
  }

  // 设置双色轨迹
  function setPassedSegment(start: number, end: number) {
    console.log('[AnimationMap] setPassedSegment:', start, '->', end)
    globalAdapter?.setPassedSegment(start, end)
  }

  // 设置移动标记
  function setMarkerPosition(position: MarkerPosition, style: MarkerStyle = 'arrow') {
    console.log('[AnimationMap] setMarkerPosition:', position, 'style:', style)
    globalAdapter?.setMarkerPosition(position, style)
  }

  // 设置地图中心
  function setCameraToMarker(position: MarkerPosition) {
    console.log('[AnimationMap] setCameraToMarker:', position)
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
  }
}
