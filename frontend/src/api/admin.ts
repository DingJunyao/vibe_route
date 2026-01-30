import http from './request'

// 坐标系类型
export type CRSType = 'wgs84' | 'gcj02' | 'bd09'

// 地图底图配置
export interface MapLayerConfig {
  id: string
  name: string
  url: string
  crs: CRSType
  attribution: string
  max_zoom: number
  min_zoom: number
  enabled: boolean
  order: number
  subdomains?: string | string[]
  ak?: string  // 百度地图 AK
  tk?: string  // 天地图 tk
  api_key?: string  // 高德地图 JS API Key
  security_js_code?: string  // 高德地图安全密钥
}

// 系统配置相关接口
export interface SystemConfig {
  registration_enabled: boolean
  invite_code_required: boolean
  default_map_provider: string
  geocoding_provider: string
  geocoding_config: {
    nominatim?: {
      url: string
      email?: string
    }
    gdf?: {
      data_path: string
    }
    amap?: {
      api_key: string
    }
    baidu?: {
      api_key: string
    }
  }
  map_layers: Record<string, MapLayerConfig>
  font_config?: FontConfig
  show_road_sign_in_region_tree: boolean
  spatial_backend: string  // 空间计算后端: auto | python | postgis
}

// 字体配置
export interface FontConfig {
  font_a?: string
  font_b?: string
  font_c?: string
}

// 字体文件信息
export interface FontInfo {
  filename: string
  size: number
  font_type?: string
}

// 字体列表响应
export interface FontListResponse {
  fonts: FontInfo[]
  active_fonts: FontConfig
}

export interface ConfigUpdateData {
  registration_enabled?: boolean
  invite_code_required?: boolean
  default_map_provider?: string
  geocoding_provider?: string
  geocoding_config?: {
    nominatim?: {
      url: string
      email?: string
    }
    gdf?: {
      data_path: string
    }
    amap?: {
      api_key: string
    }
    baidu?: {
      api_key: string
    }
  }
  map_layers?: Record<string, Partial<MapLayerConfig>>
  font_config?: FontConfig
  show_road_sign_in_region_tree?: boolean
  spatial_backend?: string
}

// 分页响应
export interface PaginatedResponse<T> {
  items: T[]
  total: number
}

// 用户相关接口
export interface User {
  id: number
  username: string
  email?: string
  is_admin: boolean
  is_active: boolean
  is_valid: boolean
  created_at: string
  updated_at: string
}

// 邀请码相关接口
export interface InviteCode {
  id: number
  code: string
  max_uses: number
  used_count: number
  created_by: number
  created_at: string
  expires_at?: string
  is_valid: boolean
}

export interface CreateInviteCodeData {
  code?: string
  max_uses: number
  expires_in_days?: number
}

export const adminApi = {
  // 获取系统配置
  getConfig(): Promise<SystemConfig> {
    return http.get('/admin/config')
  },

  // 更新系统配置
  updateConfig(data: ConfigUpdateData): Promise<SystemConfig> {
    return http.put('/admin/config', data)
  },

  // 获取用户列表（支持分页、搜索、排序、筛选）
  getUsers(params?: {
    page?: number
    page_size?: number
    search?: string
    sort_by?: string
    sort_order?: 'asc' | 'desc'
    roles?: string[]
    statuses?: string[]
  }): Promise<PaginatedResponse<User>> {
    return http.get('/admin/users', { params })
  },

  // 更新用户
  updateUser(userId: number, data: { is_admin?: boolean; is_active?: boolean }): Promise<User> {
    return http.put(`/admin/users/${userId}`, data)
  },

  // 删除用户
  deleteUser(userId: number): Promise<{ message: string }> {
    return http.delete(`/admin/users/${userId}`)
  },

  // 重置用户密码
  resetPassword(userId: number, new_password: string): Promise<{ message: string }> {
    return http.post(`/admin/users/${userId}/reset-password`, { new_password })
  },

  // 创建邀请码
  createInviteCode(data: CreateInviteCodeData): Promise<InviteCode> {
    return http.post('/admin/invite-codes', data)
  },

  // 获取邀请码列表（支持分页）
  getInviteCodes(params?: { page?: number; page_size?: number }): Promise<PaginatedResponse<InviteCode>> {
    return http.get('/admin/invite-codes', { params })
  },

  // 删除邀请码
  deleteInviteCode(inviteCodeId: number): Promise<{ message: string }> {
    return http.delete(`/admin/invite-codes/${inviteCodeId}`)
  },

  // ========== 字体管理 ==========

  // 获取字体列表
  getFonts(): Promise<FontListResponse> {
    return http.get('/admin/fonts')
  },

  // 设置激活字体
  setActiveFont(fontType: string, filename: string): Promise<{ message: string }> {
    return http.post(`/admin/fonts/${fontType}/set-active?filename=${filename}`)
  },

  // 上传字体
  uploadFont(file: File): Promise<{ message: string; filename: string }> {
    const formData = new FormData()
    formData.append('file', file)
    return http.post('/admin/fonts/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // 删除字体
  deleteFont(filename: string): Promise<{ message: string }> {
    return http.delete(`/admin/fonts/${filename}`)
  },

  // 获取数据库信息（用于判断是否显示 PostGIS 设置）
  getDatabaseInfo(): Promise<DatabaseInfo> {
    return http.get('/admin/database-info')
  },
}

// 数据库信息响应
export interface DatabaseInfo {
  database_type: 'sqlite' | 'mysql' | 'postgresql'
  postgis_enabled: boolean
}
