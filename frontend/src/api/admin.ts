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
    gdf?: Record<string, never>  // GDF 使用 spatial_backend 配置
    amap?: {
      api_key: string
      freq: number
    }
    baidu?: {
      api_key: string
      freq: number
      get_en_result: boolean
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
    gdf?: Record<string, never>  // GDF 使用 spatial_backend 配置
    amap?: {
      api_key: string
      freq: number
    }
    baidu?: {
      api_key: string
      freq: number
      get_en_result: boolean
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

  // 获取行政区划数据统计
  getAdminDivisionStats(): Promise<AdminDivisionStats> {
    return http.get('/admin/admin-division-stats')
  },

  // ========== 特殊地名映射管理 ==========

  // 获取特殊地名映射表
  getSpecialPlaceMapping() {
    return http.get('/admin/special-place-mapping') as Promise<SpecialPlaceMappingResponse>
  },

  // 更新特殊地名映射表
  updateSpecialPlaceMapping(request: UpdateSpecialPlaceMappingRequest) {
    return http.put('/admin/special-place-mapping', request) as Promise<{ message: string }>
  },

  // 重新生成英文名称
  regenerateNameEn() {
    return http.post('/admin/special-place-mapping/regenerate') as Promise<RegenerateNameEnResponse>
  },

  // ========== 边界数据管理（已弃用） ==========
  // @deprecated 此功能已被 DataV GeoJSON 在线导入取代，保留代码以备不时之需

  /**
   * @deprecated 使用 importAdminDivisionsOnline 或 uploadAdminDivisionsArchive 替代
   */
  importBoundsData(file: File) {
    const formData = new FormData()
    formData.append('file', file)
    return http.post('/admin/import-bounds-data', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }) as Promise<{ message: string; task_id: number }>
  },

  /**
   * @deprecated 使用 getAdminDivisionsImportProgress 替代
   */
  getBoundsImportTask(taskId: number) {
    return http.get(`/admin/tasks/${taskId}`) as Promise<BoundsImportTask>
  },

  // 获取边界数据统计
  getBoundsStats() {
    return http.get('/admin/bounds-stats') as Promise<BoundsStatsResponse>
  },

  // 测试文件上传
  testUpload(file: File) {
    const formData = new FormData()
    formData.append('file', file)
    return http.post('/admin/test-upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }) as Promise<{ message: string; file_info: { filename: string; content_type: string; size: number } }>
  },

  // ========== DataV GeoJSON 行政区划导入 ==========

  // 获取行政区划数据状态
  getAdminDivisionStatus(): Promise<AdminDivisionStatusResponse> {
    return http.get('/admin/admin-divisions/status')
  },

  // 从 DataV 在线导入
  importFromDataVOnline(data: DataVImportRequest): Promise<DataVImportResponse> {
    return http.post('/admin/admin-divisions/import/online', data)
  },

  // 上传压缩包导入
  importFromUpload(file: File, force: boolean = false): Promise<DataVImportResponse> {
    const formData = new FormData()
    formData.append('file', file)
    return http.post(`/admin/admin-divisions/import/upload?force=${force}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // 获取导入任务进度
  getImportProgress(taskId: number): Promise<ImportTaskProgress> {
    return http.get(`/admin/admin-divisions/import/progress/${taskId}`)
  },

  // 获取省份列表
  getProvinceList(): Promise<ProvinceListResponse> {
    return http.get('/admin/admin-divisions/provinces')
  },

  // ========== PostGIS 几何数据同步 ==========

  // 获取 PostGIS 同步状态
  getPostgisSyncStatus(): Promise<PostgisSyncStatus> {
    return http.get('/admin/admin-divisions/postgis-status')
  },

  // 同步到 PostGIS
  syncPostgisGeometry(): Promise<{ message: string; task_id: number }> {
    return http.post('/admin/admin-divisions/sync-postgis')
  },

  // 获取任务状态（通用）
  getTask(taskId: number): Promise<TaskProgress> {
    return http.get(`/admin/tasks/${taskId}`)
  },
}

// 边界导入任务状态
export interface BoundsImportTask {
  id: number
  type: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number  // 0-100
  result_path?: string  // 成功时的结果摘要
  error_message?: string
  created_at: string
  is_finished: boolean
}

// 边界数据导入响应
export interface BoundsImportResponse {
  message: string
  stats: {
    total_files: number
    updated: number
    errors: number
  }
  error_details?: string[]
}

// 边界数据统计响应
export interface BoundsStatsResponse {
  by_level: Record<string, {
    total: number
    with_bounds: number
  }>
  missing_by_province: Array<{
    province_code: string
    province_name: string
    missing_count: number
    missing_areas: string
  }>
}

// 数据库信息响应
export interface DatabaseInfo {
  database_type: 'sqlite' | 'mysql' | 'postgresql'
  postgis_enabled: boolean
}

// 行政区划统计响应
export interface AdminDivisionStats {
  total: number
  by_level: {
    province: number
    city: number
    area: number
  }
  has_bounds: number
  has_postgis: number
  sample_missing_codes: Array<{
    code: string
    name: string
    city_code: string | null
    province_code: string | null
  }>
  error?: string
}

// 特殊地名映射响应
export interface SpecialPlaceMappingResponse {
  raw_yaml: string  // 原始 YAML 文件内容（保留注释和格式）
  mappings: Record<string, string>  // 中文名称 -> 英文转写（解析后的映射，用于前端显示）
  total: number
}

// 更新特殊地名映射请求
export interface UpdateSpecialPlaceMappingRequest {
  yaml_content: string  // 原始 YAML 内容（保留注释和格式）
}

// 重新生成英文名称响应
export interface RegenerateNameEnResponse {
  message: string
  stats: {
    total: number
    updated: number
  }
}

// ========== DataV GeoJSON 行政区划导入 ==========

// 行政区划状态响应
export interface AdminDivisionStatusResponse {
  total: number
  by_level: {
    province: number
    city: number
    area: number
  }
  has_bounds: number
  has_center: number
  last_updated: string | null
  error?: string
}

// DataV 导入请求
export interface DataVImportRequest {
  province_codes?: string[]
  force?: boolean
  bounds_only?: boolean
}

// DataV 导入响应
export interface DataVImportResponse {
  message: string
  task_id?: number
  stats?: {
    provinces: number
    cities: number
    areas: number
    updated?: number
    files?: number
  }
}

// 导入任务进度响应
export interface ImportTaskProgress {
  id: number
  type: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  result?: string
  error?: string
  created_at: string
  is_finished: boolean
}

// 省份列表响应
export interface ProvinceListResponse {
  provinces: Array<{
    code: string
    name: string
  }>
}

// ========== PostGIS 几何数据同步 ==========

// PostGIS 同步状态
export interface PostgisSyncStatus {
  has_geometry: number      // 有 geometry 字段的记录数
  has_postgis: number       // PostGIS 空间表有数据的记录数
  need_sync: number         // 需要同步的记录数
  postgis_enabled: boolean  // PostGIS 扩展是否启用
  spatial_table_exists: boolean  // 空间表是否存在
}

// 任务进度（通用）
export interface TaskProgress {
  id: number
  type: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  result?: string
  result_path?: string
  error?: string
  created_at: string
  is_finished: boolean
}
