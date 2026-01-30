<template>
  <el-container class="overlay-generator-container">
    <el-header>
      <div class="header-content">
        <el-button @click="$router.push('/home')" :icon="HomeFilled" />
        <h1>信息覆盖层生成</h1>
      </div>
    </el-header>

    <el-main>
      <el-row :gutter="30">
        <!-- 左侧：配置 -->
        <el-col :span="10">
          <el-card shadow="never">
            <template #header>
              <span>生成配置</span>
            </template>

            <el-form :model="form" label-width="100px">
              <!-- 选择轨迹 -->
              <el-form-item label="选择轨迹" required>
                <el-select
                  v-model="form.track_id"
                  placeholder="选择要生成的轨迹"
                  filterable
                  style="width: 100%"
                  :loading="tracksLoading"
                >
                  <el-option
                    v-for="track in tracks"
                    :key="track.id"
                    :label="`${track.name} (${formatDistance(track.distance)})`"
                    :value="track.id"
                  >
                    <span>{{ track.name }}</span>
                    <span style="float: right; color: #8492a6; font-size: 12px">
                      {{ formatDistance(track.distance) }}
                    </span>
                  </el-option>
                </el-select>
              </el-form-item>

              <!-- 图片尺寸 -->
              <el-form-item label="图片尺寸">
                <el-select v-model="form.image_width" style="width: 120px">
                  <el-option label="1280x720" :value="1280" />
                  <el-option label="1920x1080" :value="1920" />
                  <el-option label="2560x1440" :value="2560" />
                  <el-option label="3840x2160" :value="3840" />
                </el-select>
                <span style="margin: 0 8px">×</span>
                <el-select v-model="form.image_height" style="width: 120px">
                  <el-option label="720" :value="720" />
                  <el-option label="1080" :value="1080" />
                  <el-option label="1440" :value="1440" />
                  <el-option label="2160" :value="2160" />
                </el-select>
              </el-form-item>

              <!-- 字体大小 -->
              <el-form-item label="字体大小">
                <el-slider
                  v-model="form.font_size"
                  :min="24"
                  :max="72"
                  :step="4"
                  show-input
                  :marks="{ 24: '小', 48: '中', 72: '大' }"
                />
              </el-form-item>

              <!-- 显示选项 -->
              <el-divider content-position="left">显示内容</el-divider>

              <el-form-item label="显示坐标">
                <el-switch v-model="form.show_coords" />
              </el-form-item>

              <el-form-item label="显示海拔">
                <el-switch v-model="form.show_elevation" />
              </el-form-item>

              <el-form-item label="显示道路">
                <el-switch v-model="form.show_road_info" />
              </el-form-item>

              <!-- 操作按钮 -->
              <el-form-item>
                <el-button
                  type="primary"
                  @click="generate"
                  :loading="generating"
                  :disabled="!form.track_id"
                  style="width: 100%"
                >
                  <el-icon><VideoCamera /></el-icon>
                  生成覆盖层
                </el-button>
              </el-form-item>
            </el-form>
          </el-card>

          <!-- 说明 -->
          <el-card shadow="never" style="margin-top: 20px">
            <template #header>
              <span>功能说明</span>
            </template>
            <div class="info-text">
              <p>信息覆盖层会为轨迹的每个点生成一张 PNG 图片，包含：</p>
              <ul>
                <li>道路编号和道路名称</li>
                <li>行政区划信息（省市区）</li>
                <li>当前点的坐标</li>
                <li>海拔和时间信息</li>
              </ul>
              <p>生成的图片会打包成 ZIP 文件供下载。</p>
              <el-alert
                type="info"
                :closable="false"
                show-icon
                style="margin-top: 12px"
              >
                注意：生成大型轨迹可能需要较长时间
              </el-alert>
            </div>
          </el-card>
        </el-col>

        <!-- 右侧：任务状态 -->
        <el-col :span="14">
          <el-card shadow="never">
            <template #header>
              <div style="display: flex; justify-content: space-between; align-items: center">
                <span>任务状态</span>
                <el-button
                  size="small"
                  @click="loadTasks"
                  :icon="Refresh"
                >
                  刷新
                </el-button>
              </div>
            </template>

            <!-- 当前任务 -->
            <div v-if="currentTask" class="current-task">
              <div class="task-header">
                <el-tag :type="getTaskStatusType(currentTask.status)">
                  {{ getTaskStatusText(currentTask.status) }}
                </el-tag>
                <span class="task-id">#{{ currentTask.id }}</span>
              </div>

              <!-- 进度条 -->
              <div class="progress-section">
                <el-progress
                  :percentage="currentTask.progress"
                  :status="getProgressStatus(currentTask.status)"
                  :stroke-width="24"
                >
                  <template #default="{ percentage }">
                    <span class="percentage-text">{{ percentage }}%</span>
                  </template>
                </el-progress>
              </div>

              <!-- 任务详情 -->
              <el-descriptions :column="2" border class="task-descriptions">
                <el-descriptions-item label="任务类型">
                  {{ getTaskTypeText(currentTask.type) }}
                </el-descriptions-item>
                <el-descriptions-item label="创建时间">
                  {{ formatDateTime(currentTask.created_at) }}
                </el-descriptions-item>
                <el-descriptions-item label="结果文件" v-if="currentTask.result_path">
                  {{ getFileName(currentTask.result_path) }}
                </el-descriptions-item>
                <el-descriptions-item label="错误信息" v-if="currentTask.error_message">
                  <span style="color: #f56c6c">{{ currentTask.error_message }}</span>
                </el-descriptions-item>
              </el-descriptions>

              <!-- 下载按钮 -->
              <div v-if="currentTask.status === 'completed' && currentTask.result_path" class="action-section">
                <el-button
                  type="primary"
                  size="large"
                  @click="downloadResult"
                  :icon="Download"
                >
                  下载 ZIP 文件
                </el-button>
              </div>
            </div>

            <!-- 无任务 -->
            <div v-else class="empty-task">
              <el-empty
                description="暂无任务"
                :image-size="100"
              />
            </div>
          </el-card>

          <!-- 历史任务 -->
          <el-card shadow="never" style="margin-top: 20px">
            <template #header>
              <span>历史任务</span>
            </template>
            <el-scrollbar max-height="300">
              <div v-if="taskHistory.length === 0" class="empty-text">
                暂无历史任务
              </div>
              <div v-else class="task-list">
                <div
                  v-for="task in taskHistory"
                  :key="task.id"
                  class="task-item"
                  @click="selectTask(task)"
                >
                  <el-tag :type="getTaskStatusType(task.status)" size="small">
                    {{ getTaskStatusText(task.status) }}
                  </el-tag>
                  <span class="task-id">#{{ task.id }}</span>
                  <span class="task-type">{{ getTaskTypeText(task.type) }}</span>
                  <span class="task-time">{{ formatDateTime(task.created_at) }}</span>
                  <el-button
                    v-if="task.status === 'completed'"
                    type="primary"
                    size="small"
                    text
                    @click.stop="downloadTaskById(task.id)"
                    :icon="Download"
                  >
                    下载
                  </el-button>
                </div>
              </div>
            </el-scrollbar>
          </el-card>
        </el-col>
      </el-row>
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { HomeFilled, VideoCamera, Refresh, Download } from '@element-plus/icons-vue'
import { taskApi, type Task, type CreateOverlayTaskRequest } from '@/api/task'
import { trackApi, type Track } from '@/api/track'

