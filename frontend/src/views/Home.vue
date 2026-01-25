<template>
  <el-container class="home-container">
    <!-- 顶部导航栏 -->
    <el-header class="header">
      <div class="header-left">
        <h1 class="logo">Vibe Route</h1>
        <el-button @click="$router.push('/tracks')" :icon="List" class="desktop-only">轨迹列表</el-button>
      </div>
      <div class="header-right">
        <el-button type="primary" :icon="Upload" @click="$router.push('/upload')" class="desktop-only">
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
              <el-dropdown-item command="tracks" v-if="isMobile">
                <el-icon><List /></el-icon>
                轨迹列表
              </el-dropdown-item>
              <el-dropdown-item command="upload" v-if="isMobile">
                <el-icon><Upload /></el-icon>
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

    <!-- 主内容区 -->
    <el-main class="main">
      <!-- 统计卡片 -->
      <el-row :gutter="20" class="stats-row">
        <el-col :xs="12" :sm="6">
          <el-card shadow="hover" class="stat-card" @click="$router.push('/tracks')">
            <div class="stat-card-content">
              <div class="stat-icon" style="background: #409eff">
                <el-icon :size="24"><Location /></el-icon>
              </div>
              <div class="stat-content">
                <div class="stat-value">{{ stats.total_tracks }}</div>
                <div class="stat-label">轨迹总数</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :xs="12" :sm="6">
          <el-card shadow="hover">
            <div class="stat-card-content">
              <div class="stat-icon" style="background: #67c23a">
                <el-icon :size="24"><Odometer /></el-icon>
              </div>
              <div class="stat-content">
                <div class="stat-value">{{ formatDistance(stats.total_distance) }}</div>
                <div class="stat-label">总里程</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :xs="12" :sm="6">
          <el-card shadow="hover">
            <div class="stat-card-content">
              <div class="stat-icon" style="background: #e6a23c">
                <el-icon :size="24"><Clock /></el-icon>
              </div>
              <div class="stat-content">
                <div class="stat-value">{{ formatDuration(stats.total_duration) }}</div>
                <div class="stat-label">总时长</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :xs="12" :sm="6">
          <el-card shadow="hover">
            <div class="stat-card-content">
              <div class="stat-icon" style="background: #f56c6c">
                <el-icon :size="24"><Top /></el-icon>
              </div>
              <div class="stat-content">
                <div class="stat-value">{{ formatElevation(stats.total_elevation_gain) }}</div>
                <div class="stat-label">总爬升</div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 地图 -->
      <el-card class="map-card" shadow="never">
        <template #header>
          <div class="map-header">
            <span v-if="!loadingTracks">所有轨迹</span>
            <span v-else class="loading-title">
              <el-icon class="is-loading"><Loading /></el-icon>
              正在加载所有轨迹……（{{ loadedTrackCount }}/{{ tracks.length }}）
            </span>
          </div>
        </template>
        <div class="map-container">
          <UniversalMap :tracks="tracksWithPoints" mode="home" />
          <div v-if="tracksWithPoints.length === 0 && !loadingTracks" class="map-empty">
            <el-empty description="暂无轨迹数据" :image-size="80" />
          </div>
        </div>
      </el-card>
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  User,
  ArrowDown,
  Setting,
  SwitchButton,
  Location,
  Odometer,
  Clock,
  Top,
  Upload,
  List,
  Loading,
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { trackApi, type Track, type TrackPoint } from '@/api/track'
import UniversalMap from '@/components/map/UniversalMap.vue'

const router = useRouter()
const authStore = useAuthStore()

// 响应式：判断是否为移动端
const screenWidth = ref(window.innerWidth)
const screenHeight = ref(window.innerHeight)
const isMobile = computed(() => screenWidth.value <= 768)

// 标记组件是否已挂载，用于避免卸载后更新状态
let isMounted = true

// 监听窗口大小变化
function handleResize() {
  screenWidth.value = window.innerWidth
  screenHeight.value = window.innerHeight
}

const stats = ref({
  total_tracks: 0,
  total_distance: 0,
  total_duration: 0,
  total_elevation_gain: 0,
})

const tracks = ref<Track[]>([])
const tracksPoints = ref<Map<number, TrackPoint[]>>(new Map())
const loadingTracks = ref(false)
const loadedTrackCount = ref(0)

