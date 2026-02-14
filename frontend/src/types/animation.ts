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
 * 导出配置
 */
export interface ExportConfig {
  resolution: Resolution
  fps: 30 | 60
  showHUD: boolean
  format: 'webm' | 'mp4'
  speed: number  // 导出倍速，1.0 = 原速
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
  exportFPS: 30 | 60
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
  exportFPS: 30,
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
