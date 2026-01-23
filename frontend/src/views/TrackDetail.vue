<template>
  <div class="track-detail-container">
    <el-header>
      <div class="header-left">
        <el-button @click="$router.back()" :icon="ArrowLeft">返回</el-button>
        <h1>{{ track?.name || '轨迹详情' }}</h1>
      </div>
      <div class="header-right">
        <div class="header-actions">
          <el-button type="primary" @click="showEditDialog" class="desktop-only">
            <el-icon><Edit /></el-icon>
            编辑
          </el-button>
          <el-button type="primary" @click="downloadDialogVisible = true" class="desktop-only">
            <el-icon><Download /></el-icon>
            下载 GPX
          </el-button>
          <el-button
            type="primary"
            @click="handleFillGeocoding"
            class="desktop-only"
            :loading="fillingGeocoding"
            :disabled="fillProgress.status === 'filling'"
            v-if="!track?.has_area_info || !track?.has_road_info"
          >
            <el-icon><LocationFilled /></el-icon>
            填充地理信息
          </el-button>
        </div>
        <el-dropdown @command="handleCommand">
          <span class="user-info">
            <el-icon><User /></el-icon>
            <span class="username">{{ authStore.user?.username }}</span>
            <el-icon class="el-icon--right"><arrow-down /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="edit" v-if="isMobile">
                <el-icon><Edit /></el-icon>
                编辑
              </el-dropdown-item>
              <el-dropdown-item command="download" v-if="isMobile">
                <el-icon><Download /></el-icon>
                下载 GPX
              </el-dropdown-item>
              <el-dropdown-item
                command="fill"
                v-if="isMobile && (!track?.has_area_info || !track?.has_road_info)"
                :disabled="fillProgress.status === 'filling'"
              >
                <el-icon><LocationFilled /></el-icon>
                {{ fillProgress.status === 'filling' ? '填充中...' : '填充地理信息' }}
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

    <el-main class="main" v-loading="loading">
      <!-- 调试信息 -->
      <el-alert v-if="!track" type="error" :closable="false" style="margin-bottom: 20px">
        轨迹数据加载失败，请返回列表重试
      </el-alert>

      <template v-if="track">
        <el-row :gutter="20">
          <!-- 左侧：地图和统计 -->
          <el-col :xs="24" :md="16">
            <!-- 地图 -->
            <el-card class="map-card" shadow="never">
              <template v-if="trackWithPoints">
                <!-- <div style="background: #e5e5e5; padding: 10px; font-size: 12px; color: #666;">
                  调试: trackWithPoints 存在，轨迹点数: {{ trackWithPoints.points.length }}
                </div> -->
                <div style="height: 500px; position: relative;">
                  <UniversalMap
                    ref="mapRef"
                    :tracks="[trackWithPoints]"
                    :highlight-track-id="track.id"
                    @point-hover="handleMapPointHover"
                  />
                </div>
              </template>
              <template v-else>
                <div class="map-placeholder">
                  <p>{{ points.length === 0 ? '正在加载轨迹点数据...' : '轨迹点坐标数据无效' }}</p>
                  <p v-if="points.length > 0" class="debug-info">
                    轨迹点数量: {{ points.length }}，
                    有效坐标: {{ points.filter(p => p.latitude_wgs84 != null && p.longitude_wgs84 != null).length }}
                  </p>
                  <el-button size="small" @click="$router.push('/upload')">上传新轨迹</el-button>
                </div>
              </template>
            </el-card>

            <!-- 海拔和速度图表 -->
            <el-card class="chart-card" shadow="never">
              <template #header>
                <span>海拔与速度变化</span>
              </template>
              <div ref="chartRef" class="chart"></div>
            </el-card>
          </el-col>

          <!-- 右侧：轨迹点和信息 -->
          <el-col :xs="24" :md="8">
            <!-- 统计信息 -->
            <el-card class="stats-card" shadow="never">
              <template #header>
                <span>轨迹统计</span>
              </template>
              <el-row :gutter="20">
                <el-col :span="12">
                  <div class="stat-item">
                    <el-icon class="stat-icon" color="#409eff"><Odometer /></el-icon>
                    <div class="stat-content">
                      <div class="stat-value">{{ formatDistance(track.distance) }}</div>
                      <div class="stat-label">总里程</div>
                    </div>
                  </div>
                </el-col>
                <el-col :span="12">
                  <div class="stat-item">
                    <el-icon class="stat-icon" color="#67c23a"><Clock /></el-icon>
                    <div class="stat-content">
                      <div class="stat-value">{{ formatDuration(track.duration) }}</div>
                      <div class="stat-label">总时长</div>
                    </div>
                  </div>
                </el-col>
                <el-col :span="12">
                  <div class="stat-item">
                    <el-icon class="stat-icon" color="#e6a23c"><Top /></el-icon>
                    <div class="stat-content">
                      <div class="stat-value">{{ formatElevation(track.elevation_gain) }}</div>
                      <div class="stat-label">总爬升</div>
                    </div>
                  </div>
                </el-col>
                <el-col :span="12">
                  <div class="stat-item">
                    <el-icon class="stat-icon" color="#f56c6c"><Bottom /></el-icon>
                    <div class="stat-content">
                      <div class="stat-value">{{ formatElevation(track.elevation_loss) }}</div>
                      <div class="stat-label">总下降</div>
                    </div>
                  </div>
                </el-col>
              </el-row>
            </el-card>

            <!-- 轨迹信息 -->
            <el-card class="info-card" shadow="never">
              <template #header>
                <span>轨迹信息</span>
              </template>
              <el-descriptions :column="1" border>
                <el-descriptions-item label="文件名">
                  {{ track.original_filename }}
                </el-descriptions-item>
                <el-descriptions-item label="坐标系">
                  <el-tag size="small">{{ track.original_crs.toUpperCase() }}</el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="开始时间">
                  {{ formatDateTime(track.start_time) }}
                </el-descriptions-item>
                <el-descriptions-item label="结束时间">
                  {{ formatDateTime(track.end_time) }}
                </el-descriptions-item>
                <el-descriptions-item label="备注">
                  <span class="description-text">{{ track.description || '无' }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="填充进度">
                  <div class="fill-progress-content">
                    <div v-if="fillProgress.status === 'filling'" class="fill-progress-bar">
                      <el-progress
                        :percentage="getFillProgressPercentage()"
                        :show-text="true"
                        :stroke-width="8"
                      />
                      <div class="fill-progress-text">
                        {{ fillProgress.current }} / {{ fillProgress.total }}
                      </div>
                    </div>
                    <div v-else-if="fillProgress.status === 'completed'" class="fill-status-text">
                      <el-icon color="#67c23a"><SuccessFilled /></el-icon>
                      已填充
                    </div>
                    <div v-else-if="fillProgress.status === 'error'" class="fill-status-text">
                      <el-icon color="#f56c6c"><CircleCloseFilled /></el-icon>
                      填充失败
                    </div>
                    <div v-else class="fill-status-text">
                      <el-tag v-if="track.has_area_info && track.has_road_info" type="success" size="small">已填充</el-tag>
                      <el-tag v-else type="info" size="small">未填充</el-tag>
                    </div>
                  </div>
                </el-descriptions-item>
              </el-descriptions>
            </el-card>

            <!-- 经过的区域 - 树形展示 -->
            <el-card class="areas-card" shadow="never">
              <template #header>
                <div class="card-header">
                  <span>经过区域</span>
                  <el-tag v-if="regionStats.province > 0" size="small" type="info">
                    {{ regionStats.province }} 省级 / {{ regionStats.city }} 地级 / {{ regionStats.district }} 县级
                  </el-tag>
                </div>
              </template>
              <div v-if="regionTreeLoading" v-loading="true" style="min-height: 60px"></div>
              <div v-else-if="regionTree.length > 0" class="region-tree-container">
                <el-tree
                  :data="regionTree"
                  :props="{ label: 'name', children: 'children' }"
                  default-expand-all
                  :expand-on-click-node="false"
                  node-key="id"
                >
                  <template #default="{ node, data }">
                    <div class="region-tree-node">
                      <div class="node-label">
                        <el-icon class="node-icon" :class="`icon-${data.type}`">
                          <LocationFilled v-if="data.type === 'province'" />
                          <LocationFilled v-else-if="data.type === 'city'" />
                          <LocationFilled v-else-if="data.type === 'district'" />
                          <Odometer v-else-if="data.type === 'road'" />
                        </el-icon>
                        <span class="node-name">{{ formatNodeLabel(data) }}</span>
                      </div>
                      <div class="node-info">
                        <span class="node-distance">{{ formatDistance(data.distance) }}</span>
                        <span v-if="data.start_time" class="node-time">{{ formatTimeRange(data.start_time, data.end_time) }}</span>
                      </div>
                    </div>
                  </template>
                </el-tree>
              </div>
              <el-empty v-else description="暂无区域信息，请先填充地理信息" :image-size="60" />
            </el-card>

            <!-- 轨迹点列表
            <el-card class="points-card" shadow="never">
              <template #header>
                <span>轨迹点 ({{ points.length }})</span>
              </template>
              <el-scrollbar max-height="400">
                <div class="points-list">
                  <div
                    v-for="(point, index) in points"
                    :key="point.id"
                    class="point-item"
                    @click="highlightPoint(index)"
                    :class="{ highlighted: highlightedPointIndex === index }"
                  >
                    <div class="point-header">
                      <span class="point-index">#{{ point.point_index }}</span>
                      <span class="point-time">{{ formatTime(point.time) }}</span>
                    </div>
                    <div class="point-coords">
                      {{ point.latitude?.toFixed(6) }}, {{ point.longitude?.toFixed(6) }}
                    </div>
                    <div class="point-elevation" v-if="point.elevation">
                      海拔: {{ point.elevation.toFixed(1) }}m
                    </div>
                    <div class="point-location" v-if="point.city || point.road_name">
                      <el-tag v-if="point.city" size="mini">{{ point.city }}</el-tag>
                      <el-tag v-if="point.road_name" size="mini" type="success">{{ point.road_name }}</el-tag>
                    </div>
                  </div>
                </div>
              </el-scrollbar>
            </el-card> -->
          </el-col>
        </el-row>
      </template>
    </el-main>

    <!-- 编辑对话框 -->
    <el-dialog v-model="editDialogVisible" title="编辑轨迹" width="500px">
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="editForm.name" placeholder="请输入轨迹名称" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="editForm.description"
            type="textarea"
            :rows="4"
            placeholder="请输入备注信息"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 下载对话框 -->
    <el-dialog v-model="downloadDialogVisible" title="下载 GPX" width="400px">
      <el-form label-width="100px">
        <el-form-item label="坐标系">
          <el-radio-group v-model="downloadCRS">
            <el-radio value="original">原始 ({{ track?.original_crs?.toUpperCase() }})</el-radio>
            <el-radio value="wgs84">WGS84</el-radio>
            <el-radio value="gcj02">GCJ02 (火星)</el-radio>
            <el-radio value="bd09">BD09 (百度)</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="downloadDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="downloadTrack">下载</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft,
  Download,
  Edit,
  Odometer,
  Clock,
  Top,
  Bottom,
  SuccessFilled,
  CircleCloseFilled,
  User,
  ArrowDown,
  Setting,
  SwitchButton,
  LocationFilled,
} from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { trackApi, type Track, type TrackPoint, type FillProgressResponse, type RegionNode } from '@/api/track'
import UniversalMap from '@/components/map/UniversalMap.vue'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

