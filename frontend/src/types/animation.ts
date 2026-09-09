// frontend/src/types/animation.ts

import type { TrackPoint } from './track'

/**
 * 动画配置
 */
export interface AnimationConfig {
  trackId: number
  trackPoints: TrackPoint[]
  startTime: string      // ISO 8601
  endTime: string        // ISO 8601
  duration: number       // 毫秒
}

/**
 * 播放状态
 */
export interface PlaybackState {
  isPlaying: boolean
  currentTime: number    // 毫秒
  playbackSpeed: number  // 0.25, 0.5, 1, 2, 4, 8, 16
  cameraMode: CameraMode
  orientationMode: OrientationMode
  showInfoPanel: boolean
  markerStyle: MarkerStyle
}

/**
 * 画面模式
 */
export type CameraMode = 'full' | 'fixed-center'

/**
 * 朝向模式
 */
export type OrientationMode = 'north-up' | 'track-up'

/**
 * 标记样式
 */
export type MarkerStyle = 'arrow' | 'car' | 'person'

/**
 * 导出对话框选项（视图状态由调用方补充为完整 ExportConfig）
 */
export interface ExportOptions {
  resolution: Resolution
  showHUD: boolean
  speed: number
}

/**
 * 导出配置
 */
export interface ExportConfig {
  resolution: Resolution
  showHUD: boolean
  speed: number  // 导出倍速，1.0 = 原速
  // 视图状态（导出画面与用户点击导出时一致）
  startTime: number  // 起点（播放位置，毫秒）
  cameraMode: CameraMode
  orientationMode: OrientationMode
  markerStyle: MarkerStyle
  showInfoPanel: boolean
  layerId?: string  // 地图图层（含卫星图等变体）
  zoom?: number | null  // fixed-center 模式下用户手动缩放
  center?: { lat: number; lng: number } | null
  viewportWidth?: number  // 详情页地图画幅宽度（像素），用于导出画幅变化时的 zoom 修正
  viewportHeight?: number  // 详情页地图画幅高度（像素）
}

/**
 * 分辨率选项
 */
export type Resolution = '720p' | '1080p' | '4k'

/**
 * 分辨率对应的尺寸
 */
export const RESOLUTION_DIMENSIONS: Record<Resolution, { width: number; height: number }> = {
  '720p': { width: 1280, height: 720 },
  '1080p': { width: 1920, height: 1080 },
  '4k': { width: 3840, height: 2160 },
} as const

/**
 * 移动标记位置
 */
export interface MarkerPosition {
  lat: number
  lng: number
  bearing: number  // 方位角 [0, 360)
  speed: number | null
  elevation: number | null
  time: string | null
}

/**
 * 动画偏好设置（本地存储）
 */
export interface AnimationPreferences {
  defaultSpeed: number
  showInfoPanel: boolean
  markerStyle: MarkerStyle
  defaultCameraMode: CameraMode
  defaultOrientationMode: OrientationMode
  exportResolution: Resolution
  exportShowHUD: boolean
}

/**
 * 默认偏好设置
 */
export const DEFAULT_PREFERENCES: AnimationPreferences = {
  defaultSpeed: 1,
  showInfoPanel: true,
  markerStyle: 'arrow',
  defaultCameraMode: 'full',
  defaultOrientationMode: 'north-up',
  exportResolution: '1080p',
  exportShowHUD: true,
} as const

/**
 * 本地存储键名
 */
export const ANIMATION_STORAGE_KEY = 'vibe-route-animation-prefs'

/**
 * 倍速档位
 */
export const PLAYBACK_SPEEDS = [0.25, 0.5, 1, 2, 4, 8, 16] as const

/**
 * 倍速档位类型
 */
export type PlaybackSpeed = typeof PLAYBACK_SPEEDS[number]
