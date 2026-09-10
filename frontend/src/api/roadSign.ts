import { http } from './request'

// 道路标志类型定义
export interface RoadSignRequest {
  sign_type: 'way' | 'expwy'
  code: string
  province?: string
  name?: string
  region?: string      // 地区: cn(缺省)/id。id 时 sign_type 被忽略，按编号+路名判级生成六边形盾牌
  name_id?: string     // 印尼语路名（TOL 关键词判定文本之一）
}

export interface RoadSignResponse {
  svg: string
  cached: boolean
  sign_type: string
  code: string
  province?: string
  name?: string
  region?: string      // 回显请求地区（缺省 'cn'）
}

export interface RoadSignListItem {
  id: string
  code: string
  province?: string
  name?: string
  sign_type: string
}

// API 方法
export const roadSignApi = {
  // 生成道路标志（公开访问，无需认证）
  generate(data: RoadSignRequest): Promise<RoadSignResponse> {
    return http.post('/road-signs/generate', data, { skipAuth: true })
  },

  // 获取已生成的标志列表
  getList(params?: { sign_type?: string; limit?: number }): Promise<RoadSignListItem[]> {
    return http.get('/road-signs/list', { params })
  },

  // 清除缓存
  clearCache(sign_type?: string): Promise<{ count: number }> {
    return http.post('/road-signs/clear-cache', null, { params: { sign_type } })
  },
}
