import { http } from './request'

/**
 * 控制点手柄偏移量
 */
export interface ControlPointHandle {
  dx: number  // 经度偏移
  dy: number  // 纬度偏移
}

/**
 * 贝塞尔曲线控制点
 */
export interface ControlPoint {
  lng: number
  lat: number
  inHandle: ControlPointHandle
  outHandle: ControlPointHandle
  handlesLocked: boolean
}

/**
 * 可插值区段
 */
export interface AvailableSegment {
  start_index: number
  end_index: number
  interval_seconds: number
  start_time: string | null
  end_time: string | null
}

/**
 * 插值点数据
 */
export interface InterpolatedPoint {
  point_index: number
  time: string
  latitude: number
  longitude: number
  latitude_gcj02: number
  longitude_gcj02: number
  latitude_bd09: number
  longitude_bd09: number
  speed: number
  course: number
  elevation: number | null
}

/**
 * 创建插值请求
 */
export interface InterpolationCreateRequest {
  start_point_index: number
  end_point_index: number
  control_points: ControlPoint[]
  interpolation_interval_seconds: number
  algorithm: string
}

/**
 * 插值预览请求
 */
export interface InterpolationPreviewRequest {
  track_id: number
  start_point_index: number
  end_point_index: number
  control_points: ControlPoint[]
  interpolation_interval_seconds: number
}

/**
 * 插值响应
 */
export interface InterpolationResponse {
  id: number
  track_id: number
  start_point_index: number
  end_point_index: number
  point_count: number
  control_points: ControlPoint[]
  interpolation_interval_seconds: number
  algorithm: string
  created_at: string
}

/**
 * 插值预览响应
 */
export interface InterpolationPreviewResponse {
  points: InterpolatedPoint[]
  total_count: number
  start_time: string
  end_time: string
}

/**
 * 插值 API 客户端
 */
export const interpolationApi = {
  /**
   * 获取可插值区段列表
   */
  getAvailableSegments(trackId: number, minInterval: number = 3.0): Promise<AvailableSegment[]> {
    return http.get(`/interpolation/tracks/${trackId}/available-segments`, {
      params: { min_interval: minInterval }
    })
  },

  /**
   * 预览插值结果（不保存）
   */
  preview(request: InterpolationPreviewRequest): Promise<InterpolationPreviewResponse> {
    return http.post('/interpolation/preview', request)
  },

  /**
   * 创建插值配置并插入插值点
   */
  create(trackId: number, request: InterpolationCreateRequest): Promise<InterpolationResponse> {
    return http.post(`/interpolation/tracks/${trackId}/interpolations`, request)
  },

  /**
   * 获取轨迹的所有插值配置
   */
  getTrackInterpolations(trackId: number): Promise<InterpolationResponse[]> {
    return http.get(`/interpolation/tracks/${trackId}/interpolations`)
  },

  /**
   * 删除插值配置及关联的插值点
   */
  delete(interpolationId: number): Promise<void> {
    return http.delete(`/interpolation/interpolations/${interpolationId}`)
  }
}
