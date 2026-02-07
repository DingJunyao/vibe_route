/**
 * 海报相关类型定义
 */

/** 海报模板类型 */
export type PosterTemplate = 'simple' | 'rich' | 'geo' | 'minimal'

/** 海报尺寸预设 */
export interface PosterSizePreset {
  name: string
  width: number
  height: number
  scale: number
}

/** 海报尺寸预设枚举 */
export const POSTER_SIZE_PRESETS: Record<string, PosterSizePreset> = {
  portrait_1080: { name: '竖版 1080P', width: 1080, height: 1920, scale: 2 },
  portrait_4k: { name: '竖版 4K', width: 2160, height: 3840, scale: 4 },
  landscape_1080: { name: '横版 1080P', width: 1920, height: 1080, scale: 2 },
  landscape_4k: { name: '横版 4K', width: 3840, height: 2160, scale: 4 },
  custom: { name: '自定义', width: 1080, height: 1920, scale: 2 },
}

/** 海报配置 */
export interface PosterConfig {
  template: PosterTemplate
  sizePreset: string
  customWidth?: number
  customHeight?: number
  showWatermark: boolean
  infoLevel: 'basic' | 'sports' | 'geo'
}

/** 海报数据（从轨迹数据派生） */
export interface PosterData {
  name: string
  date: string
  startTime: string
  endTime: string
  distance: number
  duration: number
  elevationGain: number
  elevationLoss: number
  avgSpeed?: number
  maxSpeed?: number
  regions?: string[]
  mapImage?: string  // Base64 格式的地图截图
}

/** 海报生成进度 */
export interface PosterProgress {
  stage: 'idle' | 'capturing' | 'drawing' | 'done' | 'error'
  message: string
  percent: number
}
