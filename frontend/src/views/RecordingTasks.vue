<!-- frontend/src/views/RecordingTasks.vue -->
<template>
  <el-container class="recording-tasks-container">
    <el-header>
      <div class="header-left">
        <el-button @click="$router.back()" :icon="ArrowLeft" class="nav-btn" />
        <el-button @click="$router.push('/home')" :icon="HomeFilled" class="nav-btn home-nav-btn" />
        <h1>录屏任务</h1>
      </div>
      <div class="header-right">
        <el-dropdown @command="handleCommand">
          <span class="user-info">
            <el-icon><User /></el-icon>
            <span class="username">{{ authStore.user?.username }}</span>
            <el-icon class="el-icon--right"><arrow-down /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="tracks">
                <el-icon><Tickets /></el-icon>
                我的轨迹
              </el-dropdown-item>
              <el-dropdown-item command="settings">
                <el-icon><Setting /></el-icon>
                设置
              </el-dropdown-item>
              <el-dropdown-item command="admin" v-if="authStore.user?.is_admin">
                <el-icon><Setting /></el-icon>
                后台管理
              </el-dropdown-item>
              <el-dropdown-item command="logout">
                <el-icon><SwitchButton /></el-icon>
                退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-header>

    <el-main class="main">
      <el-card class="list-card" shadow="never">
        <!-- 加载中显示骨架屏 -->
        <div v-if="loading" class="skeleton-wrapper">
          <el-skeleton :rows="5" animated class="desktop-only" />
          <div class="mobile-only">
            <div v-for="i in 3" :key="i" class="mobile-card-skeleton">
              <el-skeleton :rows="3" animated />
            </div>
          </div>
        </div>

        <template v-else>
          <!-- 空状态 -->
          <el-empty
            v-if="tasks.length === 0"
            description="还没有录屏任务，在轨迹详情页的动画播放器里点击「导出视频」即可创建"
          />

          <template v-else>
            <!-- PC 端表格 -->
            <el-table
              :data="tasks"
              style="width: 100%"
              class="pc-table"
              row-key="task_id"
              :expand-row-keys="expandedRowKeys"
              @expand-change="handleExpandChange"
            >
              <el-table-column type="expand" width="36">
                <template #default="{ row }">
                  <div v-if="row.status === 'processing' && row.runtime" class="runtime-block">
                    <img
                      v-if="row.runtime.thumbnail_url"
                      :src="thumbnailSrc(row)"
                      class="runtime-thumb"
                      alt="录制画面"
                    />
                    <div class="runtime-info">
                      <div v-if="row.runtime.current_frame != null" class="runtime-line">
                        录制位置：第 <b>{{ row.runtime.current_frame }}</b> / {{ row.runtime.total_frames }} 帧
                      </div>
                      <div v-if="row.runtime.point_index != null" class="runtime-line">
                        轨迹点：第 <b>{{ row.runtime.point_index + 1 }}</b> / {{ row.runtime.total_points }} 个
                      </div>
                      <div v-if="row.runtime.total_time_ms" class="runtime-line">
                        轨迹进度：{{ formatClock(row.runtime.current_time_ms) }} / {{ formatClock(row.runtime.total_time_ms) }}（{{ trackPercent(row.runtime) }}%）
                      </div>
                      <div class="runtime-line">
                        已用时长：{{ formatElapsed(row.runtime.elapsed_seconds) }}
                        <template v-if="row.runtime.eta_seconds != null">
                          · 预计剩余 <b>{{ formatElapsed(row.runtime.eta_seconds) }}</b>
                        </template>
                      </div>
                    </div>
                  </div>
                  <div v-else-if="row.status === 'processing'" class="runtime-line muted">
                    录制准备中，稍后显示实时画面与位置…
                  </div>
                  <div v-else class="runtime-line muted">任务不在录制中</div>
                </template>
              </el-table-column>
              <el-table-column prop="track_title" label="轨迹" min-width="180" show-overflow-tooltip />
              <el-table-column label="状态" width="180">
                <template #default="{ row }">
                  <div class="status-cell">
                    <el-tag :type="statusTagType(row.status)" size="small">
                      {{ statusText(row) }}
                    </el-tag>
                    <el-progress
                      v-if="row.status === 'processing'"
                      :percentage="Math.round(row.progress)"
                      :stroke-width="6"
                      class="status-progress"
                    />
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="创建时间" width="170">
                <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
              </el-table-column>
              <el-table-column label="耗时" width="110">
                <template #default="{ row }">{{ formatDuration(row) }}</template>
              </el-table-column>
              <el-table-column label="操作" width="170" fixed="right">
                <template #default="{ row }">
                  <el-button
                    v-if="row.status === 'completed'"
                    type="primary"
                    size="small"
                    text
                    :icon="Download"
                    @click="handleDownload(row)"
                  >下载</el-button>
                  <el-button
                    v-if="row.status === 'pending' || row.status === 'processing'"
                    type="warning"
                    size="small"
                    text
                    @click="handleCancel(row)"
                  >取消</el-button>
                  <el-button
                    v-if="isFinished(row)"
                    type="danger"
                    size="small"
                    text
                    :icon="Delete"
                    @click="handleDelete(row)"
                  >删除</el-button>
                </template>
              </el-table-column>
            </el-table>

            <!-- 移动端卡片列表 -->
            <div class="mobile-card-list">
              <el-card v-for="task in tasks" :key="task.task_id" class="mobile-task-card" shadow="hover">
                <div class="mobile-card-header">
                  <span class="mobile-track-title">{{ task.track_title || `轨迹 #${task.track_id}` }}</span>
                  <el-tag :type="statusTagType(task.status)" size="small">
                    {{ statusText(task) }}
                  </el-tag>
                </div>
                <el-progress
                  v-if="task.status === 'processing'"
                  :percentage="Math.round(task.progress)"
                  :stroke-width="6"
                />
                <div v-if="task.status === 'processing' && task.runtime" class="mobile-runtime">
                  <img
                    v-if="task.runtime.thumbnail_url"
                    :src="thumbnailSrc(task)"
                    class="runtime-thumb"
                    alt="录制画面"
                  />
                  <div class="runtime-info">
                    <div v-if="task.runtime.current_frame != null" class="runtime-line">
                      第 {{ task.runtime.current_frame }} / {{ task.runtime.total_frames }} 帧
                    </div>
                    <div v-if="task.runtime.point_index != null" class="runtime-line">
                      轨迹点 {{ task.runtime.point_index + 1 }} / {{ task.runtime.total_points }}
                    </div>
                    <div v-if="task.runtime.total_time_ms" class="runtime-line">
                      {{ formatClock(task.runtime.current_time_ms) }} / {{ formatClock(task.runtime.total_time_ms) }}（{{ trackPercent(task.runtime) }}%）
                    </div>
                    <div class="runtime-line">
                      已用 {{ formatElapsed(task.runtime.elapsed_seconds) }}
                      <template v-if="task.runtime.eta_seconds != null">
                        · 剩余约 {{ formatElapsed(task.runtime.eta_seconds) }}
                      </template>
                    </div>
                  </div>
                </div>
                <div v-else-if="task.status === 'processing'" class="runtime-line muted mobile-runtime">
                  录制准备中…
                </div>
                <div class="mobile-card-meta">
                  <span>{{ formatTime(task.created_at) }}</span>
                  <span v-if="formatDuration(task)">耗时 {{ formatDuration(task) }}</span>
                </div>
                <div class="mobile-card-error" v-if="task.status === 'failed' && task.error">
                  {{ task.error }}
                </div>
                <div class="mobile-card-actions">
                  <el-button
                    v-if="task.status === 'completed'"
                    type="primary"
                    size="small"
                    :icon="Download"
                    @click="handleDownload(task)"
                  >下载</el-button>
                  <el-button
                    v-if="task.status === 'pending' || task.status === 'processing'"
                    type="warning"
                    size="small"
                    @click="handleCancel(task)"
                  >取消</el-button>
                  <el-button
                    v-if="isFinished(task)"
                    type="danger"
                    size="small"
                    :icon="Delete"
                    @click="handleDelete(task)"
                  >删除</el-button>
                </div>
              </el-card>
            </div>

            <!-- 分页 -->
            <div class="pagination">
              <el-pagination
                v-model:current-page="page"
                v-model:page-size="pageSize"
                :total="total"
                :page-sizes="[10, 20, 50]"
                layout="total, sizes, prev, pager, next"
                @current-change="loadTasks"
                @size-change="handleSizeChange"
              />
            </div>
          </template>
        </template>
      </el-card>
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft,
  ArrowDown,
  HomeFilled,
  User,
  Tickets,
  Setting,
  SwitchButton,
  Download,
  Delete,
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import {
  animationTaskApi,
  type AnimationExportTask,
  type AnimationTaskStatus,
} from '@/api/animationTask'
import { downloadFile, generateExportFilename } from '@/utils/animation/videoExport'

