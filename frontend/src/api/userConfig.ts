import { http } from './request'

// 用户配置类型定义
export interface UserConfig {
  id: number
  user_id: number
  map_provider: string | null
  map_layers: Record<string, any> | null
  // 录屏任务邮件通知开关（还需管理员开启总开关才生效）
  notify_recording_completed: boolean
  notify_recording_failed: boolean
  created_at: string
  updated_at: string
}

export interface UserConfigUpdate {
  map_provider?: string | null
  map_layers?: Record<string, any> | null
  notify_recording_completed?: boolean
  notify_recording_failed?: boolean
}

// 用户配置 API
export const userConfigApi = {
  // 获取用户配置
  getConfig(): Promise<UserConfig> {
    return http.get('/user/config')
  },

  // 更新用户配置
  updateConfig(data: UserConfigUpdate): Promise<UserConfig> {
    return http.put('/user/config', data)
  },

  // 重置用户配置（清除自定义，使用系统默认）
  resetConfig(): Promise<{ message: string }> {
    return http.post('/user/config')
  },
}
