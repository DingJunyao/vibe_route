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
  bearing: number | null  // 方位角（度），范围 [0, 360)
  province: string | null
  city: string | null
  district: string | null
  road_name: string | null
  road_number: string | null
  province_en: string | null
  city_en: string | null
  district_en: string | null
  road_name_en: string | null
  memo: string | null  // 备注
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

export interface FillProgressItem {
  status: 'idle' | 'filling' | 'completed' | 'failed'
  current: number
  total: number
  percent: number
}

export type AllFillProgressResponse = Record<number, FillProgressItem>

export interface RegionNode {
  id: string
  name: string
  type: 'province' | 'city' | 'district' | 'road'
  road_number: string | null
  has_info: boolean  // 是否有详细信息
  distance: number  // 路径长度（米）
  start_time: string | null
  end_time: string | null
  start_index: number  // 起始点索引
  end_index: number  // 结束点索引
  children: RegionNode[]
}

export interface RegionStats {
  province: number
  city: number
  district: number
  road: number
}

export interface RegionTreeResponse {
  track_id: number
  regions: RegionNode[]
  stats: RegionStats
}

export interface ImportResponse {
  updated: number
  total: number
  matched_by: 'index' | 'time' | 'none'
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

  // 停止填充地理信息
  stopFillGeocoding(trackId: number): Promise<{ message: string; track_id: number }> {
    return http.post(`/tracks/${trackId}/fill-stop`)
  },

  // 获取所有轨迹的填充进度
  getAllFillProgress(): Promise<AllFillProgressResponse> {
    return http.get('/tracks/fill-progress/all')
  },

  // 获取区域树
  getRegions(trackId: number): Promise<RegionTreeResponse> {
    return http.get(`/tracks/${trackId}/regions`)
  },

  // 导出轨迹点
  exportPoints(trackId: number, format: 'csv' | 'xlsx' = 'csv'): string {
    return `/api/tracks/${trackId}/export?format=${format}`
  },

  // 导入轨迹点
  importPoints(trackId: number, file: File, matchMode: 'index' | 'time', timezone: string = 'UTC+8', timeTolerance: number = 1.0): Promise<ImportResponse> {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('match_mode', matchMode)
    formData.append('timezone', timezone)
    formData.append('time_tolerance', String(timeTolerance))
    return http.post(`/tracks/${trackId}/import`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
  },
}