// 响应式：判断是否为移动端
const screenWidth = ref(window.innerWidth)
const isMobile = computed(() => screenWidth.value <= 768)

// 监听窗口大小变化
function handleResize() {
  screenWidth.value = window.innerWidth
}

const loading = ref(true)
const track = ref<Track | null>(null)
const points = ref<TrackPoint[]>([])
const trackId = ref<number>(parseInt(route.params.id as string))
const highlightedPointIndex = ref<number>(-1)

const mapRef = ref()
const chartRef = ref<HTMLElement>()
let chartInstance: echarts.ECharts | null = null  // 保存图表实例
const downloadDialogVisible = ref(false)
const downloadCRS = ref('original')

// 编辑相关
const editDialogVisible = ref(false)
const saving = ref(false)
const editForm = ref({
  name: '',
  description: ''
})

// 填充地理信息相关
const fillingGeocoding = ref(false)
const fillProgress = ref<{
  current: number
  total: number
  status: 'idle' | 'filling' | 'completed' | 'error'
}>({ current: 0, total: 0, status: 'idle' })
let fillProgressTimer: number | null = null

// 区域树相关
const regionTree = ref<RegionNode[]>([])
const regionTreeLoading = ref(false)
const regionStats = ref<{ province: number; city: number; district: number; road: number }>({
  province: 0,
  city: 0,
  district: 0,
  road: 0,
})

