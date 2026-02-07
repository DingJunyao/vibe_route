/**
 * 海报生成 API
 */
import { http } from './request'

export interface PosterConfig {
  template: string
  width: number
  height: number
  show_watermark: boolean
  map_scale?: number  // 地图缩放百分比，100-200
}

export interface PosterTrackData {
  track_id: number
  name: string
  points: Array<{
    latitude: number
    longitude: number
    latitude_wgs84: number
    longitude_wgs84: number
    latitude_gcj02: number | null
    longitude_gcj02: number | null
    latitude_bd09: number | null
    longitude_bd09: number | null
  }>
  distance: number
  duration: number
  elevation_gain: number
  elevation_loss: number
  start_time: string | null
  end_time: string | null
}

export interface MapBounds {
  min_lat: number
  max_lat: number
  min_lon: number
  max_lon: number
}

export interface PosterGenerateRequest {
  config: PosterConfig
  track: PosterTrackData
  bounds: MapBounds
  provider?: string
}

export interface PosterProvidersResponse {
  providers: Array<{
    id: string
    name: string
    enabled: boolean
  }>
}

/**
 * 生成海报
 */
export async function generatePoster(request: PosterGenerateRequest): Promise<Blob> {
  const params = new URLSearchParams()
  if (request.provider) {
    params.append('provider', request.provider)
  }

  const response = await http.post<Blob>(
    `/poster/generate?${params.toString()}`,
    request,
    {
      responseType: 'blob',
    }
  )
  return response as unknown as Blob
}

/**
 * 获取可用的地图提供商
 */
export async function getPosterProviders(): Promise<PosterProvidersResponse> {
  return http.get('/poster/providers')
}
