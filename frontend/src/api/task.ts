import { http } from './request'

// 任务类型定义
export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed'
export type TaskType = 'overlay_generate'

export interface Task {
  id: number
  type: TaskType
  status: TaskStatus
  progress: number
  result_path?: string
  error_message?: string
  created_at: string
  is_finished: boolean
}

export interface CreateOverlayTaskRequest {
  track_id: number
  image_width?: number
  image_height?: number
  font_size?: number
  show_coords?: boolean
  show_elevation?: boolean
  show_road_info?: boolean
}

// API 方法
export const taskApi = {
  // 创建覆盖层生成任务
  createOverlayTask(data: CreateOverlayTaskRequest): Promise<Task> {
    return http.post('/tasks/generate-overlay', data)
  },

  // 获取任务状态
  getTask(taskId: number): Promise<Task> {
    return http.get(`/tasks/${taskId}`)
  },

  // 获取任务列表
  listTasks(limit?: number): Promise<Task[]> {
    return http.get('/tasks', { params: { limit } })
  },

  // 下载任务结果
  download(taskId: number): string {
    return `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/tasks/${taskId}/download`
  },
}
