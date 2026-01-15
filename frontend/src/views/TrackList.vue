<template>
  <el-container class="track-list-container">
    <el-header>
      <div class="header-content">
        <el-button @click="$router.push('/')" :icon="ArrowLeft">返回</el-button>
        <h1>我的轨迹</h1>
        <el-button type="primary" :icon="Plus" @click="$router.push('/upload')">
          上传轨迹
        </el-button>
      </div>
    </el-header>

    <el-main class="main">
      <!-- 搜索和筛选 -->
      <el-card class="filter-card" shadow="never">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-input
              v-model="searchQuery"
              placeholder="搜索轨迹名称..."
              :prefix-icon="Search"
              clearable
              @input="handleSearch"
            />
          </el-col>
          <el-col :span="12" style="text-align: right">
            <el-radio-group v-model="sortBy" @change="loadTracks">
              <el-radio-button value="created_at">最新</el-radio-button>
              <el-radio-button value="distance">距离</el-radio-button>
              <el-radio-button value="duration">时长</el-radio-button>
            </el-radio-group>
          </el-col>
        </el-row>
      </el-card>

      <!-- 轨迹列表 -->
      <el-card v-loading="loading" class="list-card" shadow="never">
        <template v-if="tracks.length > 0">
          <el-table :data="tracks" style="width: 100%" @row-click="viewTrack">
            <el-table-column prop="name" label="轨迹名称" min-width="200">
              <template #default="{ row }">
                <el-link :underline="false" @click.stop="viewTrack(row)">
                  {{ row.name }}
                </el-link>
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

          <!-- 分页 -->
          <div class="pagination">
            <el-pagination
              v-model:current-page="currentPage"
              v-model:page-size="pageSize"
              :page-sizes="[10, 20, 50, 100]"
              :total="total"
              layout="total, sizes, prev, pager, next, jumper"
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
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus,
  Search,
  Odometer,
  Clock,
  Top,
  ArrowLeft,
} from '@element-plus/icons-vue'
import { trackApi, type Track } from '@/api/track'

const router = useRouter()

const loading = ref(false)
const tracks = ref<Track[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const searchQuery = ref('')
const sortBy = ref('created_at')

async function loadTracks() {
  loading.value = true
  try {
    const response = await trackApi.getList({
      page: currentPage.value,
      page_size: pageSize.value,
    })
    tracks.value = response.items
    total.value = response.total
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  // TODO: 实现搜索功能
  // 目前只是在前端过滤
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
})
</script>

<style scoped>
.track-list-container {
  height: 100%;
  background: #f5f7fa;
}

.el-header {
  background: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  display: flex;
  align-items: center;
  padding: 0 20px;
}

.header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.header-content h1 {
  font-size: 20px;
  margin: 0;
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

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}
</style>