// 组合轨迹数据用于地图展示
const trackWithPoints = computed(() => {
  if (!track.value || !points.value.length) return null

  // 过滤出有有效坐标的点
  const validPoints = points.value.filter(p =>
    p.latitude_wgs84 != null &&
    p.longitude_wgs84 != null &&
    !isNaN(p.latitude_wgs84) &&
    !isNaN(p.longitude_wgs84)
  )

  if (validPoints.length === 0) return null

  return {
    id: track.value.id,
    points: validPoints.map(p => ({
      latitude: p.latitude_wgs84,
      longitude: p.longitude_wgs84,
      latitude_wgs84: p.latitude_wgs84,
      longitude_wgs84: p.longitude_wgs84,
      latitude_gcj02: p.latitude_gcj02,
      longitude_gcj02: p.longitude_gcj02,
      latitude_bd09: p.latitude_bd09,
      longitude_bd09: p.longitude_bd09,
      elevation: p.elevation,
      time: p.time,
      speed: p.speed,
      province: p.province,
      city: p.city,
      district: p.district,
      road_name: p.road_name,
      road_number: p.road_number,
    })),
  }
})

// 处理用户下拉菜单命令
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
  } else if (command === 'edit') {
    showEditDialog()
  } else if (command === 'download') {
    downloadDialogVisible.value = true
  } else if (command === 'fill') {
    handleFillGeocoding()
  }
}