const router = useRouter()
const authStore = useAuthStore()

const loading = ref(true)
const tasks = ref<AnimationExportTask[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

// ---------- 录制实时状态展示辅助 ----------
// 轮询计数：作为缩略图 URL 的缓存穿透参数
const pollTick = ref(0)

function thumbnailSrc(task: AnimationExportTask): string {
  const url = task.runtime?.thumbnail_url
  if (!url) return ''
  const tok = previewTokens.value.get(task.task_id)
  if (!tok) return ''
  return url + '&download_token=' + encodeURIComponent(tok) + '&t=' + pollTick.value
}

// 展开行受控：轮询整体替换 tasks 数组会重建行对象，非受控时展开状态每 3s 被重置
const expandedRowKeys = ref<string[]>([])
function handleExpandChange(row: AnimationExportTask, expandedRows: AnimationExportTask[]) {
  expandedRowKeys.value = expandedRows.map(r => r.task_id)
}

// <img> 无法携带 Authorization 头：为录制中任务换取任务作用域令牌后拼进缩略图 URL
const previewTokens = ref<Map<string, string>>(new Map())

async function ensurePreviewTokens() {
  const need = tasks.value.filter(
    t => t.status === 'processing' && t.runtime?.thumbnail_url && !previewTokens.value.has(t.task_id)
  )
  if (need.length === 0) return
  const updated = new Map(previewTokens.value)
  await Promise.all(need.map(async t => {
    try {
      const res = await animationTaskApi.createDownloadToken(t.task_id)
      updated.set(t.task_id, res.download_token)
    } catch {
      // 换取失败：本轮不显示缩略图，下轮轮询重试
    }
  }))
  previewTokens.value = updated
}

// 毫秒 → mm:ss / h:mm:ss（轨迹时间进度）
function formatClock(ms?: number | null): string {
  if (ms == null || ms < 0) return '--:--'
  const total = Math.floor(ms / 1000)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const pad = (n: number) => String(n).padStart(2, '0')
  return h > 0 ? h + ':' + pad(m) + ':' + pad(s) : pad(m) + ':' + pad(s)
}

// 秒 → 中文时长（已用/预计剩余）
function formatElapsed(seconds?: number | null): string {
  if (seconds == null || seconds < 0) return '--'
  const total = Math.round(seconds)
  if (total < 60) return total + ' 秒'
  const m = Math.floor(total / 60)
  const s = total % 60
  if (m < 60) return s ? m + ' 分 ' + s + ' 秒' : m + ' 分钟'
  return Math.floor(m / 60) + ' 小时 ' + (m % 60) + ' 分'
}

// 轨迹时间进度百分比
function trackPercent(rt: NonNullable<AnimationExportTask['runtime']>): string {
  if (!rt.total_time_ms) return '--'
  const pct = Math.round(((rt.current_time_ms ?? 0) / rt.total_time_ms) * 100)
  return String(Math.min(100, Math.max(0, pct)))
}

// 存在进行中的任务时轮询刷新
const POLL_INTERVAL = 3000
let pollTimer: ReturnType<typeof setInterval> | null = null

const hasActiveTask = computed(() =>
  tasks.value.some(t => t.status === 'pending' || t.status === 'processing')
)

async function loadTasks() {
  try {
    const result = await animationTaskApi.listMine(page.value, pageSize.value)
    total.value = result.total
    tasks.value = result.items
    pollTick.value++
    void ensurePreviewTokens()
  } catch {
    // 错误已在拦截器中处理
  } finally {
    loading.value = false
  }
  syncPolling()
}

function syncPolling() {
  if (hasActiveTask.value && pollTimer === null) {
    pollTimer = setInterval(() => {
      if (document.hidden) return
      loadTasks()
    }, POLL_INTERVAL)
  } else if (!hasActiveTask.value && pollTimer !== null) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function handleSizeChange() {
  page.value = 1
  loadTasks()
}

function statusTagType(status: AnimationTaskStatus) {
  switch (status) {
    case 'completed': return 'success'
    case 'failed': return 'danger'
    case 'pending': return 'warning'
    case 'processing': return 'primary'
    default: return 'info'
  }
}

function statusText(task: AnimationExportTask): string {
  switch (task.status) {
    case 'pending':
      return task.queue_position && task.queue_position > 1
        ? `排队中 · 第 ${task.queue_position} 位`
        : '排队中'
    case 'processing': return `录制中 ${Math.round(task.progress)}%`
    case 'completed': return '已完成'
    case 'failed': return '失败'
    case 'cancelled': return '已取消'
    case 'expired': return '已过期'
    default: return task.status
  }
}

function isFinished(task: AnimationExportTask): boolean {
  return ['completed', 'failed', 'cancelled', 'expired'].includes(task.status)
}

function formatTime(value?: string | null): string {
  if (!value) return '-'
  const d = new Date(value)
  if (isNaN(d.getTime())) return value
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function formatDuration(task: AnimationExportTask): string {
  if (!task.started_at || !task.finished_at) return ''
  const ms = new Date(task.finished_at).getTime() - new Date(task.started_at).getTime()
  if (!(ms > 0)) return ''
  const totalSec = Math.round(ms / 1000)
  if (totalSec < 60) return `${totalSec}s`
  const min = Math.floor(totalSec / 60)
  const sec = totalSec % 60
  if (min < 60) return `${min}m${sec}s`
  return `${Math.floor(min / 60)}h${min % 60}m`
}

async function handleDownload(task: AnimationExportTask) {
  try {
    await downloadFile(
      `/api/animation/export/${task.task_id}/download`,
      generateExportFilename(task.track_id || 0)
    )
  } catch (e: any) {
    ElMessage.error(`下载失败: ${e.message || '未知错误'}`)
  }
}

async function handleCancel(task: AnimationExportTask) {
  try {
    await ElMessageBox.confirm(
      task.status === 'processing'
        ? '任务正在录制中，确定要取消吗？'
        : '确定要取消这个排队中的任务吗？',
      '取消任务',
      { type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await animationTaskApi.cancelOrDelete(task.task_id)
    ElMessage.success('任务已取消')
    loadTasks()
  } catch {
    // 错误已在拦截器中处理
  }
}

async function handleDelete(task: AnimationExportTask) {
  try {
    await ElMessageBox.confirm(
      task.status === 'completed'
        ? '删除后视频文件将被清除且无法恢复，确定删除吗？'
        : '确定删除这条任务记录吗？',
      '删除任务',
      { type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await animationTaskApi.cancelOrDelete(task.task_id)
    ElMessage.success('删除成功')
    // 删除当前页最后一条后回退一页
    if (tasks.value.length === 1 && page.value > 1) {
      page.value -= 1
    }
    loadTasks()
  } catch {
    // 错误已在拦截器中处理
  }
}

function handleCommand(command: string) {
  switch (command) {
    case 'tracks':
      router.push('/tracks')
      break
    case 'settings':
      router.push('/settings')
      break
    case 'admin':
      router.push('/admin')
      break
    case 'logout':
      authStore.logout()
      router.push('/login')
      break
  }
}

onMounted(loadTasks)

onBeforeUnmount(() => {
  if (pollTimer !== null) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})
</script>

<style scoped>
.recording-tasks-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.recording-tasks-container > .el-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: white;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.nav-btn {
  padding: 8px;
}

.home-nav-btn {
  margin-left: 0;
  margin-right: 12px;
}

.header-left h1 {
  font-size: 20px;
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
  padding: 5px 10px;
  border-radius: 4px;
  transition: background-color 0.3s;
}

.user-info:hover {
  background-color: #f5f7fa;
}

.user-info .username {
  display: inline;
}

.main {
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px;
  width: 100%;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-sizing: border-box;
  overflow-x: hidden;
}

.list-card {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  width: 100%;
  box-sizing: border-box;
}

/* 录制实时状态（PC 展开行 + 移动端卡片共用） */
.runtime-block {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 8px 12px;
}

.runtime-thumb {
  width: 160px;
  height: 90px;
  border-radius: 6px;
  object-fit: cover;
  background: #f0f2f5;
  flex-shrink: 0;
}

.runtime-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.runtime-line {
  font-size: 13px;
  color: #606266;
  line-height: 1.5;
}

.runtime-line b {
  color: #303133;
}

.runtime-line.muted {
  color: #c0c4cc;
}

.mobile-runtime {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-top: 8px;
}

.mobile-runtime .runtime-thumb {
  width: 120px;
  height: 68px;
}

.list-card > :deep(.el-card__body) {
  height: 100%;
  overflow-y: auto;
  padding: 0;
}

.status-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-progress {
  width: 90px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: center;
  flex-shrink: 0;
  padding: 0 2px;
  overflow-x: hidden;
}

.pagination :deep(.el-pagination) {
  flex-wrap: wrap;
  justify-content: center;
}

/* 移动端卡片列表 - 默认隐藏 */
.mobile-card-list {
  display: none;
}

.mobile-only {
  display: none;
}

.pc-table {
  width: 100%;
}

@media (min-width: 1367px) {
  .mobile-card-list {
    display: none !important;
  }
}

/* 移动端响应式 */
@media (max-width: 1366px) {
  .desktop-only {
    display: none !important;
  }

  .mobile-only {
    display: block !important;
  }

  .recording-tasks-container {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    overflow: hidden;
    background: #f5f7fa;
  }

  .recording-tasks-container > .el-header {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    z-index: 1000;
    flex-wrap: wrap;
    background: white;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  }

  .recording-tasks-container > .el-main {
    padding-top: 80px;
    height: 100%;
    background: #f5f7fa;
  }

  .pc-table {
    display: none !important;
  }

  .mobile-card-list {
    display: flex !important;
    flex-direction: column;
    gap: 12px;
    padding: 12px;
  }

  .mobile-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }

  .mobile-track-title {
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .mobile-card-meta {
    display: flex;
    gap: 12px;
    font-size: 13px;
    color: #909399;
    margin-top: 8px;
  }

  .mobile-card-error {
    margin-top: 8px;
    font-size: 12px;
    color: var(--el-color-danger);
    word-break: break-all;
  }

  .mobile-card-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 10px;
  }
}
</style>