// 表单数据
const form = reactive<CreateOverlayTaskRequest>({
  track_id: 0,
  image_width: 1920,
  image_height: 1080,
  font_size: 48,
  show_coords: true,
  show_elevation: true,
  show_road_info: true,
})

// 状态
const tracks = ref<Track[]>([])
const tracksLoading = ref(false)
const generating = ref(false)
const currentTask = ref<Task | null>(null)
const taskHistory = ref<Task[]>([])
let pollTimer: ReturnType<typeof setInterval> | null = null

// 标记组件是否已挂载，用于避免卸载后更新状态
const isMounted = ref(true)

// 加载轨迹列表
async function loadTracks() {
  tracksLoading.value = true
  try {
    const result = await trackApi.getList({ page: 1, page_size: 100 })
    if (isMounted.value) {
      tracks.value = result
    }
  } catch (error) {
    console.error('Failed to load tracks:', error)
  } finally {
    if (isMounted.value) {
      tracksLoading.value = false
    }
  }
}

// 加载任务列表
async function loadTasks() {
  try {
    const tasks = await taskApi.listTasks(20)
    if (!isMounted.value) return
    if (tasks.length > 0) {
      // 第一个是最新任务
      if (!currentTask.value || tasks[0].id !== currentTask.value.id) {
        currentTask.value = tasks[0]
      }
      taskHistory.value = tasks.slice(1)
    }
  } catch (error) {
    console.error('Failed to load tasks:', error)
  }
}

// 选择任务
function selectTask(task: Task) {
  currentTask.value = task
}

// 生成覆盖层
async function generate() {
  if (!form.track_id) {
    ElMessage.warning('请选择轨迹')
    return
  }

  generating.value = true
  try {
    const task = await taskApi.createOverlayTask(form)
    currentTask.value = task
    ElMessage.success('任务已创建')

    // 开始轮询任务状态
    startPolling()

    // 刷新任务列表
    loadTasks()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '创建任务失败')
  } finally {
    generating.value = false
  }
}