// 获取轨迹详情
async function fetchTrackDetail() {
  try {
    track.value = await trackApi.getDetail(trackId.value)
  } catch (error) {
    // 错误已在拦截器中处理
  }
}

// 获取轨迹点
async function fetchTrackPoints() {
  try {
    const response = await trackApi.getPoints(trackId.value)
    points.value = response.points
  } catch (error) {
    // 错误已在拦截器中处理
  }
}

// 获取区域树
async function fetchRegions() {
  if (!track.value?.has_area_info && !track.value?.has_road_info) {
    regionTree.value = []
    regionStats.value = { province: 0, city: 0, district: 0, road: 0 }
    return
  }

  try {
    regionTreeLoading.value = true
    const response = await trackApi.getRegions(trackId.value)
    regionTree.value = response.regions
    regionStats.value = response.stats
  } catch (error) {
    // 错误已在拦截器中处理
    regionTree.value = []
    regionStats.value = { province: 0, city: 0, district: 0, road: 0 }
  } finally {
    regionTreeLoading.value = false
  }
}

// 格式化节点显示名称
function formatNodeLabel(node: RegionNode): string {
  let label = node.name
  if (node.road_number) {
    // 将逗号分隔的道路编号改为斜杠分隔
    const roadNumbers = node.road_number.split(',').map(s => s.trim()).join(' / ')
    label += ` (${roadNumbers})`
  }
  return label
}

// 格式化距离
function formatDistance(meters: number): string {
  if (meters >= 1000) {
    const km = (meters / 1000).toFixed(2)
    // 去掉末尾的 .00
    return km.endsWith('.00') ? `${km.slice(0, -3)} km` : `${km} km`
  }
  return `${Math.round(meters)} m`
}

