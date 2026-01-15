<template>
  <el-container class="home-container">
    <!-- 顶部导航栏 -->
    <el-header class="header">
      <div class="header-left">
        <h1 class="logo">Vibe Route</h1>
      </div>
      <div class="header-right">
        <el-dropdown @command="handleCommand">
          <span class="user-info">
            <el-icon><User /></el-icon>
            {{ authStore.user?.username }}
            <el-icon class="el-icon--right"><arrow-down /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="admin" v-if="authStore.user?.is_admin">
                <el-icon><Setting /></el-icon>
                后台管理
              </el-dropdown-item>
              <el-dropdown-item command="logout" divided>
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
        <el-col :span="6">
          <el-card shadow="hover">
            <div class="stat-card">
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
        <el-col :span="6">
          <el-card shadow="hover">
            <div class="stat-card">
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
        <el-col :span="6">
          <el-card shadow="hover">
            <div class="stat-card">
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
        <el-col :span="6">
          <el-card shadow="hover">
            <div class="stat-card">
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
            <span>所有轨迹</span>
            <div class="map-actions">
              <el-button size="small" @click="$router.push('/upload')">
                <el-icon><Upload /></el-icon>
                上传轨迹
              </el-button>
              <el-button size="small" @click="$router.push('/tracks')">
                <el-icon><List /></el-icon>
                轨迹列表
              </el-button>
            </div>
          </div>
        </template>
        <div class="map-container">
          <LeafletMap :tracks="tracksWithPoints" />
          <div v-if="loadingTracks" class="map-loading">
            <el-icon class="is-loading"><Loading /></el-icon>
            <span>加载轨迹中...</span>
          </div>
          <div v-else-if="tracksWithPoints.length === 0" class="map-empty">
            <el-empty description="暂无轨迹数据" :image-size="80" />
          </div>
        </div>
      </el-card>
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
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
import LeafletMap from '@/components/map/LeafletMap.vue'

const router = useRouter()
const authStore = useAuthStore()

const stats = ref({
  total_tracks: 0,
  total_distance: 0,
  total_duration: 0,
  total_elevation_gain: 0,
})

const tracks = ref<Track[]>([])
const tracksPoints = ref<Map<number, TrackPoint[]>>(new Map())
const loadingTracks = ref(false)

// 组合轨迹和点数据供地图组件使用
const tracksWithPoints = computed(() => {
  return tracks.value.map(track => ({
    id: track.id,
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

// 获取所有轨迹的点数据
async function fetchAllTracksPoints() {
  if (tracks.value.length === 0) return

  loadingTracks.value = true

  try {
    // 并发获取所有轨迹的点数据
    const promises = tracks.value.map(async (track) => {
      try {
        const response = await trackApi.getPoints(track.id, 'wgs84')
        return { trackId: track.id, points: samplePoints(response.points) }
      } catch (error) {
        console.error(`Failed to load points for track ${track.id}:`, error)
        return { trackId: track.id, points: [] }
      }
    })

    const results = await Promise.all(promises)

    // 存储结果
    for (const result of results) {
      tracksPoints.value.set(result.trackId, result.points)
    }
  } finally {
    loadingTracks.value = false
  }
}

onMounted(async () => {
  // 获取统计数据
  try {
    stats.value = await trackApi.getStats()
  } catch (error) {
    // 错误已在拦截器中处理
  }

  // 获取轨迹列表
  try {
    const response = await trackApi.getList({ page: 1, page_size: 100 })
    tracks.value = response.items

    // 获取轨迹点数据
    await fetchAllTracksPoints()
  } catch (error) {
    // 错误已在拦截器中处理
  }
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
}

.header-left .logo {
  margin: 0;
  font-size: 24px;
  color: #409eff;
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

.main {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
  flex: 1;
  overflow-y: auto;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
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
  height: calc(100% - 140px);
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

.map-actions {
  display: flex;
  gap: 10px;
}

.map-container {
  width: 100%;
  height: 100%;
  position: relative;
}

.map-loading,
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

.map-loading .el-icon {
  font-size: 32px;
}
</style>
