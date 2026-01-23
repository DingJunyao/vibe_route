<template>
  <el-container class="track-list-container">
    <el-header>
      <div class="header-left">
        <el-button @click="$router.push('/')" :icon="ArrowLeft">返回</el-button>
        <h1>我的轨迹</h1>
      </div>
      <div class="header-right">
        <el-button type="primary" :icon="Plus" @click="$router.push('/upload')" class="desktop-only">
          上传轨迹
        </el-button>
        <el-dropdown @command="handleCommand">
          <span class="user-info">
            <el-icon><User /></el-icon>
            <span class="username">{{ authStore.user?.username }}</span>
            <el-icon class="el-icon--right"><arrow-down /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="upload" v-if="isMobile">
                <el-icon><Plus /></el-icon>
                上传轨迹
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
      <!-- 搜索和筛选 -->
      <el-card class="filter-card" shadow="never">
        <el-row :gutter="20">
          <el-col :xs="24" :sm="12">
            <el-input
              v-model="searchQuery"
              placeholder="搜索轨迹名称..."
              :prefix-icon="Search"
              clearable
              @input="handleSearchInput"
            />
          </el-col>
          <el-col :xs="24" :sm="12" class="sort-col">
            <div class="sort-buttons">
              <el-button
                v-for="item in sortOptions"
                :key="item.value"
                :type="sortBy === item.value ? 'primary' : ''"
                @click="handleSortClick(item.value)"
              >
                {{ item.label }}
                <el-icon v-if="sortBy === item.value" class="sort-icon">
                  <component :is="sortOrder === 'desc' ? SortDown : SortUp" />
                </el-icon>
              </el-button>
            </div>
          </el-col>
        </el-row>
      </el-card>

      <!-- PC端表格列表 -->
      <el-card v-loading="loading" class="list-card" shadow="never">
        <template v-if="tracks.length > 0">
          <!-- PC端表格 -->
          <el-table :data="tracks" style="width: 100%" @row-click="viewTrack" class="pc-table">
            <el-table-column prop="name" label="轨迹名称" min-width="200">
              <template #default="{ row }">
                <div class="track-name-cell">
                  <el-link :underline="false" @click.stop="viewTrack(row)">
                    {{ row.name }}
                  </el-link>
                  <template v-if="getTrackProgress(row.id)">
                    <el-tag
                      v-if="getTrackProgress(row.id)!.status === 'filling'"
                      type="primary"
                      size="small"
                      class="progress-tag"
                    >
                      填充中 {{ getTrackProgress(row.id)!.percent }}%
                    </el-tag>
                    <el-tag
                      v-else-if="getTrackProgress(row.id)!.status === 'failed'"
                      type="danger"
                      size="small"
                      class="progress-tag"
                    >
                      填充失败
                    </el-tag>
                  </template>
                </div>
              </template>
            </el-table-column>

            <el-table-column label="时间" width="180">
              <template #default="{ row }">
                <div class="track-time">
                  {{ formatDateTime(row.start_time) }}
                </div>
              </template>
            </el-table-column>

            <el-table-column label="统计信息" width="280">
              <template #default="{ row }">
                <div class="track-stats">
                  <span><el-icon><Odometer /></el-icon> {{ formatDistance(row.distance) }}</span>
                  <span><el-icon><Clock /></el-icon> {{ formatDuration(row.duration) }}</span>
                  <span v-if="row.elevation_gain > 0">
                    <el-icon><Top /></el-icon> {{ formatElevation(row.elevation_gain) }}
                  </span>
                </div>
              </template>
            </el-table-column>

            <el-table-column label="操作" width="130" fixed="right">
              <template #default="{ row }">
                <div class="action-buttons">
                  <el-button
                    type="primary"
                    size="small"
                    text
                    @click.stop="viewTrack(row)"
                  >
                    查看
                  </el-button>
                  <el-button
                    type="danger"
                    size="small"
                    text
                    @click.stop="deleteTrack(row)"
                  >
                    删除
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>

          <!-- 移动端卡片列表 -->
          <div class="mobile-card-list">
            <div v-for="row in tracks" :key="row.id" class="track-card" @click="viewTrack(row)">
              <div class="card-header">
                <div class="track-name">{{ row.name }}</div>
                <div class="track-time">{{ formatDateTime(row.start_time) }}</div>
              </div>
              <div class="card-body">
                <div class="card-item">
                  <span class="label">里程</span>
                  <span class="value">{{ formatDistance(row.distance) }}</span>
                </div>
                <div class="card-item">
                  <span class="label">时长</span>
                  <span class="value">{{ formatDuration(row.duration) }}</span>
                </div>
                <div class="card-item" v-if="getTrackProgress(row.id)">
                  <span class="label">状态</span>
                  <span class="value">
                    <el-tag
                      v-if="getTrackProgress(row.id)!.status === 'filling'"
                      type="primary"
                      size="small"
                    >
                      填充中 {{ getTrackProgress(row.id)!.percent }}%
                    </el-tag>
                    <el-tag
                      v-else-if="getTrackProgress(row.id)!.status === 'failed'"
                      type="danger"
                      size="small"
                    >
                      填充失败
                    </el-tag>
                  </span>
                </div>
              </div>
              <div class="card-actions" @click.stop>
                <el-button type="primary" size="small" @click="viewTrack(row)">
                  查看
                </el-button>
                <el-button type="danger" size="small" @click="deleteTrack(row)">
                  删除
                </el-button>
              </div>
            </div>
          </div>

          <!-- 分页 -->
          <div class="pagination">
            <el-pagination
              v-model:current-page="currentPage"
              v-model:page-size="pageSize"
              :page-sizes="[10, 20, 50, 100]"
              :total="total"
              :layout="isMobile ? 'prev, pager, next' : 'total, sizes, prev, pager, next, jumper'"
              @current-change="loadTracks"
              @size-change="loadTracks"
            />
          </div>
        </template>

        <!-- 空状态 -->
        <el-empty v-else description="暂无轨迹，请先上传">
          <el-button type="primary" @click="$router.push('/upload')">
            上传第一条轨迹
          </el-button>
        </el-empty>
      </el-card>
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus,
  Search,
  Odometer,
  Clock,
  Top,
  ArrowLeft,
  User,
  ArrowDown,
  Setting,
  SwitchButton,
  SortUp,
  SortDown,
} from '@element-plus/icons-vue'
import { trackApi, type Track, type AllFillProgressResponse, type FillProgressItem } from '@/api/track'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