// 格式化时间范围
function formatTimeRange(start: string | null, end: string | null): string {
  if (!start) return '-'
  const startDate = new Date(start)
  const endDate = end ? new Date(end) : null

  // 格式化时间（本地时区）
  const formatTime = (date: Date) => {
    const hours = date.getHours().toString().padStart(2, '0')
    const minutes = date.getMinutes().toString().padStart(2, '0')
    return `${hours}:${minutes}`
  }

  if (endDate) {
    const diff = (endDate.getTime() - startDate.getTime()) / 1000 / 60 // 分钟
    if (diff < 1) {
      return `${formatTime(startDate)}`
    } else if (diff < 60) {
      return `${formatTime(startDate)} - ${formatTime(endDate)} (${Math.round(diff)}分钟)`
    } else {
      const hours = Math.floor(diff / 60)
      const mins = Math.round(diff % 60)
      return `${formatTime(startDate)} - ${formatTime(endDate)} (${hours}小时${mins}分钟)`
    }
  }
  return formatTime(startDate)
}

// 渲染海拔和速度合并图表
function renderChart() {
  if (!chartRef.value || !points.value.length) return

  const chart = echarts.init(chartRef.value)
  chartInstance = chart  // 保存图表实例

  // 判断是否为移动端
  const isMobile = window.innerWidth <= 768

  // 移动端数据采样
  let sampledPoints = points.value
  let sampledElevationData: number[][] = []
  let sampledSpeedData: number[][] = []
  let sampledXAxisData: string[] = []

  // if (isMobile && points.value.length > 100) {
  //   // 移动端使用采样：目标约 50 个点
  //   const targetPoints = 50
  //   const step = Math.ceil(points.value.length / targetPoints)
  //   sampledPoints = points.value.filter((_p: any, index: number) => index % step === 0)
  // }

  // 准备海拔数据
  sampledElevationData = sampledPoints
    .filter((p: any) => p.elevation !== null)
    .map((p: any, index: number) => [index, p.elevation])

  // 准备速度数据（转换为 km/h）
  sampledSpeedData = sampledPoints
    .filter((p: any) => p.speed !== null && p.speed !== undefined)
    .map((p: any, index: number) => [index, (p.speed ?? 0) * 3.6])

  // X 轴数据（使用时间标签）
  sampledXAxisData = sampledPoints.map((p: any, index: number) => {
    if (p.time) {
      const date = new Date(p.time)
      return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`
    }
    return index.toString()
  })

  const option = {
    grid: {
      left: isMobile ? '30px' : '70px',
      right: isMobile ? '30px' : '70px',
      top: isMobile ? '30px' : '50px',
      bottom: isMobile ? '30px' : '50px',
    },
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const dataIndex = params[0].dataIndex
        const point = sampledPoints[dataIndex]
        const speedRaw = point.speed
        const speedKmh = speedRaw !== null ? (speedRaw * 3.6).toFixed(2) : '-'
        let result = `点 #${dataIndex}<br/>时间: ${point.time ? formatTime(point.time) : '-'}<br/>`
        for (const param of params) {
          if (param.seriesName === '海拔') {
            const elevationValue = param.value !== null ? param.value.toFixed(1) : '-'
            result += `${param.marker}${param.seriesName}: ${elevationValue} m<br/>`
          } else if (param.seriesName === '速度') {
            result += `${param.marker}${param.seriesName}: ${speedKmh} km/h<br/>`
          }
        }
        return result
      },
    },
    xAxis: {
      type: 'category',
      data: sampledXAxisData,
      axisLabel: {
        interval: isMobile ? 'auto' : Math.max(1, Math.floor(sampledXAxisData.length / 10)),
        fontSize: isMobile ? 9 : 12,
        rotate: isMobile ? 45 : 0,
      },
      axisTick: {
        alignWithLabel: true,
      },
    },
    yAxis: [
      {
        type: 'value',
        name: '海拔 (m)',
        nameLocation: 'middle',
        nameGap: isMobile ? 20 : 40,
        nameTextStyle: {
          padding: [0, 0, 0, 0],
          fontSize: isMobile ? 10 : 12,
        },
        axisLine: {
          lineStyle: {
            color: '#409eff',
          },
        },
        splitLine: {
          show: true,
          lineStyle: {
            color: '#e5e5e5',
          },
        },
        splitNumber: isMobile ? 4 : 5,
        axisLabel: {
          fontSize: isMobile ? 9 : 12,
        },
      },
      {
        type: 'value',
        name: '速度 (km/h)',
        nameLocation: 'middle',
        nameGap: isMobile ? 20 : 40,
        nameTextStyle: {
          padding: [0, 0, 0, 0],
          fontSize: isMobile ? 10 : 12,
        },
        axisLine: {
          lineStyle: {
            color: '#67c23a',
          },
        },
        splitLine: {
          show: false,
        },
        splitNumber: isMobile ? 4 : 5,
        axisLabel: {
          fontSize: isMobile ? 9 : 12,
        },
      },
    ],
    series: [
      {
        name: '海拔',
        type: 'line',
        yAxisIndex: 0,
        data: sampledElevationData.map(d => d[1]),
        smooth: !isMobile, // 移动端不使用平滑
        sampling: null,
        symbol: 'none',
        areaStyle: isMobile ? undefined : {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(64, 158, 255, 0.3)' },
              { offset: 1, color: 'rgba(64, 158, 255, 0.05)' },
            ],
          },
        },
        lineStyle: {
          color: '#409eff',
          width: 2,
        },
      },
      {
        name: '速度',
        type: 'line',
        yAxisIndex: 1,
        data: sampledSpeedData.map(d => d[1]),
        smooth: false,  // 禁用平滑，确保 tooltip 显示原始数据点值
        sampling: null,
        symbol: 'none',
        areaStyle: isMobile ? undefined : {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(103, 194, 58, 0.3)' },
              { offset: 1, color: 'rgba(103, 194, 58, 0.05)' },
            ],
          },
        },
        lineStyle: {
          color: '#67c23a',
          width: 2,
        },
      },
    ],
    legend: {
      data: ['海拔', '速度'],
      top: isMobile ? 5 : 10,
      right: 20,
      textStyle: {
        fontSize: isMobile ? 10 : 12,
      },
    },
  }

  chart.setOption(option)

  // 图表鼠标移动事件监听 - 用于反向同步到地图
  chart.on('mousemove', (params: any) => {
    // 检查是否在数据系列上
    if (params.componentType === 'series' && params.dataIndex !== undefined) {
      // 使用采样的原始索引（如果有采样数据）
      let originalIndex = params.dataIndex

      // 调用地图组件的 highlightPoint 方法
      if (mapRef.value?.highlightPoint) {
        mapRef.value.highlightPoint(originalIndex)
      }
    }
  })

  // 使用 axis 指针事件更可靠
  chart.on('showTip', (params: any) => {
    if (params.dataIndex !== undefined && mapRef.value?.highlightPoint) {
      mapRef.value.highlightPoint(params.dataIndex)
    }
  })

  // 图表鼠标离开事件 - 隐藏地图标记
  chart.on('mouseleave', () => {
    if (mapRef.value?.hideMarker) {
      mapRef.value.hideMarker()
    }
  })

  // 也监听 hideTip 事件
  chart.on('hideTip', () => {
    if (mapRef.value?.hideMarker) {
      mapRef.value.hideMarker()
    }
  })

  // 响应式调整
  const resizeObserver = new ResizeObserver(() => {
    chart.resize()
  })
  resizeObserver.observe(chartRef.value)
}

