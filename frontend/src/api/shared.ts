import { http } from './request'
import type { Track, TrackPoint, RegionNode, RegionStats, RegionTreeResponse } from './track'

// 分享相关类型定义
export interface SharedTrackResponse {
  track: Track
  points: TrackPoint[]
}

export interface SharedConfigResponse {
  map_provider: string | null
  map_layers: Record<string, any> | null
}

export interface SharedTrackGeoJSON {
  type: 'FeatureCollection'
  features: Array<{
    type: 'Feature'
    properties: {
      index: number
      elevation: number | null
      time: string | null
    }
    geometry: {
      type: 'Point'
      coordinates: [number, number]  // [longitude, latitude]
    }
  }>
}

// 分享页面 API（公开访问，无需登录）
export const sharedApi = {
  // 获取分享的轨迹数据
  getSharedTrack(token: string): Promise<SharedTrackResponse> {
    return http.get(`/shared/${token}`, { skipAuth: true })
  },

  // 获取分享者的地图配置
  getSharedConfig(token: string): Promise<SharedConfigResponse> {
    return http.get(`/shared/${token}/config`, { skipAuth: true })
  },

  // 获取分享轨迹的轨迹点（GeoJSON 格式）
  getSharedTrackPoints(token: string): Promise<SharedTrackGeoJSON> {
    return http.get(`/shared/${token}/points`, { skipAuth: true })
  },

  // 获取分享轨迹的经过区域
  getSharedRegions(token: string): Promise<RegionTreeResponse> {
    return http.get(`/shared/${token}/regions`, { skipAuth: true })
  },

  // 生成完整的分享 URL
  getShareUrl(token: string, embed = false): string {
    const baseUrl = window.location.origin
    return `${baseUrl}/s/${token}${embed ? '?embed=true' : ''}`
  },

  // 生成嵌入代码
  getEmbedCode(token: string, width = '100%', height = '520'): string {
    const url = this.getShareUrl(token, true)
    return `<iframe src="${url}" width="${width}" height="${height}" frameborder="0" scrolling="no" allowfullscreen allow="fullscreen"></iframe>`
  },
}