// 响应式：判断是否为移动端
const screenWidth = ref(window.innerWidth)
const isMobile = computed(() => screenWidth.value <= 768)

// 监听窗口大小变化
function handleResize() {
  screenWidth.value = window.innerWidth
}

const loading = ref(false)
const tracks = ref<Track[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const searchQuery = ref('')
const sortBy = ref('start_time')
const sortOrder = ref<'asc' | 'desc'>('asc')  // 初始为正序图标，表示从新到旧

// 填充进度数据
const fillProgress = ref<AllFillProgressResponse>({})
let progressTimer: ReturnType<typeof setInterval> | null = null
const PROGRESS_REFRESH_INTERVAL = 2000  // 2秒刷新一次

// 排序选项
const sortOptions = [
  { label: '最新', value: 'start_time' },
  { label: '距离', value: 'distance' },
  { label: '时长', value: 'duration' },
]

// 获取所有填充进度
async function loadAllProgress() {
  try {
    const data = await trackApi.getAllFillProgress()
    fillProgress.value = data
  } catch (error) {
    // 静默处理错误
  }
}

// 启动进度轮询
function startProgressPolling() {
  if (progressTimer) return
  // 立即加载一次
  loadAllProgress()
  // 定时刷新
  progressTimer = setInterval(() => {
    loadAllProgress()
  }, PROGRESS_REFRESH_INTERVAL)
}

// 停止进度轮询
function stopProgressPolling() {
  if (progressTimer) {
    clearInterval(progressTimer)
    progressTimer = null
  }
}

// 获取轨迹的进度信息
function getTrackProgress(trackId: number): FillProgressItem | null {
  return fillProgress.value[trackId] || null
}

// 检查是否有正在填充的轨迹
function hasFillingTracks(): boolean {
  return Object.values(fillProgress.value).some(
    p => p.status === 'filling'
  )
}

async function loadTracks() {
  loading.value = true
  try {
    // 对于 start_time 字段，反转排序方向以符合用户习惯
    // start_time: 正序图标(asc)表示从新到旧，倒序图标(desc)表示从旧到新
    let actualSortOrder = sortOrder.value
    if (sortBy.value === 'start_time') {
      actualSortOrder = sortOrder.value === 'asc' ? 'desc' : 'asc'
    }

    const response = await trackApi.getList({
      page: currentPage.value,
      page_size: pageSize.value,
      search: searchQuery.value || undefined,
      sort_by: sortBy.value,
      sort_order: actualSortOrder,
    })
    tracks.value = response.items
    total.value = response.total
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    loading.value = false
  }
}

// 搜索输入防抖
let searchTimeout: ReturnType<typeof setTimeout> | null = null
function handleSearchInput() {
  if (searchTimeout) {
    clearTimeout(searchTimeout)
  }
  searchTimeout = setTimeout(() => {
    currentPage.value = 1  // 搜索时重置到第一页
    loadTracks()
  }, 500)
}

// 点击排序按钮
function handleSortClick(value: string) {
  if (sortBy.value === value) {
    // 点击当前排序字段，切换排序方向
    sortOrder.value = sortOrder.value === 'desc' ? 'asc' : 'desc'
  } else {
    // 切换到新的排序字段
    sortBy.value = value
    // 对于"最新"，使用 asc（正序图标，表示从新到旧）
    // 对于"距离"和"时长"，使用 desc（倒序，表示从大到小）
    sortOrder.value = value === 'start_time' ? 'asc' : 'desc'
  }
  loadTracks()
}

function viewTrack(track: Track) {
  router.push(`/tracks/${track.id}`)
}

function deleteTrack(track: Track) {
  ElMessageBox.confirm(
    `确定要删除轨迹 "${track.name}" 吗？此操作不可撤销。`,
    '确认删除',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }
  ).then(async () => {
    try {
      await trackApi.delete(track.id)
      ElMessage.success('删除成功')
      loadTracks()
    } catch (error) {
      // 错误已在拦截器中处理
    }
  })
}

