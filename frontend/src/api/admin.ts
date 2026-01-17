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
}

// 用户相关接口
export interface User {
  id: number
  username: string
  email?: string
  is_admin: boolean
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

  // 获取用户列表
  getUsers(params?: { skip?: number; limit?: number }): Promise<User[]> {
    return http.get('/admin/users', { params })
  },

  // 更新用户
  updateUser(userId: number, data: { is_admin?: boolean; is_valid?: boolean }): Promise<User> {
    return http.put(`/admin/users/${userId}`, data)
  },

  // 删除用户
  deleteUser(userId: number): Promise<{ message: string }> {
    return http.delete(`/admin/users/${userId}`)
  },

  // 创建邀请码
  createInviteCode(data: CreateInviteCodeData): Promise<InviteCode> {
    return http.post('/admin/invite-codes', data)
  },

  // 获取邀请码列表
  getInviteCodes(params?: { skip?: number; limit?: number }): Promise<InviteCode[]> {
    return http.get('/admin/invite-codes', { params })
  },

  // 删除邀请码
  deleteInviteCode(inviteCodeId: number): Promise<{ message: string }> {
    return http.delete(`/admin/invite-codes/${inviteCodeId}`)
  },
}