// 开始轮询任务状态
function startPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
  }

  pollTimer = setInterval(async () => {
    if (!currentTask.value || !isMounted.value) return

    try {
      const task = await taskApi.getTask(currentTask.value.id)
      if (!isMounted.value) return
      currentTask.value = task

      // 如果任务完成，停止轮询
      if (task.is_finished) {
        stopPolling()
        loadTasks()

        if (isMounted.value) {
          if (task.status === 'completed') {
            ElMessage.success('覆盖层生成完成！')
          } else {
            ElMessage.error(`任务失败: ${task.error_message}`)
          }
        }
      }
    } catch (error) {
      console.error('Failed to poll task status:', error)
    }
  }, 2000) // 每 2 秒轮询一次
}

// 停止轮询
function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

// 下载当前任务结果
async function downloadResult() {
  if (!currentTask.value || !currentTask.value.result_path) return

  try {
    const url = taskApi.download(currentTask.value.id)
    const response = await fetch(url, {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      }
    })

    if (!response.ok) throw new Error('下载失败')

    const blob = await response.blob()
    const blobUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = blobUrl
    link.download = currentTask.value.result_path.split('\\').pop() || 'overlay.zip'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(blobUrl)

    ElMessage.success('下载成功')
  } catch (error) {
    ElMessage.error('下载失败')
  }
}

// 下载指定任务结果
async function downloadTaskById(taskId: number) {
  try {
    const url = taskApi.download(taskId)
    const response = await fetch(url, {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      }
    })

    if (!response.ok) throw new Error('下载失败')

    const blob = await response.blob()
    const blobUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = blobUrl
    link.download = 'overlay.zip'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(blobUrl)

    ElMessage.success('下载成功')
  } catch (error) {
    ElMessage.error('下载失败')
  }
}

// 获取任务状态类型
function getTaskStatusType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  const types: Record<string, any> = {
    pending: 'info',
    running: 'warning',
    completed: 'success',
    failed: 'danger',
  }
  return types[status] || 'info'
}

// 获取任务状态文本
function getTaskStatusText(status: string): string {
  const texts: Record<string, string> = {
    pending: '等待中',
    running: '处理中',
    completed: '已完成',
    failed: '失败',
  }
  return texts[status] || status
}

// 获取任务类型文本
function getTaskTypeText(type: string): string {
  const texts: Record<string, string> = {
    overlay_generate: '覆盖层生成',
  }
  return texts[type] || type
}

// 获取进度条状态
function getProgressStatus(status: string): '' | 'success' | 'exception' {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'exception'
  return ''
}

// 获取文件名
function getFileName(path: string): string {
  return path.split('\\').pop() || path.split('/').pop() || path
}

// 格式化距离
function formatDistance(meters: number): string {
  if (meters < 1000) return `${meters.toFixed(1)} m`
  return `${(meters / 1000).toFixed(2)} km`
}

// 格式化日期时间
function formatDateTime(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (hours < 24) return `${hours}小时前`
  if (days < 7) return `${days}天前`

  return date.toLocaleString('zh-CN')
}

onMounted(() => {
  loadTracks()
  loadTasks()
})

// 组件即将卸载时设置标志
onBeforeUnmount(() => {
  isMounted.value = false
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.overlay-generator-container {
  min-height: 100vh;
  background: #f5f7fa;
}

.el-header {
  background: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  display: flex;
  align-items: center;
}

.header-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.el-header h1 {
  font-size: 20px;
  margin: 0;
}

.info-text p {
  margin-bottom: 12px;
  color: #606266;
}

.info-text ul {
  margin: 8px 0;
  padding-left: 20px;
  color: #909399;
}

.info-text li {
  margin-bottom: 4px;
}

.current-task {
  padding: 20px;
}

.task-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.task-id {
  font-size: 14px;
  color: #909399;
  font-family: monospace;
}

.progress-section {
  margin-bottom: 24px;
}

.percentage-text {
  font-weight: bold;
  color: #333;
}

.task-descriptions {
  margin-bottom: 24px;
}

.action-section {
  text-align: center;
}

.empty-task {
  padding: 40px;
}

.empty-text {
  text-align: center;
  color: #909399;
  padding: 20px;
}

.task-list {
  font-size: 13px;
}

.task-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid #f5f7fa;
  cursor: pointer;
  transition: background 0.2s;
  gap: 8px;
}

.task-item:hover {
  background: #f5f7fa;
}

.task-item:last-child {
  border-bottom: none;
}

.task-type {
  flex: 1;
  color: #606266;
}

.task-time {
  color: #909399;
  font-size: 12px;
}
</style>