function handleCommand(command: string) {
  if (command === 'logout') {
    ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }).then(() => {
      authStore.logout()
      ElMessage.success('已退出登录')
      router.push('/login')
    })
  } else if (command === 'admin') {
    router.push('/admin')
  } else if (command === 'upload') {
    router.push('/upload')
  }
}

function formatDistance(meters: number): string {
  if (meters < 1000) {
    return `${meters.toFixed(1)} m`
  }
  return `${(meters / 1000).toFixed(2)} km`
}

function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (hours > 0) {
    return `${hours}h ${minutes}m`
  }
  return `${minutes}m`
}

function formatElevation(meters: number): string {
  return `${meters.toFixed(0)} m`
}

function formatDateTime(dateStr: string | null): string {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  const year = date.getFullYear()
  const month = (date.getMonth() + 1).toString().padStart(2, '0')
  const day = date.getDate().toString().padStart(2, '0')
  const hours = date.getHours().toString().padStart(2, '0')
  const minutes = date.getMinutes().toString().padStart(2, '0')
  const seconds = date.getSeconds().toString().padStart(2, '0')
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
}

onMounted(async () => {
  await loadTracks()
  // 启动进度轮询
  startProgressPolling()

  // 添加窗口大小监听
  window.addEventListener('resize', handleResize)
})

// 组件卸载时移除监听器
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  stopProgressPolling()  // 停止进度轮询
})
</script>

<style scoped>
.track-list-container {
  height: 100vh;
  overflow-y: auto;
  background: #f5f7fa;
  display: block;
}

.track-list-container > .el-header {
  position: sticky;
  top: 0;
  z-index: 1000;
  background: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  flex-shrink: 0;
  gap: 16px;
}

.track-list-container > .el-main {
  overflow: visible;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: 1;
  min-width: 0;
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
}

.filter-card {
  margin-bottom: 20px;
}

.sort-col {
  display: flex;
  align-items: center;
}

.sort-buttons {
  display: flex;
  gap: 4px;
  width: 100%;
}

.sort-buttons .el-button {
  flex: 1;
}

.sort-icon {
  margin-left: 4px;
  font-size: 14px;
}

.list-card {
  min-height: 400px;
}

:deep(.el-table__row) {
  cursor: pointer;
}

:deep(.el-table__row:hover) {
  background-color: #f5f7fa;
}

.track-time {
  font-size: 13px;
  color: #606266;
}

.track-stats {
  display: flex;
  gap: 12px;
  font-size: 13px;
  color: #606266;
}

.track-stats span {
  display: flex;
  align-items: center;
  gap: 4px;
}

.action-buttons {
  display: flex;
  gap: 4px;
  align-items: center;
}

.track-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.progress-tag {
  flex-shrink: 0;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}

/* 移动端卡片列表 - 默认隐藏 */
.mobile-card-list {
  display: none;
}

.desktop-only {
  display: inline-block;
}

/* 移动端响应式 */
@media (max-width: 768px) {
  .el-header {
    flex-wrap: wrap;
    padding: 10px;
  }

  .header-left {
    flex: 1;
    min-width: 0;
  }

  .header-left h1 {
    font-size: 16px;
  }

  .desktop-only {
    display: none !important;
  }

  .user-info .username {
    display: inline;
  }

  .main {
    padding: 10px;
  }

  .sort-col {
    text-align: left;
    margin-top: 10px;
  }

  /* 隐藏PC端表格 */
  .pc-table {
    display: none;
  }

  /* 显示移动端卡片 */
  .mobile-card-list {
    display: block;
  }

  .track-stats {
    flex-wrap: wrap;
  }
}

.track-card {
  background: white;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  transition: box-shadow 0.3s;
}

.track-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.card-header {
  margin-bottom: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.track-name {
  font-size: 16px;
  font-weight: 500;
  color: #303133;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.track-card .track-time {
  font-size: 12px;
  color: #909399;
  white-space: nowrap;
}

.card-body {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px 16px;
  margin-bottom: 12px;
}

.card-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-item .label {
  font-size: 12px;
  color: #909399;
}

.card-item .value {
  font-size: 14px;
  color: #606266;
}

.card-actions {
  display: flex;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid #ebeef5;
}

.card-actions .el-button {
  flex: 1;
}

/* 防止移动端拖动卡片 */
.mobile-card-list {
  touch-action: pan-y pinch-zoom;
}

.track-card {
  touch-action: pan-y pinch-zoom;
  user-select: none;
  -webkit-user-select: none;
  -webkit-touch-callout: none;
}
</style>