// 处理地图点悬浮事件 - 同步到图表
function handleMapPointHover(point: any, pointIndex: number) {
  if (!chartInstance || pointIndex < 0) return

  // 在图表上显示标记线
  chartInstance.dispatchAction({
    type: 'showTip',
    seriesIndex: 0,
    dataIndex: pointIndex,
  })

  // 高亮该点
  chartInstance.dispatchAction({
    type: 'highlight',
    seriesIndex: 0,
    dataIndex: pointIndex,
  })

  // 取消之前的高亮
  if (highlightedPointIndex.value >= 0 && highlightedPointIndex.value !== pointIndex) {
    chartInstance.dispatchAction({
      type: 'downplay',
      seriesIndex: 0,
      dataIndex: highlightedPointIndex.value,
    })
  }

  highlightedPointIndex.value = pointIndex
}

// 填充地理信息
async function handleFillGeocoding() {
  try {
    await trackApi.fillGeocoding(trackId.value)
    ElMessage.success('开始填充地理信息')
    fillingGeocoding.value = true
    startPollingProgress()
  } catch (error) {
    // 错误已在拦截器中处理
  }
}

// 开始轮询进度
function startPollingProgress() {
  if (fillProgressTimer) return

  fillProgressTimer = window.setInterval(async () => {
    try {
      const response = await trackApi.getFillProgress(trackId.value)
      fillProgress.value = response.progress

      if (response.progress.status === 'completed') {
        stopPollingProgress()
        fillingGeocoding.value = false
        ElMessage.success('地理信息填充完成')
        // 重新加载轨迹数据
        await fetchTrackDetail()
        await fetchTrackPoints()
        await fetchRegions()
      } else if (response.progress.status === 'error') {
        stopPollingProgress()
        fillingGeocoding.value = false
        ElMessage.error('填充地理信息失败')
      }
    } catch (error) {
      console.error('Failed to fetch fill progress:', error)
    }
  }, 2000)
}

