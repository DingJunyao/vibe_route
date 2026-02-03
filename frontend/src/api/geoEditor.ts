import { http } from './request'

// 类型定义
export interface TrackPointGeoData {
  point_index: number
  time: string | null
  created_at: string | null
  latitude: number        // WGS84 纬度
  longitude: number       // WGS84 经度
  latitude_gcj02: number | null   // GCJ02 纬度（高德、腾讯）
  longitude_gcj02: number | null  // GCJ02 经度
  latitude_bd09: number | null   // BD09 纬度（百度）
  longitude_bd09: number | null  // BD09 经度
  elevation: number | null  // 海拔（米）
  speed: number | null  // 速度（m/s）
  province: string | null
  city: string | null
  district: string | null
  province_en: string | null
  city_en: string | null
  district_en: string | null
  road_number: string | null
  road_name: string | null
  road_name_en: string | null
}

export interface GeoEditorData {
  track_id: number
  name: string
  original_crs: string
  total_duration: number  // 毫秒
  point_count: number
  points: TrackPointGeoData[]
}

export interface GeoSegmentUpdate {
  track_type: 'province' | 'city' | 'district' | 'road_number' | 'road_name'
  start_index: number
  end_index: number
  value: string | null
  value_en: string | null
}

export interface GeoSegmentsUpdateRequest {
  segments: GeoSegmentUpdate[]
}

export interface GeoUpdateResponse {
  track_id: number
  updated_count: number
  segments_count: number
}

// API 方法
export const geoEditorApi = {
  // 获取编辑器数据
  getEditorData(trackId: number): Promise<GeoEditorData> {
    return http.get(`/geo-editor/tracks/${trackId}`)
  },

  // 批量更新段落
  updateSegments(trackId: number, request: GeoSegmentsUpdateRequest): Promise<GeoUpdateResponse> {
    return http.put(`/geo-editor/tracks/${trackId}/segments`, request)
  },
}
