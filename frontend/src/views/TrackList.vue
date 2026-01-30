<template>
  <el-container class="track-list-container">
    <el-header>
      <div class="header-left">
        <el-button @click="$router.push('/')" :icon="ArrowLeft" class="nav-btn" />
        <el-button @click="$router.push('/home')" :icon="HomeFilled" class="nav-btn home-nav-btn" />
        <h1>我的轨迹</h1>
      </div>
      <div class="header-right">
        <el-button type="warning" :icon="VideoPlay" @click="openCreateRecordingDialog" class="desktop-only">
          记录实时轨迹
        </el-button>
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
              <el-dropdown-item command="liveRecording" v-if="isMobile">
                <el-icon><VideoPlay /></el-icon>
                记录实时轨迹
              </el-dropdown-item>
              <el-dropdown-item v-if="isMobile" class="dropdown-divider" :disabled="true" />
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
      <el-card class="list-card" shadow="never">
        <!-- 加载中显示骨架屏 -->
        <div v-if="loading" class="skeleton-wrapper">
          <!-- PC端表格骨架屏 -->
          <el-skeleton :rows="5" animated class="desktop-only" />
          <!-- 移动端卡片骨架屏 -->
          <div class="mobile-only">
            <div v-for="i in 3" :key="i" class="mobile-card-skeleton">
              <el-skeleton :rows="3" animated />
            </div>
          </div>
        </div>

        <!-- 加载完成后显示内容 -->
        <template v-else>
          <!-- PC端表格 -->
          <el-table :data="displayItems" style="width: 100%" @row-click="handleRowClick" class="pc-table">
            <el-table-column prop="name" label="名称" min-width="200">
              <template #default="{ row }">
                <div class="name-cell">
                  <el-link underline="never" @click.stop="viewTrack(row)">
                    {{ row.name }}
                  </el-link>

                  <!-- 轨迹进度标签 -->
                  <template v-if="!row.is_live_recording && getFillLabel(row.id)">
                    <el-tag
                      :type="getFillLabel(row.id)!.type"
                      size="small"
                      class="progress-tag"
                    >
                      {{ getFillLabel(row.id)!.text }}
                    </el-tag>
                  </template>

                  <!-- 实时记录状态标签 -->
                  <el-tag v-if="row.id < 0" type="info" size="small">
                    等待上传点
                  </el-tag>
                  <el-tag v-else-if="row.is_live_recording && row.live_recording_status === 'active'" type="success" size="small">
                    {{ (row.last_upload_at || row.last_point_time) ? `实时记录中 · ${formatTimeShortWithRefresh(row.last_point_time || row.last_upload_at)}` : '实时轨迹记录中' }}
                  </el-tag>
                </div>
              </template>
            </el-table-column>

            <el-table-column label="时间" width="180">
              <template #default="{ row }">
                <div class="item-time">
                  {{ formatDateTime(row.start_time || row.created_at) }}
                </div>
              </template>
            </el-table-column>

            <el-table-column label="信息" width="280">
              <template #default="{ row }">
                <div class="track-stats">
                  <!-- 等待上传点 -->
                  <template v-if="row.id < 0">
                    <span class="waiting-info">待记录</span>
                  </template>
                  <!-- 正常显示 -->
                  <template v-else>
                    <span><el-icon><Odometer /></el-icon> {{ formatDistance(row.distance) }}</span>
                    <span><el-icon><Clock /></el-icon> {{ formatDuration(row.duration) }}</span>
                    <span v-if="row.elevation_gain > 0">
                      <el-icon><Top /></el-icon> {{ formatElevation(row.elevation_gain) }}
                    </span>
                  </template>
                </div>
              </template>
            </el-table-column>

            <el-table-column label="操作" width="280" fixed="right">
              <template #default="{ row }">
                <div class="action-buttons">
                  <!-- 普通轨迹操作 -->
                  <template v-if="!row.is_live_recording">
                    <el-button type="primary" size="small" text @click.stop="viewTrack(row)">
                      查看
                    </el-button>
                    <el-button type="danger" size="small" text @click.stop="deleteTrack(row)">
                      删除
                    </el-button>
                  </template>
                  <!-- 实时记录操作 -->
                  <template v-else>
                    <el-button
                      type="primary"
                      size="small"
                      text
                      @click.stop="viewTrack(row)"
                    >
                      查看
                    </el-button>
                    <el-button type="warning" size="small" text @click.stop="showRecordingDetail(row)">
                      记录配置
                    </el-button>
                    <el-button type="danger" size="small" text @click.stop="deleteTrack(row)">
                      删除
                    </el-button>
                  </template>
                </div>
              </template>
            </el-table-column>
          </el-table>

          <!-- 移动端卡片列表 -->
          <div class="mobile-card-list">
            <!-- 统一的轨迹卡片 -->
            <div
              v-for="row in unifiedTracks"
              :key="row.id"
              class="track-card"
              :class="row.is_live_recording ? 'recording-type' : 'track-type'"
              @click="handleRowClick(row)"
            >
              <div class="card-header">
                <div class="track-name">{{ row.name }}</div>
                <!-- 轨迹进度标签 -->
                <template v-if="!row.is_live_recording && getFillLabel(row.id)">
                  <el-tag
                    :type="getFillLabel(row.id)!.type"
                    size="small"
                  >
                    {{ getFillLabel(row.id)!.text }}
                  </el-tag>
                </template>
                <!-- 实时记录状态标签 -->
                <el-tag v-if="row.id < 0" type="info" size="small">
                  等待上传点
                </el-tag>
                <el-tag v-else-if="row.is_live_recording && row.live_recording_status === 'active'" type="success" size="small">
                  {{ (row.last_upload_at || row.last_point_time) ? `实时记录中 · ${formatTimeShortWithRefresh(row.last_point_time || row.last_upload_at)}` : '实时轨迹记录中' }}
                </el-tag>
                <div class="track-time">{{ formatDateTime(row.start_time || row.created_at) }}</div>
              </div>
              <div class="card-body">
                <!-- 等待上传点 -->
                <template v-if="row.id < 0">
                  <div class="card-item">
                    <span class="value waiting-info">待记录</span>
                  </div>
                </template>
                <!-- 正常显示 -->
                <template v-else>
                  <div class="card-stats-row">
                    <span class="stat-item">
                      <el-icon class="stat-icon"><Odometer /></el-icon>
                      {{ formatDistance(row.distance) }}
                    </span>
                    <span class="stat-item">
                      <el-icon class="stat-icon"><Clock /></el-icon>
                      {{ formatDuration(row.duration) }}
                    </span>
                    <span class="stat-item" v-if="row.elevation_gain > 0">
                      <el-icon class="stat-icon"><Top /></el-icon>
                      {{ formatElevation(row.elevation_gain) }}
                    </span>
                  </div>
                </template>
              </div>
              <div class="card-actions" @click.stop>
                <!-- 普通轨迹操作 -->
                <template v-if="!row.is_live_recording">
                  <el-button type="primary" size="small" @click="viewTrack(row)">
                    查看
                  </el-button>
                  <el-button type="danger" size="small" @click="deleteTrack(row)">
                    删除
                  </el-button>
                </template>
                <!-- 实时记录操作 -->
                <template v-else>
                  <el-button
                    type="primary"
                    size="small"
                    @click="viewTrack(row)"
                  >
                    查看
                  </el-button>
                  <el-button type="warning" size="small" @click="showRecordingDetail(row)">
                    记录配置
                  </el-button>
                  <el-button type="danger" size="small" @click="deleteTrack(row)">
                    删除
                  </el-button>
                </template>
              </div>
            </div>
          </div>

          <!-- 空状态 -->
          <el-empty v-if="unifiedTracks.length === 0" description="暂无轨迹和记录">
          <el-button type="primary" @click="$router.push('/upload')">
            上传第一条轨迹
          </el-button>
        </el-empty>
      </template>
      </el-card>

      <!-- 分页（仅轨迹） -->
      <div class="pagination" v-if="unifiedTracks.length > 0">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          :layout="isMobile ? 'prev, pager, next' : 'total, sizes, prev, pager, next, jumper'"
          @current-change="loadTracks"
          @size-change="handleSizeChange"
        />
      </div>
    </el-main>

    <!-- 实时记录详情对话框 -->
    <LiveRecordingDialog
      v-model:visible="recordingDetailVisible"
      :recording-id="currentRecordingId || 0"
      :token="currentRecordingToken || ''"
      :name="currentRecordingName || ''"
      :status="currentRecordingStatus || 'ended'"
      :fill-geocoding="currentRecordingFillGeocoding || false"
      :last-upload-at="currentRecordingLastUploadAt"
      :last-point-time="currentRecordingLastPointTime"
      @ended="loadTracks"
      @fill-geocoding-changed="handleFillGeocodingChanged"
    />

    <!-- 创建实时记录对话框 -->
    <el-dialog v-model="createRecordingDialogVisible" title="创建实时记录" :width="isMobile ? '95%' : '500px'" class="responsive-dialog">
      <el-form :model="createRecordingForm" label-width="100px">
        <el-form-item label="记录名称">
          <el-input v-model="createRecordingForm.name" placeholder="留空则使用当前时间" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createRecordingForm.description" type="textarea" :rows="2" placeholder="可选，记录的描述信息" />
        </el-form-item>
        <el-form-item label="自动填充地理信息">
          <el-switch v-model="createRecordingForm.fill_geocoding" />
          <div class="radio-hint">
            开启后，上传轨迹点时会自动获取省市区、道路名称等地理信息
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="createRecordingDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="createLiveRecording" :loading="creatingRecording">创建</el-button>
      </template>
    </el-dialog>

    <!-- 创建成功对话框（显示 URL 和二维码） -->
    <el-dialog v-model="recordingCreatedDialogVisible" title="实时记录已创建" :width="isMobile ? '95%' : '500px'" class="responsive-dialog">
      <div v-if="createdRecordingData" class="recording-created-content">
        <p class="success-tip">实时记录创建成功！使用以下 URL 上传轨迹：</p>

        <!-- GPS Logger URL -->
        <div class="url-section">
          <div class="url-label">GPS Logger URL：</div>
          <el-input :model-value="createdRecordingData.gpsLoggerUrl" readonly type="textarea" :rows="4" class="url-textarea" />
          <el-button @click="copyCreatedRecordingUrl" :icon="DocumentCopy" type="primary" class="copy-button">
            {{ createdRecordingCopyButtonText }}
          </el-button>
        </div>

        <!-- 二维码 -->
        <div class="qrcode-container" v-if="createdRecordingData.qrCode">
          <div class="qrcode" v-html="createdRecordingData.qrCode"></div>
          <p class="qrcode-tip">扫描二维码查看配置说明</p>
        </div>
      </div>

      <template #footer>
        <el-button @click="recordingCreatedDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </el-container>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, onBeforeUnmount, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus,
  Search,
  Odometer,
  Clock,
  Top,
  ArrowLeft,
  HomeFilled,
  User,
  ArrowDown,
  Setting,
  SwitchButton,
  SortUp,
  SortDown,
  Sort,
  Link,
  Position,
  VideoPlay,
  DocumentCopy,
} from '@element-plus/icons-vue'
import { trackApi, type UnifiedTrack, type AllFillProgressResponse, type FillProgressItem } from '@/api/track'
import { liveRecordingApi } from '@/api/liveRecording'
import { useAuthStore } from '@/stores/auth'
import LiveRecordingDialog from '@/components/LiveRecordingDialog.vue'
import { formatDistance, formatDuration, formatElevation, formatDateTime } from '@/utils/format'
import { formatTimeWithRelative, formatTimeShort } from '@/utils/relativeTime'
import QRCode from 'qrcode'

