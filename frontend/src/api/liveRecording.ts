import { http } from './request'

// 类型定义
export interface LiveRecording {
  id: number
  name: string
  description: string | null
  token: string
  status: 'active' | 'ended'
  track_count: number
  last_upload_at: string | null
  upload_url: string
  created_at: string
  fill_geocoding: boolean
}

export interface CreateRecordingRequest {
  name: string
  description?: string
  fill_geocoding?: boolean
}

export interface RecordingStatus {
  id: number
  name: string
  description: string | null
  status: 'active' | 'ended'
  track_count: number
  last_upload_at: string | null
  created_at: string
  tracks: RecordingTrack[]
}

export interface RecordingTrack {
  id: number
  name: string
  distance: number
  duration: number
  created_at: string
}

export interface UploadToRecordingResponse {
  message: string
  track_id: number
  recording_id: number
  recording_name: string
}

// API 方法
export const liveRecordingApi = {
  // 创建记录会话
  create(data: CreateRecordingRequest): Promise<LiveRecording> {
    return http.post('/live-recordings/create', data)
  },

  // 根据 token 获取记录信息（无需认证）
  getInfoByToken(token: string): Promise<LiveRecording> {
    // 不使用 http 客户端，因为这是无认证请求
    return fetch(`/api/live-recordings/info/${token}`).then(async (res) => {
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || '获取记录信息失败')
      }
      return res.json()
    })
  },

  // 获取记录列表
  getList(status?: 'active' | 'ended'): Promise<LiveRecording[]> {
    return http.get('/live-recordings', {
      params: status ? { status } : undefined,
    })
  },

  // 结束记录
  end(recordingId: number): Promise<LiveRecording> {
    return http.post(`/live-recordings/${recordingId}/end`)
  },

  // 删除记录
  delete(recordingId: number): Promise<void> {
    return http.delete(`/live-recordings/${recordingId}`)
  },

  // 更新自动填充地理信息设置
  updateFillGeocoding(recordingId: number, fillGeocoding: boolean): Promise<{ fill_geocoding: boolean; message: string }> {
    return http.patch(`/live-recordings/${recordingId}/fill-geocoding`, { fill_geocoding: fillGeocoding })
  },

  // 获取记录状态
  getStatus(recordingId: number): Promise<RecordingStatus> {
    return http.get(`/live-recordings/${recordingId}/status`)
  },

  // 获取记录详情（返回轨迹详情格式，用于轨迹详情页）
  getDetail(recordingId: number): Promise<import('./track').TrackResponse> {
    return http.get(`/live-recordings/${recordingId}/detail`)
  },

  // 使用 token 上传轨迹（无认证）
  uploadWithToken(
    token: string,
    data: {
      file: File
      name: string
      description?: string
      original_crs?: string
      convert_to?: string
      fill_geocoding?: boolean
    }
  ): Promise<UploadToRecordingResponse> {
    const formData = new FormData()
    formData.append('file', data.file)
    formData.append('name', data.name)
    if (data.description) formData.append('description', data.description)
    if (data.original_crs) formData.append('original_crs', data.original_crs)
    if (data.convert_to) formData.append('convert_to', data.convert_to)
    if (data.fill_geocoding !== undefined)
      formData.append('fill_geocoding', String(data.fill_geocoding))

    // 不使用 http 客户端，因为这是无认证请求
    return fetch(`/api/live-recordings/upload/${token}`, {
      method: 'POST',
      body: formData,
    }).then(async (res) => {
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || '上传失败')
      }
      return res.json()
    })
  },

  // 获取完整上传 URL
  getFullUploadUrl(token: string): string {
    return `${window.location.origin}/api/live-recordings/log/${token}`
  },

  // 获取 GPS Logger 格式的日志记录 URL
  getGpsLoggerUrl(token: string): string {
    const origin = window.location.origin
    return `${origin}/api/live-recordings/log/${token}?lat=%LAT&lon=%LON&time=%TIME&alt=%ALT&spd=%SPD`
  },
}
