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