// 停止轮询进度
function stopPollingProgress() {
  if (fillProgressTimer) {
    clearInterval(fillProgressTimer)
    fillProgressTimer = null
  }
}

// 获取填充进度百分比
function getFillProgressPercentage(): number {
  if (fillProgress.value.total > 0) {
    return Math.round((fillProgress.value.current / fillProgress.value.total) * 100)
  }
  return 0
}

// 检查并恢复填充进度轮询
async function checkAndResumeFilling() {
  try {
    const response = await trackApi.getFillProgress(trackId.value)
    fillProgress.value = response.progress

    // 如果正在填充，启动轮询
    if (response.progress.status === 'filling') {
      fillingGeocoding.value = true
      startPollingProgress()
    }
  } catch (error) {
    // 忽略错误，可能是填充功能还未调用过
  }
}

// 高亮点
function highlightPoint(index: number) {
  highlightedPointIndex.value = index
  // TODO: 在地图上高亮该点
}

// 显示下载对话框
function showDownloadDialog() {
  downloadDialogVisible.value = true
}

// 显示编辑对话框
function showEditDialog() {
  if (track.value) {
    editForm.value.name = track.value.name
    editForm.value.description = track.value.description || ''
  }
  editDialogVisible.value = true
}

// 保存编辑
async function saveEdit() {
  if (!track.value) return

  if (!editForm.value.name.trim()) {
    ElMessage.warning('轨迹名称不能为空')
    return
  }

  saving.value = true
  try {
    const updated = await trackApi.update(track.value.id, {
      name: editForm.value.name.trim(),
      description: editForm.value.description.trim() || undefined
    })
    track.value = updated
    editDialogVisible.value = false
    ElMessage.success('保存成功')
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    saving.value = false
  }
}

// 下载轨迹
async function downloadTrack() {
  try {
    const url = trackApi.download(trackId.value, downloadCRS.value)
    // 使用 fetch 下载，自动携带认证信息
    const response = await fetch(url, {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      }
    })

    if (!response.ok) {
      throw new Error('下载失败')
    }

    // 获取文件名
    const contentDisposition = response.headers.get('Content-Disposition')
    let filename = `track_${trackId.value}.gpx`
    if (contentDisposition) {
      const match = contentDisposition.match(/filename="(.+)"/)
      if (match) filename = match[1]
    }

    // 创建 blob 并下载
    const blob = await response.blob()
    const blobUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = blobUrl
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(blobUrl)

    downloadDialogVisible.value = false
    ElMessage.success('下载成功')
  } catch (error) {
    console.error('Download error:', error)
    ElMessage.error('下载失败')
  }
}

// 格式化函数
function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (hours > 0) return `${hours}h ${minutes}m`
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

function formatTime(dateStr: string | null): string {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  const hours = date.getHours().toString().padStart(2, '0')
  const minutes = date.getMinutes().toString().padStart(2, '0')
  const seconds = date.getSeconds().toString().padStart(2, '0')
  return `${hours}:${minutes}:${seconds}`
}

