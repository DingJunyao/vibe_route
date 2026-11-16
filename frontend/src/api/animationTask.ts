// frontend/src/api/animationTask.ts
// 录屏（动画导出）任务 API

import { http } from './request'

export type AnimationTaskStatus =
  | 'pending'
  | 'processing'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'expired'

export interface AnimationExportRuntime {
  stage: string
  current_time_ms?: number | null      // 已录制到的轨迹时间点（毫秒）
  total_time_ms?: number | null        // 轨迹区间总时长（毫秒）
  current_frame?: number | null        // 已录制帧号（逐帧模式）
  total_frames?: number | null         // 总帧数（逐帧模式）
  point_index?: number | null          // 当前轨迹点序号（0 基）
  total_points?: number | null         // 轨迹点总数
  elapsed_seconds?: number | null      // 录制已用时长（秒）
  eta_seconds?: number | null          // 预计剩余时长（秒）
  thumbnail_url?: string | null        // 实时缩略图地址（带版本参数）
}

export interface AnimationExportTask {
  task_id: string
  status: AnimationTaskStatus
  progress: number
  download_url?: string | null
  error?: string | null
  track_id?: number | null
  track_title?: string | null
  username?: string | null
  queue_position?: number | null
  runtime?: AnimationExportRuntime | null
  created_at?: string | null
  started_at?: string | null
  finished_at?: string | null
}

export interface AnimationExportTaskList {
  total: number
  items: AnimationExportTask[]
}

export interface AnimationTaskQuery {
  page?: number
  page_size?: number
  status?: AnimationTaskStatus | ''
  username?: string
}

export const animationTaskApi = {
  // 我的录屏任务列表（分页）
  listMine(page = 1, pageSize = 20, status?: AnimationTaskStatus | ''): Promise<AnimationExportTaskList> {
    return http.get('/animation/export/my', {
      params: { page, page_size: pageSize, status: status || undefined },
      skipProgress: true,
    })
  },

  // 任务详情
  get(taskId: string): Promise<AnimationExportTask> {
    return http.get(`/animation/export/${taskId}`, { skipProgress: true })
  },

  // 取消（pending/processing）或删除（终态）任务
  cancelOrDelete(taskId: string): Promise<{ message: string; status: AnimationTaskStatus }> {
    return http.delete(`/animation/export/${taskId}`, { skipProgress: true })
  },

  // 任务作用域令牌：completed 用于原生下载，processing 用于缩略图（img 无法携带 Bearer 头）
  createDownloadToken(taskId: string): Promise<{ download_token: string; expires_in: number }> {
    return http.post(`/animation/export/${taskId}/download-token`, {}, { skipProgress: true })
  },

  // 全部用户任务列表（管理员）
  adminList(query: AnimationTaskQuery = {}): Promise<AnimationExportTaskList> {
    return http.get('/animation/export/admin/tasks', {
      params: {
        page: query.page ?? 1,
        page_size: query.page_size ?? 20,
        status: query.status || undefined,
        username: query.username || undefined,
      },
      skipProgress: true,
    })
  },

  // 立即清理过期录屏文件（管理员）
  adminCleanup(): Promise<{ cleaned: number }> {
    return http.post('/animation/export/admin/cleanup', {}, { skipProgress: true })
  },
}