// 组合轨迹和点数据供地图组件使用
const tracksWithPoints = computed(() => {
  return tracks.value.map(track => ({
    id: track.id,
    name: track.name,
    start_time: track.start_time,
    end_time: track.end_time,
    distance: track.distance,
    duration: track.duration,
    points: tracksPoints.value.get(track.id) || [],
  }))
})

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
  } else if (command === 'tracks') {
    router.push('/tracks')
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

// 采样轨迹点（减少数据量，提高渲染性能）
function samplePoints(points: TrackPoint[], maxPoints: number = 500): TrackPoint[] {
  if (points.length <= maxPoints) return points

  const sampled: TrackPoint[] = []
  const step = Math.ceil(points.length / maxPoints)

  for (let i = 0; i < points.length; i += step) {
    sampled.push(points[i])
  }

  // 确保最后一个点被包含
  if (sampled[sampled.length - 1] !== points[points.length - 1]) {
    sampled.push(points[points.length - 1])
  }

  return sampled
}

// 获取所有轨迹的点数据（限制并发数量，避免阻塞其他请求）
async function fetchAllTracksPoints() {
  if (tracks.value.length === 0) return

  loadingTracks.value = true
  loadedTrackCount.value = 0

  try {
    // 限制并发数量为 3，避免占满 HTTP 连接池
    const concurrency = 3
    let index = 0
    const total = tracks.value.length

    // 使用递归函数来处理并发，每个请求完成后立即更新地图
    async function fetchNext() {
      // 检查组件是否已卸载或所有轨迹都已处理
      if (!isMounted || index >= total) {
        return
      }

      // 获取当前批次
      const batchSize = Math.min(concurrency, total - index)
      const batch = tracks.value.slice(index, index + batchSize)
      index += batchSize

      // 并发请求当前批次的轨迹点
      const promises = batch.map(async (track) => {
        try {
          const response = await trackApi.getPoints(track.id, 'wgs84')
          const points = samplePoints(response.points)

          // 每个请求完成后立即更新地图
          if (isMounted) {
            tracksPoints.value.set(track.id, points)
            loadedTrackCount.value++
          }

          return { success: true }
        } catch (error) {
          console.error(`Failed to load points for track ${track.id}:`, error)
          if (isMounted) {
            loadedTrackCount.value++
          }
          return { success: false }
        }
      })

       // 等待当前批次完成
      await Promise.all(promises)

      // 继续处理下一批
      await fetchNext()
    }

    // 开始获取
    await fetchNext()
  } finally {
    // 只有在组件仍然挂载时才更新 loading 状态
    if (isMounted) {
      loadingTracks.value = false
    }
  }
}

onMounted(() => {
  // 异步获取统计数据，不阻塞页面渲染
  trackApi.getStats()
    .then((data: typeof stats.value) => {
      if (isMounted) stats.value = data
    })
    .catch(() => {
      // 错误已在拦截器中处理
    })

  // 异步获取轨迹列表，不阻塞页面渲染
  trackApi.getList({ page: 1, page_size: 100 })
    .then((response: { items: typeof tracks.value }) => {
      if (isMounted) {
        // 按开始时间排序（从旧到新）
        tracks.value = response.items.sort((a, b) => {
          const timeA = a.start_time ? new Date(a.start_time).getTime() : 0
          const timeB = b.start_time ? new Date(b.start_time).getTime() : 0
          return timeA - timeB
        })
        // 异步获取轨迹点数据
        fetchAllTracksPoints()
      }
    })
    .catch(() => {
      // 错误已在拦截器中处理
    })

  // 添加窗口大小监听
  window.addEventListener('resize', handleResize)
})

// 组件卸载时设置标志，避免更新已卸载组件的状态
onUnmounted(() => {
  isMounted = false
  // 移除窗口大小监听器
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.home-container {
  height: 100%;
  background: #f5f7fa;
  display: flex;
  flex-direction: column;
}

.header {
  background: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  flex-shrink: 0;
  gap: 16px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-left .logo {
  margin: 0;
  font-size: 24px;
  color: #409eff;
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

.mobile-only {
  display: none;
}

:deep(.mobile-only) {
  display: none !important;
}

/* 移动端响应式 */
@media (max-width: 768px) {
  .header {
    flex-wrap: wrap;
    padding: 10px;
  }

  .header-left {
    flex: 1;
    min-width: 0;
  }

  .header-left .logo {
    font-size: 18px;
  }

  .desktop-only {
    display: none !important;
  }

  .user-info .username {
    display: inline;
  }

  .mobile-only {
    display: block !important;
  }
}

.main {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
  height: calc(100vh - 60px); /* 减去导航栏高度 */
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.stats-row {
  margin-bottom: 20px;
  flex-shrink: 0; /* 防止统计卡片被压缩 */
}

.stat-card {
  cursor: pointer;
  transition: box-shadow 0.3s;
}

.stat-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.stat-card-content {
  display: flex;
  align-items: center;
  gap: 15px;
}

.stat-icon {
  width: 50px;
  height: 50px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.stat-content {
  flex: 1;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #333;
}

.stat-label {
  font-size: 14px;
  color: #999;
  margin-top: 5px;
}

.map-card {
  flex: 1; /* 自动填充剩余空间 */
  min-height: 0; /* 允许 flex 子元素缩小 */
  display: flex;
  flex-direction: column;
}

.map-card :deep(.el-card__body) {
  flex: 1;
  padding: 0;
  overflow: hidden;
}

.map-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.map-container {
  width: 100%;
  height: 100%;
  position: relative;
}

.map-empty {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  color: #909399;
}

.loading-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #909399;
}

/* 移动端响应式 */
@media (max-width: 768px) {
  .header {
    flex-wrap: wrap;
    padding: 10px;
  }

  .header-left {
    flex: 1;
    min-width: 0;
  }

  .header-left .logo {
    font-size: 18px;
  }

  .desktop-only {
    display: none;
  }

  .user-info .username {
    display: inline;
  }

  .main {
    padding: 10px;
    height: calc(100vh - 60px); /* 减去导航栏高度 */
  }

  .stats-row {
    margin-bottom: 10px;
  }

  .stats-row :deep(.el-col) {
    margin-bottom: 10px;
  }

  .stats-row :deep(.el-card) {
    height: 100%;
  }

  .stats-row :deep(.el-card__body) {
    min-height: 70px;
    max-height: 80px;
    display: flex;
    align-items: center;
    padding: 10px;
  }

  .stat-icon {
    width: 36px;
    height: 36px;
    flex-shrink: 0;
  }

  .stat-icon :deep(.el-icon) {
    font-size: 18px;
  }

  .stat-value {
    font-size: 16px;
    white-space: nowrap;
  }

  .stat-label {
    font-size: 11px;
    white-space: nowrap;
  }

  .map-card {
    flex: 1;
    min-height: 200px;
  }

  .map-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 5px;
  }

  .map-header span {
    font-size: 14px;
  }
}
</style>