onMounted(async () => {
  try {
    await fetchTrackDetail()
    await fetchTrackPoints()
    await fetchRegions()
  } catch (error) {
    console.error('Failed to load track data:', error)
  } finally {
    loading.value = false
  }

  // 检查是否有正在进行的填充操作
  await checkAndResumeFilling()

  // 等待 DOM 更新后渲染图表
  nextTick(() => {
    renderChart()
  })

  // 添加窗口大小监听
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  stopPollingProgress()
  // 移除窗口大小监听器
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.track-detail-container {
  height: 100vh;
  overflow-y: auto;
  background: #f5f7fa;
  display: block;
}

.track-detail-container > .el-header {
  position: sticky;
  top: 0;
  z-index: 1000;
  background: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  gap: 16px;
  flex-shrink: 0;
}

.track-detail-container > .el-main {
  overflow: visible;
}

/* 限制地图相关元素的 z-index */
.map-card {
  position: relative;
  z-index: 1;
}

:deep(.leaflet-map-container) {
  z-index: 1;
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
  gap: 16px;
}

.header-actions {
  display: flex;
  gap: 10px;
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

.desktop-only {
  display: inline-block;
}

.main {
  max-width: 1600px;
  margin: 0 auto;
  padding: 20px;
  width: 100%;
}

.map-card,
.chart-card {
  margin-bottom: 20px;
}

.map-card :deep(.el-card__body) {
  padding: 0;
  height: 500px;
}

.map-placeholder {
  height: 500px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #909399;
  text-align: center;
}

.map-placeholder p {
  margin: 8px 0;
}

.debug-info {
  font-size: 12px;
  color: #f56c6c;
}

.stats-card,
.info-card,
.areas-card,
.points-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.stats-card :deep(.el-row) {
  --el-row-gutter: 20px;
}

.stats-card :deep(.el-col) {
  margin-top: 8px;
  margin-bottom: 8px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.stat-icon {
  font-size: 24px;
}

.stat-value {
  font-size: 18px;
  font-weight: bold;
  color: #333;
}

.stat-label {
  font-size: 12px;
  color: #999;
}

.chart {
  height: 220px;
}

/* 时间线样式 */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* 区域树样式 */
.region-tree-container {
  padding: 10px 0;
}

.region-tree-node {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  padding-right: 10px;
}

.node-label {
  display: flex;
  align-items: center;
  gap: 8px;
}

.node-icon {
  font-size: 16px;
}

.node-icon.icon-province {
  color: #f56c6c;
}

.node-icon.icon-city {
  color: #409eff;
}

.node-icon.icon-district {
  color: #67c23a;
}

.node-icon.icon-road {
  color: #e6a23c;
}

.node-name {
  font-weight: 500;
  color: #303133;
}

.node-info {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #909399;
  font-size: 12px;
}

.node-distance {
  color: #606266;
  font-weight: 500;
}

.node-time {
  color: #909399;
}

.info-missing {
  color: #f56c6c;
  font-size: 12px;
  font-style: italic;
}

.points-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.point-item {
  padding: 10px;
  border: 1px solid #eee;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.point-item:hover {
  background: #f5f7fa;
}

.point-item.highlighted {
  background: #e6f7ff;
  border-color: #409eff;
}

.point-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}

.point-index {
  font-weight: bold;
  color: #409eff;
}

.point-time {
  font-size: 12px;
  color: #999;
}

.point-coords {
  font-size: 12px;
  color: #666;
  margin-bottom: 2px;
}

.point-elevation {
  font-size: 12px;
  color: #666;
}

.point-location {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.fill-progress-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.fill-progress-bar {
  margin-top: 4px;
}

.fill-progress-text {
  font-size: 12px;
  color: #909399;
  text-align: center;
  margin-top: 4px;
}

.fill-status-text {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
}

.description-text {
  color: #606266;
  white-space: pre-wrap;
  word-break: break-word;
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

  .map-card :deep(.el-card__body),
  .map-placeholder {
    height: 300px;
  }

  .chart {
    height: 200px;
  }

  .stat-icon {
    font-size: 20px;
  }

  .stat-value {
    font-size: 16px;
  }

  .stat-label {
    font-size: 11px;
  }
}
</style>
