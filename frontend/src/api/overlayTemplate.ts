/**
 * 覆盖层模板 API
 */
import request from './request'
import type { AxiosProgressEvent } from 'axios'

// ============================================================================
// 类型定义
// ============================================================================

export type ContainerAnchor =
  | 'top-left' | 'top' | 'top-right'
  | 'left' | 'center' | 'right'
  | 'bottom-left' | 'bottom' | 'bottom-right'

export type ElementAnchor = ContainerAnchor

export type DataSource =
  | 'none'  // 自定义文本，不从数据源获取
  | 'province' | 'city' | 'district'
  | 'province_en' | 'city_en' | 'district_en'
  | 'region' | 'region_en'
  | 'road_number' | 'road_name' | 'road_name_en'
  | 'speed' | 'elevation' | 'compass_angle'
  | 'elapsed_distance' | 'elapsed_time'
  | 'remain_distance' | 'remain_time'
  | 'current_time' | 'latitude' | 'longitude'

export interface PositionConfig {
  container_anchor: ContainerAnchor
  element_anchor: ElementAnchor
  x: number
  y: number
  use_safe_area: boolean
}

export interface SizeConfig {
  width?: number
  height?: number
}

export interface ContentConfig {
  source: DataSource
  prefix: string  // 已废弃，使用 format
  suffix: string  // 已废弃，使用 format
  format: string  // 支持前缀后缀和小数位数，如 '速度: {:.1f} km/h'
  sample_text?: string  // 自定义示例文本
  decimal_places?: number  // 小数位数（0-10）
}

export interface TextLayoutConfig {
  width?: number
  max_width?: number
  min_width?: number
  height?: number
  horizontal_align: 'left' | 'center' | 'right' | 'justify'
  vertical_align: 'top' | 'middle' | 'bottom'
  wrap: boolean
  max_lines?: number
  line_height: number
  char_spacing?: number
  paragraph_spacing?: number
}

export interface StyleConfig {
  font_family: string
  font_size: number
  color: string
  background_color?: string
  padding?: number
}

export interface OverlayElement {
  id: string
  type: 'text' | 'road_sign' | 'icon' | 'group'
  name: string
  visible: boolean | string
  position: PositionConfig
  size: SizeConfig
  style?: StyleConfig
  content?: ContentConfig
  layout?: TextLayoutConfig
  children?: OverlayElement[]
}

export interface SafeAreaConfig {
  top: number
  bottom: number
  left: number
  right: number
}

export interface BackgroundConfig {
  color: string
  opacity: number
}

export interface CanvasConfig {
  width: number
  height: number
}

export interface OverlayTemplateConfig {
  canvas: CanvasConfig
  safe_area: SafeAreaConfig
  background?: BackgroundConfig
  elements: OverlayElement[]
}

export interface OverlayTemplate {
  id: number
  name: string
  description: string | null
  config: OverlayTemplateConfig
  user_id: number | null
  is_public: boolean
  is_system: boolean
  created_at: string
  updated_at: string
}

export interface OverlayTemplateCreate {
  name: string
  description?: string
  config: OverlayTemplateConfig
}

export interface OverlayTemplateUpdate {
  name?: string
  description?: string
  config?: OverlayTemplateConfig
  is_public?: boolean
}

export interface OverlayTemplateListResponse {
  total: number
  items: OverlayTemplate[]
}

export interface Font {
  id: string
  name: string
  filename: string
  type: 'system' | 'admin' | 'user'
  owner_id: number | null
  file_size: number
  family: string | null
  style: string
  weight: number
  supports_latin: boolean
  supports_chinese: boolean
  supports_japanese: boolean
  supports_korean: boolean
  preview_url: string | null
  created_at: string
}

export interface FontListResponse {
  total: number
  items: Font[]
}

// ============================================================================
// API 方法
// ============================================================================

export const overlayTemplateApi = {
  /**
   * 获取模板列表
   */
  list: (params?: { include_system?: boolean; only_public?: boolean }) => {
    return request.get<OverlayTemplateListResponse>('/overlay-templates', { params })
  },

  /**
   * 获取单个模板
   */
  get: (templateId: number) => {
    return request.get<OverlayTemplate>(`/overlay-templates/${templateId}`)
  },

  /**
   * 创建模板
   */
  create: (data: OverlayTemplateCreate) => {
    return request.post<OverlayTemplate>('/overlay-templates', data)
  },

  /**
   * 更新模板
   */
  update: (templateId: number, data: OverlayTemplateUpdate) => {
    return request.put<OverlayTemplate>(`/overlay-templates/${templateId}`, data)
  },

  /**
   * 删除模板
   */
  delete: (templateId: number) => {
    return request.delete(`/overlay-templates/${templateId}`)
  },

  /**
   * 复制模板
   */
  duplicate: (templateId: number) => {
    return request.post<OverlayTemplate>(`/overlay-templates/${templateId}/duplicate`)
  },

  /**
   * 导出模板为 YAML
   */
  export: (templateId: number) => {
    return request.get<string>(`/overlay-templates/${templateId}/export`, {
      responseType: 'blob'
    })
  },

  /**
   * 从 YAML 导入模板
   */
  import: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return request.post<OverlayTemplate>('/overlay-templates/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },

  /**
   * 生成模板预览图（使用模板配置中的画布尺寸）
   */
  preview: (templateId: number) => {
    return request.get<Blob>(`/overlay-templates/${templateId}/preview`, {
      responseType: 'blob'
    })
  },

  /**
   * 使用指定配置生成预览图（不保存到数据库）
   */
  previewWithConfig: (config: OverlayTemplateConfig) => {
    return request.post<Blob>('/overlay-templates/preview-with-config', { config }, {
      responseType: 'blob'
    })
  },

  /**
   * 获取字体列表
   */
  listFonts: () => {
    return request.get<FontListResponse>('/overlay-templates/fonts/list')
  },

  /**
   * 上传字体
   */
  uploadFont: (file: File, onProgress?: (progress: number) => void) => {
    const formData = new FormData()
    formData.append('file', file)
    return request.post<Font>('/overlay-templates/fonts/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent: AxiosProgressEvent) => {
        if (onProgress && progressEvent.total) {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          onProgress(percentCompleted)
        }
      }
    })
  },

  /**
   * 删除字体
   */
  deleteFont: (fontId: string) => {
    return request.delete(`/overlay-templates/fonts/${fontId}`)
  },

  /**
   * 导出覆盖层序列（使用模板配置中的画布尺寸）
   */
  exportOverlay: (
    trackId: number,
    params: {
      template_id: number
      frame_rate?: number
      start_index?: number
      end_index?: number
      output_format?: 'zip' | 'png_sequence'
    }
  ) => {
    const formData = new FormData()
    Object.entries(params).forEach(([key, value]) => {
      formData.append(key, String(value))
    })
    return request.post<Blob>(`/overlay-templates/tracks/${trackId}/export`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      responseType: 'blob'
    })
  }
}