const router = useRouter()
const authStore = useAuthStore()

// 响应式：判断是否为移动端
const screenWidth = ref(window.innerWidth)
const screenHeight = ref(window.innerHeight)
const isMobile = computed(() => screenWidth.value <= 1366)

// 监听窗口大小变化
function handleResize() {
  screenWidth.value = window.innerWidth
  screenHeight.value = window.innerHeight
}

const loading = ref(false)
const unifiedTracks = ref<UnifiedTrack[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const searchQuery = ref('')
const sortBy = ref('start_time')
const sortOrder = ref<'asc' | 'desc'>('asc')

// 标记组件是否已挂载，用于避免卸载后更新状态
const isMounted = ref(true)

// 实时记录详情对话框（使用 LiveRecordingDialog 组件）
const recordingDetailVisible = ref(false)
const currentRecordingId = ref<number | null>(null)
const currentRecordingToken = ref<string | null>(null)
const currentRecordingName = ref<string | null>(null)
const currentRecordingStatus = ref<'active' | 'ended' | null>(null)
const currentRecordingFillGeocoding = ref<boolean>(false)
const currentRecordingLastUploadAt = ref<string | null>(null)
const currentRecordingLastPointTime = ref<string | null>(null)

// 创建实时记录对话框
const createRecordingDialogVisible = ref(false)
const recordingCreatedDialogVisible = ref(false)
const createRecordingForm = ref({
  name: '',
  description: '',
  fill_geocoding: false,
})
const creatingRecording = ref(false)
const createdRecordingData = ref<{
  gpsLoggerUrl: string
  qrCode: string
} | null>(null)
const createdRecordingCopyButtonText = ref('复制')

// 填充进度数据
const fillProgress = ref<AllFillProgressResponse>({})
let progressTimer: ReturnType<typeof setInterval> | null = null
const PROGRESS_REFRESH_INTERVAL = 2000
// 用于触发相对时间更新的 key
const timeRefreshKey = ref(0)
// 实时记录数据刷新定时器
let liveRecordingsTimer: ReturnType<typeof setInterval> | null = null
const LIVE_RECORDINGS_REFRESH_INTERVAL = 5000 // 每 5 秒刷新一次实时记录数据

// 排序选项
const sortOptions = [
  { label: '最新', value: 'start_time' },
  { label: '距离', value: 'distance' },
  { label: '时长', value: 'duration' },
]

// PC端显示数据（使用统一轨迹列表）
const displayItems = computed(() => {
  return unifiedTracks.value
})

// 获取所有填充进度
async function loadAllProgress() {
  try {
    const data = await trackApi.getAllFillProgress()
    if (!isMounted.value) return
    // 确保 data 是对象类型
    if (data && typeof data === 'object' && !Array.isArray(data)) {
      fillProgress.value = data
    } else {
      fillProgress.value = {}
    }
  } catch (error) {
    // 静默处理错误
  }
  // 更新时间刷新 key，触发相对时间重新计算
  timeRefreshKey.value++
}

// 启动进度轮询
function startProgressPolling() {
  if (progressTimer) return
  loadAllProgress()
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

// 刷新正在记录的轨迹数据
async function refreshLiveRecordings() {
  // 找出所有正在记录的轨迹
  const activeRecordings = unifiedTracks.value.filter(
    t => t.is_live_recording && t.live_recording_status === 'active' && t.live_recording_id
  )

  if (activeRecordings.length === 0) return

  // 并行获取所有正在记录的数据
  const updates = await Promise.allSettled(
    activeRecordings.map(t => liveRecordingApi.getStatus(t.live_recording_id!))
  )

  // 更新对应轨迹的数据
  updates.forEach((result, index) => {
    if (result.status === 'fulfilled' && result.value) {
      const track = activeRecordings[index]
      const status = result.value

      // 从 tracks 数组累加统计数据
      const tracks = status.tracks || []
      const totalDistance = tracks.reduce((sum: number, t: any) => sum + (t.distance || 0), 0)
      const totalDuration = tracks.reduce((sum: number, t: any) => sum + (t.duration || 0), 0)

      // 更新距离、时长等数据
      track.distance = totalDistance
      track.duration = totalDuration
      track.end_time = status.last_point_time || status.last_upload_at
      track.last_upload_at = status.last_upload_at
      track.last_point_time = status.last_point_time
    }
  })
}

// 启动实时记录轮询
function startLiveRecordingsPolling() {
  if (liveRecordingsTimer) return
  refreshLiveRecordings()
  liveRecordingsTimer = setInterval(() => {
    refreshLiveRecordings()
  }, LIVE_RECORDINGS_REFRESH_INTERVAL)
}

// 停止实时记录轮询
function stopLiveRecordingsPolling() {
  if (liveRecordingsTimer) {
    clearInterval(liveRecordingsTimer)
    liveRecordingsTimer = null
  }
}

// 获取轨迹的进度信息
function getTrackProgress(trackId: number): FillProgressItem | null {
  const progress = fillProgress.value[trackId]
  if (!progress) return null

  // 确保 percent 字段存在（后端可能不返回）
  if (typeof progress.percent === 'undefined') {
    const current = progress.current || 0
    const total = progress.total || 0
    return {
      ...progress,
      percent: total > 0 ? Math.floor((current / total) * 100) : 0
    }
  }

  return progress
}

// 获取填充标签的类型和文本
function getFillLabel(trackId: number): { type: string; text: string } | null {
  const progress = getTrackProgress(trackId)
  if (!progress || progress.status !== 'filling') return null

  const { current = 0, failed = 0, percent = 0 } = progress

  // 全部失败（没有成功）
  if (current === 0 && failed > 0) {
    return { type: 'danger', text: '填充有失败' }
  }
  // 部分失败
  if (current > 0 && failed > 0) {
    return { type: 'warning', text: `填充中 ${percent}%（有失败）` }
  }
  // 没有失败
  return { type: 'primary', text: `填充中 ${percent}%` }
}

// 处理每页条数变化
function handleSizeChange() {
  currentPage.value = 1  // 重置到第一页
  loadTracks()
}

async function loadTracks() {
  loading.value = true
  try {
    let actualSortOrder = sortOrder.value
    if (sortBy.value === 'start_time') {
      actualSortOrder = sortOrder.value === 'asc' ? 'desc' : 'asc'
    }

    const response = await trackApi.getUnifiedList({
      page: currentPage.value,
      page_size: pageSize.value,
      search: searchQuery.value || undefined,
      sort_by: sortBy.value,
      sort_order: actualSortOrder,
    })
    if (!isMounted.value) return
    // 确保 items 是数组
    unifiedTracks.value = Array.isArray(response?.items) ? response.items : []
    total.value = response?.total || 0
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    if (isMounted.value) {
      loading.value = false
    }
  }
}

// 搜索输入防抖
let searchTimeout: ReturnType<typeof setTimeout> | null = null
function handleSearchInput() {
  if (searchTimeout) {
    clearTimeout(searchTimeout)
  }
  searchTimeout = setTimeout(() => {
    currentPage.value = 1
    loadTracks()
  }, 500)
}

// 点击排序按钮
function handleSortClick(value: string) {
  if (sortBy.value === value) {
    sortOrder.value = sortOrder.value === 'desc' ? 'asc' : 'desc'
  } else {
    sortBy.value = value
    sortOrder.value = value === 'start_time' ? 'asc' : 'desc'
  }
  loadTracks()
}

function handleRowClick(row: UnifiedTrack) {
  viewTrack(row)
}

function viewTrack(track: UnifiedTrack) {
  // 所有列表项都导航到轨迹详情（包括等待上传点的实时记录）
  router.push(`/tracks/${track.id}`)
}

function deleteTrack(track: UnifiedTrack) {
  const isRecording = track.is_live_recording
  const itemName = isRecording ? '实时记录' : '轨迹'

  ElMessageBox.confirm(
    `确定要删除${itemName} "${track.name}" 吗？此操作不可撤销。`,
    '确认删除',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }
  ).then(async () => {
    try {
      if (isRecording && track.live_recording_id) {
        // 删除实时记录（使用 recording ID）
        await liveRecordingApi.delete(track.live_recording_id)
      } else {
        // 删除普通轨迹
        await trackApi.delete(track.id)
      }
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
  } else if (command === 'liveRecording') {
    openCreateRecordingDialog()
  } else if (command === 'upload') {
    router.push('/upload')
  }
}

// 显示实时记录详情对话框
async function showRecordingDetail(track: UnifiedTrack) {
  if (!track.live_recording_token || !track.live_recording_id) return

  try {
    // 从后端获取最新的实时记录数据
    const recording = await liveRecordingApi.getList('active')
    const currentRecordingData = recording.find(r => r.id === track.live_recording_id)

    currentRecordingId.value = track.live_recording_id
    currentRecordingToken.value = track.live_recording_token
    currentRecordingName.value = track.name
    currentRecordingStatus.value = track.live_recording_status
    currentRecordingFillGeocoding.value = currentRecordingData?.fill_geocoding || track.fill_geocoding || false
    currentRecordingLastUploadAt.value = currentRecordingData?.last_upload_at || null
    currentRecordingLastPointTime.value = currentRecordingData?.last_point_time || null
    recordingDetailVisible.value = true
  } catch (error) {
    ElMessage.error('获取实时记录信息失败')
  }
}

// 处理填充地理信息变更
function handleFillGeocodingChanged(value: boolean) {
  // 更新对应 track 的 fill_geocoding 值
  const track = unifiedTracks.value.find(t => t.live_recording_id === currentRecordingId.value)
  if (track) {
    track.fill_geocoding = value
  }
}

// 打开创建实时记录对话框
function openCreateRecordingDialog() {
  createRecordingForm.value = {
    name: '',
    description: '',
    fill_geocoding: false,
  }
  createRecordingDialogVisible.value = true
}

// 创建实时记录
async function createLiveRecording() {
  // 生成记录名称（如果未填写则使用当前时间）
  let name = createRecordingForm.value.name.trim()
  if (!name) {
    const now = new Date()
    name = `${now.getFullYear()}年${now.getMonth() + 1}月${now.getDate()}日 ${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`
  }

  creatingRecording.value = true
  try {
    const recording = await liveRecordingApi.create({
      name,
      description: createRecordingForm.value.description.trim() || undefined,
      fill_geocoding: createRecordingForm.value.fill_geocoding,
    })

    // 生成 GPS Logger URL
    const gpsLoggerUrl = liveRecordingApi.getGpsLoggerUrl(recording.token)

    // 生成二维码
    const qrCode = await QRCode.toString(gpsLoggerUrl, {
      width: 200,
      margin: 2,
      type: 'svg',
    })

    createdRecordingData.value = {
      gpsLoggerUrl,
      qrCode,
    }

    // 关闭创建对话框，显示成功对话框
    createRecordingDialogVisible.value = false
    recordingCreatedDialogVisible.value = true

    // 刷新轨迹列表
    loadTracks()

    ElMessage.success('记录创建成功')
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    creatingRecording.value = false
  }
}

// 复制创建成功的记录 URL
function copyCreatedRecordingUrl() {
  if (!createdRecordingData.value) return
  const url = createdRecordingData.value.gpsLoggerUrl

  // 检查剪贴板 API 是否可用
  if (!navigator.clipboard) {
    const textarea = document.createElement('textarea')
    textarea.value = url
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()

    try {
      const successful = document.execCommand('copy')
      document.body.removeChild(textarea)
      if (successful) {
        createdRecordingCopyButtonText.value = '已复制'
        ElMessage.success('URL 已复制到剪贴板')
        setTimeout(() => {
          createdRecordingCopyButtonText.value = '复制'
        }, 2000)
      } else {
        ElMessage.error('复制失败，请手动选择复制')
      }
    } catch (err) {
      document.body.removeChild(textarea)
      ElMessage.error('复制失败，请手动选择复制')
      console.error('复制失败:', err)
    }
    return
  }

  navigator.clipboard.writeText(url).then(() => {
    createdRecordingCopyButtonText.value = '已复制'
    ElMessage.success('URL 已复制到剪贴板')
    setTimeout(() => {
      createdRecordingCopyButtonText.value = '复制'
    }, 2000)
  }).catch((err) => {
    const isSecureContext = window.isSecureContext
    if (!isSecureContext) {
      ElMessage.warning('剪贴板 API 需要 HTTPS 环境，请手动选择复制')
    } else {
      ElMessage.error('复制失败，请手动复制')
    }
    console.error('复制失败:', err)
  })
}

// 复制记录 URL（保留用于其他可能的调用）
function copyRecordingUrl(track: UnifiedTrack) {
  if (!track.live_recording_token) return
  const url = liveRecordingApi.getFullUploadUrl(track.live_recording_token)
  navigator.clipboard.writeText(url).then(() => {
    ElMessage.success('链接已复制到剪贴板')
  }).catch(() => {
    ElMessage.error('复制失败，请手动复制')
  })
}

// 显示二维码（保留用于其他可能的调用）
async function showRecordingQrCode(track: UnifiedTrack) {
  showRecordingDetail(track)
}

// 结束记录（保留用于其他可能的调用）
function endRecording(track: UnifiedTrack) {
  ElMessageBox.confirm(
    `确定要结束记录 "${track.name}" 吗？结束后将无法继续上传轨迹。`,
    '确认结束',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }
  ).then(async () => {
    try {
      await liveRecordingApi.end(track.live_recording_id!)
      ElMessage.success('记录已结束')
      loadTracks()
    } catch (error) {
      // 错误已在拦截器中处理
    }
  })
}

// 格式化更新时间（依赖 timeRefreshKey 以触发刷新）
function formatTimeShortWithRefresh(timeStr: string | null | undefined): string {
  // 依赖 timeRefreshKey，确保定时触发重新计算
  void timeRefreshKey.value
  return formatTimeShort(timeStr)
}

onMounted(async () => {
  await loadTracks()
  startProgressPolling()
  startLiveRecordingsPolling()
  window.addEventListener('resize', handleResize)
})

// 组件即将卸载时设置标志
onBeforeUnmount(() => {
  isMounted.value = false
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  stopProgressPolling()
  stopLiveRecordingsPolling()
})
</script>

<style scoped>
.track-list-container {
  height: 100vh;
  background: #f5f7fa;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  overflow-x: hidden;
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
  flex-shrink: 0;
  gap: 16px;
}

.track-list-container > .el-main {
  flex: 1;
  overflow: hidden;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
}

/* 下拉菜单分割线 */
.dropdown-divider {
  margin: 4px 0;
  height: 1px;
  padding: 0;
  overflow: hidden;
  line-height: 0;
  background-color: var(--el-border-color-lighter);
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
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-sizing: border-box;
  overflow-x: hidden;
}

.filter-card {
  margin-bottom: 20px;
  flex-shrink: 0;
}

.sort-col {
  display: flex;
  align-items: center;
  justify-content: flex-end;
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
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  width: 100%;
  box-sizing: border-box;
}

.list-card :deep(.el-card__body) {
  height: 100%;
  overflow-y: scroll;
  padding: 0;
}

:deep(.el-table__row) {
  cursor: pointer;
}

:deep(.el-table__row:hover) {
  background-color: #f5f7fa;
}

.item-time {
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

.name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.progress-tag {
  flex-shrink: 0;
}

.upload-time-tag {
  flex-shrink: 0;
  font-size: 11px;
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

/* PC 端表格样式 */
.pc-table {
  width: 100%;
}

/* PC 端显示表格，隐藏移动端卡片 */
@media (min-width: 1367px) {
  .mobile-card-list {
    display: none !important;
  }

  .pc-table {
    display: table !important;
  }
}

/* 移动端响应式 */
@media (max-width: 1366px) {
  .track-list-container {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    overflow: hidden;
    background: #f5f7fa;
  }

  .track-list-container > .el-header {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    z-index: 1000;
    flex-wrap: wrap;
    background: white;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  }

  .track-list-container > .el-main {
    padding-top: 80px;
    height: 100%;
    background: #f5f7fa;
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
    padding: 0;
    background: #f5f7fa;
  }

  :deep(.el-main) {
    background: #f5f7fa;
  }

  .filter-card {
    margin-bottom: 10px;
    flex-shrink: 0;
    padding: 0 10px;
  }

  .filter-card :deep(.el-card__body) {
    padding: 15px 10px;
  }

  .sort-col {
    text-align: left;
    margin-top: 10px;
  }

  .pc-table {
    display: none;
  }

  .mobile-card-list {
    display: block;
  }

  .track-stats {
    flex-wrap: wrap;
  }

  .mobile-card-list {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: 10px;
    /* Android Edge 等浏览器的工具栏很高，需要更多底部空间 */
    padding-bottom: calc(160px + env(safe-area-inset-bottom, 0px));
  }

  .list-card {
    flex: 1;
    min-height: 0;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    margin: 0;
    border: none;
    box-shadow: none;
    background: transparent;
  }

  .list-card :deep(.el-card__body) {
    flex: 1;
    min-height: 0;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    padding: 0;
  }

  .pagination {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 100;
    background: #f5f7fa;
    padding: 10px;
    padding-bottom: max(10px, env(safe-area-inset-bottom));
    box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.1);
    margin-top: 0;
  }

  .pagination :deep(.el-pagination) {
    justify-content: center;
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

/* 实时记录卡片特殊样式 */
.recording-type {
  border-left: 4px solid #67c23a;
  cursor: default;
}

.recording-type:hover {
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.track-type {
  border-left: 4px solid #409eff;
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
  margin-bottom: 12px;
}

.card-stats-row {
  display: flex;
  gap: 16px;
  align-items: center;
  flex-wrap: wrap;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  color: #606266;
}

.stat-icon {
  font-size: 16px;
  color: #909399;
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

<style>
@media (max-width: 1366px) {
  .track-list-container::before {
    content: '';
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: #f5f7fa;
    z-index: -1;
    height: 100vh;
    height: -webkit-fill-available;
  }

  body {
    background: #f5f7fa !important;
  }

  #app {
    background: #f5f7fa !important;
  }
}

/* 实时记录详情对话框 */
.recording-detail-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.recording-status {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-label {
  font-weight: 500;
  color: var(--el-text-color-regular);
}

.status-value {
  color: var(--el-text-color-primary);
}

.url-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.url-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-regular);
}

.url-textarea {
  font-family: monospace;
}

.copy-button {
  align-self: flex-start;
}

/* 最近上传信息区域 */
.upload-info-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
  margin: 12px 0;
}

.upload-info-section .info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.upload-info-section .info-label {
  font-size: 14px;
  color: var(--el-text-color-regular);
}

.upload-info-section .info-value {
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

/* 设置区域 */
.setting-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}

.setting-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.setting-label {
  font-size: 14px;
  color: var(--el-text-color-regular);
}

.setting-tip {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-left: 0;
}

/* 操作区域 */
.action-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* 二维码 */
.qrcode-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 20px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}

.qrcode {
  display: flex;
}

.qrcode :deep(svg) {
  width: 200px;
  height: 200px;
}

.qrcode-tip {
  margin: 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

/* 创建成功对话框 */
.recording-created-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.success-tip {
  margin: 0 0 10px 0;
  font-size: 14px;
  color: var(--el-text-color-regular);
}

.action-tip {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  text-align: center;
}

/* 骨架屏样式 */
.skeleton-wrapper {
  padding: 20px;
}

.mobile-card-skeleton {
  padding: 16px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.mobile-card-skeleton:last-child {
  border-bottom: none;
}
</style>
