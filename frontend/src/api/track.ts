import { http } from './request'

// 类型定义
export interface Track {
  id: number
  user_id: number
  name: string
  description: string | null
  original_filename: string
  original_crs: string
  distance: number
  duration: number
  elevation_gain: number
  elevation_loss: number
  start_time: string | null
  end_time: string | null
  has_area_info: boolean
  has_road_info: boolean
  created_at: string
  updated_at: string
}

export interface TrackPoint {
  id: number
  point_index: number
  time: string | null
  latitude: number
  longitude: number
  latitude_wgs84: number
  longitude_wgs84: number
  latitude_gcj02: number | null
  longitude_gcj02: number | null
  latitude_bd09: number | null
  longitude_bd09: number | null
  elevation: number | null
  speed: number | null
  province: string | null
  city: string | null
  district: string | null
  road_name: string | null
  road_number: string | null
}

export interface TrackListResponse {
  total: number
  page: number
  page_size: number
  items: Track[]
}

export interface TrackStats {
  total_tracks: number
  total_distance: number
  total_duration: number
  total_elevation_gain: number
}

export interface TrackPointsResponse {
  track_id: number
  crs: string
  count: number
  points: TrackPoint[]
}

export interface FillProgressResponse {
  track_id: number
  progress: {
    current: number
    total: number
    status: 'idle' | 'filling' | 'completed' | 'error'
  }
}

// API 方法
export const trackApi = {
  // 上传轨迹
  upload(data: {
    file: File
    name: string
    description?: string
    original_crs?: string
    convert_to?: string
    fill_geocoding?: boolean
  }): Promise<Track> {
    const formData = new FormData()
    formData.append('file', data.file)
    formData.append('name', data.name)
    if (data.description) formData.append('description', data.description)
    if (data.original_crs) formData.append('original_crs', data.original_crs)
    if (data.convert_to) formData.append('convert_to', data.convert_to)
    if (data.fill_geocoding !== undefined)
      formData.append('fill_geocoding', String(data.fill_geocoding))

    return http.post('/tracks/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
  },

  // 获取轨迹列表
  getList(params?: {
    page?: number
    page_size?: number
    search?: string
    sort_by?: string
    sort_order?: string
  }): Promise<TrackListResponse> {
    return http.get('/tracks', { params })
  },

  // 获取轨迹统计
  getStats(): Promise<TrackStats> {
    return http.get('/tracks/stats')
  },

  // 获取轨迹详情
  getDetail(trackId: number): Promise<Track> {
    return http.get(`/tracks/${trackId}`)
  },

  // 更新轨迹
  update(trackId: number, data: { name?: string; description?: string }): Promise<Track> {
    return http.patch(`/tracks/${trackId}`, data)
  },

  // 删除轨迹
  delete(trackId: number): Promise<{ message: string }> {
    return http.delete(`/tracks/${trackId}`)
  },

  // 获取轨迹点
  getPoints(trackId: number, crs: string = 'wgs84'): Promise<TrackPointsResponse> {
    return http.get(`/tracks/${trackId}/points`, { params: { crs } })
  },

  // 下载轨迹
  download(trackId: number, crs: string = 'original'): string {
    return `/api/tracks/${trackId}/download?crs=${crs}`
  },

  // 填充地理信息
  fillGeocoding(trackId: number): Promise<{ message: string; track_id: number; progress?: any }> {
    return http.post(`/tracks/${trackId}/fill-geocoding`)
  },

  // 获取填充进度
  getFillProgress(trackId: number): Promise<FillProgressResponse> {
    return http.get(`/tracks/${trackId}/fill-progress`)
  },
}
