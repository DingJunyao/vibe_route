<template>
  <el-container class="track-merge-container">
    <el-header>
      <div class="header-left">
        <el-button @click="handleBack" :icon="ArrowLeft" class="nav-btn" />
        <el-button @click="goHome" :icon="HomeFilled" class="nav-btn home-nav-btn" />
        <h1>合并轨迹</h1>
      </div>
    </el-header>

    <el-main class="merge-main">
      <el-steps :active="step" simple class="merge-steps">
        <el-step title="选择轨迹" />
        <el-step title="预览并合并" />
      </el-steps>

      <!-- 步骤 1：选择轨迹 -->
      <template v-if="step === 0">
        <el-card shadow="never" class="select-card">
          <div class="select-toolbar">
            <el-input
              v-model="searchQuery"
              placeholder="搜索轨迹名称..."
              :prefix-icon="Search"
              clearable
            />
          </div>

          <div v-if="loadingTracks" class="loading-wrapper">
            <el-skeleton :rows="5" animated />
          </div>
          <template v-else>
            <!-- PC 端表格 -->
            <el-table
              v-if="!isMobile"
              :data="filteredTracks"
              row-key="id"
              max-height="480"
              @selection-change="handleSelectionChange"
            >
              <el-table-column type="selection" width="50" :selectable="isSelectable" reserve-selection />
              <el-table-column prop="name" label="名称" min-width="180" show-overflow-tooltip />
              <el-table-column label="开始时间" width="170">
                <template #default="{ row }">{{ formatDateTime(row.start_time) }}</template>
              </el-table-column>
              <el-table-column label="结束时间" width="170">
                <template #default="{ row }">{{ formatDateTime(row.end_time) }}</template>
              </el-table-column>
              <el-table-column label="距离" width="100">
                <template #default="{ row }">{{ formatDistance(row.distance) }}</template>
              </el-table-column>
              <el-table-column label="时长" width="110">
                <template #default="{ row }">{{ formatDuration(row.duration) }}</template>
              </el-table-column>
            </el-table>

            <!-- 移动端卡片列表 -->
            <div v-else class="mobile-track-list">
              <el-empty v-if="filteredTracks.length === 0" description="暂无符合条件的轨迹" />
              <div
                v-for="track in filteredTracks"
                :key="track.id"
                class="mobile-track-card"
                :class="{ selected: selectedIds.has(track.id), disabled: !isSelectable(track) }"
                @click="toggleSelect(track)"
              >
                <el-checkbox
                  :model-value="selectedIds.has(track.id)"
                  :disabled="!isSelectable(track)"
                  @click.stop
                  @change="toggleSelect(track)"
                />
                <div class="mobile-track-info">
                  <div class="mobile-track-name">{{ track.name }}</div>
                  <div class="mobile-track-meta">
                    {{ formatTimeRange(track.start_time, track.end_time) }} ·
                    {{ formatDistance(track.distance) }}
                  </div>
                </div>
              </div>
            </div>

            <el-empty v-if="!isMobile && filteredTracks.length === 0" description="暂无符合条件的轨迹" />
          </template>
        </el-card>

        <!-- 已选轨迹摘要 -->
        <el-card v-if="selectedTracks.length > 0" shadow="never" class="selected-card">
          <div class="selected-header">
            已选 {{ selectedTracks.length }} 段（按时间排序，合并时将按此顺序组合）：
          </div>
          <div class="selected-tags">
            <el-tag
              v-for="(track, i) in selectedTracks"
              :key="track.id"
              :color="segmentColor(i)"
              effect="dark"
              class="selected-tag"
            >
              {{ i + 1 }}. {{ track.name }}
            </el-tag>
          </div>
          <el-alert
            v-if="hasPreOverlap"
            type="warning"
            :closable="false"
            show-icon
            class="overlap-alert"
          >
            所选轨迹存在时间重叠，合并时将自动剔除重叠部分（保留时间靠后的段），可在预览中查看明细。
          </el-alert>
        </el-card>

        <div class="step-actions">
          <el-button @click="handleBack">返回</el-button>
          <el-button
            type="primary"
            :disabled="selectedTracks.length < 2"
            :loading="previewLoading"
            @click="goPreview"
          >
            下一步：预览合并
          </el-button>
        </div>
      </template>

      <!-- 步骤 2：预览并合并 -->
      <template v-else>
        <div v-if="previewLoading" class="preview-loading">
          <el-skeleton :rows="6" animated />
        </div>

        <div v-else-if="preview" class="merge-layout">
          <!-- 地图区域 -->
          <div class="map-section">
            <UniversalMap
              ref="mapRef"
              :custom-overlays="mapOverlays"
              :disable-point-hover="true"
              mode="detail"
              @map-provider-changed="handleProviderChanged"
            />
            <div class="map-legend">
              <div v-for="(seg, i) in preview.segments" :key="seg.track_id" class="legend-item">
                <span class="segment-dot" :style="{ backgroundColor: segmentColor(i) }"></span>
                <span class="legend-name">{{ seg.name }}</span>
              </div>
              <div class="legend-divider"></div>
              <div class="legend-item">
                <span class="legend-link legend-link-normal"></span>
                <span class="legend-name">段间衔接</span>
              </div>
              <div class="legend-item">
                <span class="legend-link legend-link-gap"></span>
                <span class="legend-name">时间空缺（&gt;5 分钟，直线连接）</span>
              </div>
            </div>
          </div>

          <!-- 信息面板 -->
          <div class="panel-section">
            <el-alert
              v-if="preview.has_overlap"
              type="warning"
              :closable="false"
              show-icon
              class="overlap-alert"
              :title="`检测到时间重叠，已自动剔除 ${preview.removed_points} 个重叠点（保留时间靠后的段）`"
            />

            <el-alert
              v-if="gapList.length > 0"
              type="warning"
              :closable="false"
              show-icon
              class="overlap-alert"
              :title="`检测到 ${gapList.length} 处时间空缺（间隔超过 5 分钟），空缺处以直线连接，不插入插值点`"
            />

            <!-- 空缺明细 -->
            <div v-if="gapList.length > 0" class="gap-list">
              <div class="segment-title">时间空缺明细</div>
              <div v-for="(gap, i) in gapList" :key="i" class="gap-item">
                <span class="legend-link legend-link-gap gap-link-icon"></span>
                <div class="segment-info">
                  <div class="segment-name">
                    段{{ gap.from_segment + 1 }} → 段{{ gap.to_segment + 1 }}：间隔
                    {{ formatDuration(gap.time_gap ?? 0) }}
                  </div>
                  <div class="segment-meta">衔接直线距离 {{ formatDistance(gap.distance) }}</div>
                </div>
              </div>
            </div>

            <el-descriptions :column="2" border size="small" class="stat-desc">
              <el-descriptions-item label="总距离">{{ formatDistance(preview.distance) }}</el-descriptions-item>
              <el-descriptions-item label="总时长">{{ formatDuration(preview.duration) }}</el-descriptions-item>
              <el-descriptions-item label="轨迹点数">{{ preview.total_points }}</el-descriptions-item>
              <el-descriptions-item label="爬升 / 下降">
                {{ formatElevation(preview.elevation_gain) }} / {{ formatElevation(preview.elevation_loss) }}
              </el-descriptions-item>
              <el-descriptions-item label="开始时间" :span="2">{{ formatDateTime(preview.start_time) }}</el-descriptions-item>
              <el-descriptions-item label="结束时间" :span="2">{{ formatDateTime(preview.end_time) }}</el-descriptions-item>
            </el-descriptions>

            <!-- 段列表 -->
            <div class="segment-list">
              <div class="segment-title">合并顺序（按时间）</div>
              <div v-for="(seg, i) in preview.segments" :key="seg.track_id" class="segment-item">
                <span class="segment-dot" :style="{ backgroundColor: segmentColor(i) }"></span>
                <div class="segment-info">
                  <div class="segment-name">{{ i + 1 }}. {{ seg.name }}</div>
                  <div class="segment-meta">
                    {{ formatTimeRange(seg.start_time, seg.end_time) }}
                    <span class="segment-points">{{ seg.kept_points }} 点</span>
                    <span v-if="seg.removed_points > 0" class="segment-removed">
                      剔除 {{ seg.removed_points }} 点
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <!-- 新轨迹信息 -->
            <el-form label-position="top" class="merge-form">
              <el-form-item label="新轨迹名称" required>
                <el-input v-model="mergeName" maxlength="200" show-word-limit />
              </el-form-item>
              <el-form-item label="描述">
                <el-input v-model="mergeDescription" type="textarea" :rows="2" />
              </el-form-item>
            </el-form>

            <el-alert
              type="info"
              :closable="false"
              show-icon
              class="keep-alert"
              title="合并将创建一条新轨迹，原轨迹全部保留"
            />

            <div class="step-actions">
              <el-button :disabled="merging" @click="step = 0">上一步</el-button>
              <el-button type="primary" :loading="merging" @click="handleMerge">确认合并</el-button>
            </div>
          </div>
        </div>
      </template>
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, HomeFilled, Search } from '@element-plus/icons-vue'
import UniversalMap from '@/components/map/UniversalMap.vue'
import {
  trackApi,
  type UnifiedTrack,
  type MergePreviewResponse,
  type MergePreviewPoint,
  type MergeGapInfo,
} from '@/api/track'
import {
  formatDistance,
  formatDuration,
  formatElevation,
  formatDateTime,
  formatTimeRange,
} from '@/utils/format'
import { wgs84ToGcj02, wgs84ToBd09 } from '@/utils/coordTransform'

// 段颜色调色板（按合并顺序循环取色）
const SEGMENT_COLORS = [
  '#409eff', '#67c23a', '#e6a23c', '#f56c6c',
  '#9b59b6', '#00bcd4', '#ff9800', '#795548',
]
// 段间衔接线颜色：空缺=醒目橙色虚线，正常衔接=中性灰色
const GAP_LINK_COLOR = '#e6a23c'
const NORMAL_LINK_COLOR = '#909399'

const router = useRouter()

// 响应式
const screenWidth = ref(window.innerWidth)
function handleResize() {
  screenWidth.value = window.innerWidth
}
const isMobile = computed(() => screenWidth.value <= 1366)

// 步骤状态
const step = ref(0)

// 步骤 1 状态
const loadingTracks = ref(false)
const allTracks = ref<UnifiedTrack[]>([])
const searchQuery = ref('')
const selectedIds = ref<Set<number>>(new Set())

// 步骤 2 状态
const previewLoading = ref(false)
const preview = ref<MergePreviewResponse | null>(null)
const mergeName = ref('')
const mergeDescription = ref('')
const merging = ref(false)

const mapRef = ref()

// 过滤后的可选轨迹列表
const filteredTracks = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  if (!query) return allTracks.value
  return allTracks.value.filter(t => t.name.toLowerCase().includes(query))
})

// 已选轨迹（按开始时间排序）
const selectedTracks = computed(() => {
  const selected = allTracks.value.filter(t => selectedIds.value.has(t.id))
  return selected.sort((a, b) => {
    const ta = a.start_time ? new Date(a.start_time).getTime() : Infinity
    const tb = b.start_time ? new Date(b.start_time).getTime() : Infinity
    return ta - tb
  })
})

// 前端粗略时间重叠预检
const hasPreOverlap = computed(() => {
  const tracks = selectedTracks.value
  for (let i = 1; i < tracks.length; i++) {
    const prevEnd = tracks[i - 1].end_time ? new Date(tracks[i - 1].end_time!).getTime() : null
    const curStart = tracks[i].start_time ? new Date(tracks[i].start_time!).getTime() : null
    if (prevEnd !== null && curStart !== null && curStart < prevEnd) {
      return true
    }
  }
  return false
})

// 段颜色（按索引循环）
function segmentColor(index: number): string {
  return SEGMENT_COLORS[index % SEGMENT_COLORS.length]
}

// 是否可选中：排除进行中的实时记录与无轨迹的虚拟项（负数 ID）
function isSelectable(row: UnifiedTrack): boolean {
  if (row.id <= 0) return false
  if (row.is_live_recording && row.live_recording_status === 'active') return false
  return true
}

// 加载全部轨迹（分页循环拉取，接口 page_size 上限 100）
async function loadAllTracks() {
  loadingTracks.value = true
  try {
    const pageSize = 100
    let page = 1
    let total = Infinity
    const items: UnifiedTrack[] = []
    // 最多拉取 10000 条，防止死循环
    while (items.length < total && items.length < 10000) {
      const res = await trackApi.getUnifiedList({ page, page_size: pageSize })
      total = res.total
      items.push(...res.items)
      if (res.items.length < pageSize) break
      page++
    }
    allTracks.value = items
  } catch {
    // 错误已由拦截器统一提示
  } finally {
    loadingTracks.value = false
  }
}

// 表格选择变化（PC 端）
function handleSelectionChange(rows: UnifiedTrack[]) {
  selectedIds.value = new Set(rows.map(r => r.id))
}

// 切换选择（移动端卡片）
function toggleSelect(track: UnifiedTrack) {
  if (!isSelectable(track)) return
  const next = new Set(selectedIds.value)
  if (next.has(track.id)) {
    next.delete(track.id)
  } else {
    next.add(track.id)
  }
  selectedIds.value = next
}

// 进入预览
async function goPreview() {
  if (selectedTracks.value.length < 2) {
    ElMessage.warning('请至少选择两段轨迹')
    return
  }
  previewLoading.value = true
  step.value = 1
  try {
    preview.value = await trackApi.mergePreview(selectedTracks.value.map(t => t.id))
    mergeName.value = `合并轨迹（${preview.value.segments.length}段）`
    mergeDescription.value = ''
    // 等待地图渲染后调整视野
    nextTick(() => {
      setTimeout(fitToPreview, 500)
    })
  } catch {
    // 错误已由拦截器统一提示，返回选择步骤
    step.value = 0
  } finally {
    previewLoading.value = false
  }
}

// 地图覆盖层类型（与 UniversalMap 的 CustomOverlay 接口结构兼容）
interface MergeOverlayPolyline {
  type: 'polyline'
  positions: Array<[number, number]>
  positions_gcj02?: Array<[number, number]>
  positions_bd09?: Array<[number, number]>
  color?: string
  weight?: number
  opacity?: number
  dashArray?: string
}

interface MergeOverlayMarker {
  type: 'marker'
  position?: [number, number]
  latitude_wgs84?: number
  longitude_wgs84?: number
  latitude_gcj02?: number | null
  longitude_gcj02?: number | null
  latitude_bd09?: number | null
  longitude_bd09?: number | null
  icon?: {
    type: 'circle'
    radius: number
    fillColor: string
    fillOpacity: number
    strokeColor: string
    strokeWidth: number
  }
  label?: string
}

type MergeOverlay = MergeOverlayPolyline | MergeOverlayMarker

// 地图覆盖层：每段一条彩色线 + 段间衔接线 + 合并整体起终点标记
const mapOverlays = computed<MergeOverlay[]>(() => {
  if (!preview.value) return []
  const overlays: MergeOverlay[] = []

  // 按段分组（key 升序，即合并顺序）
  const bySegment = new Map<number, MergePreviewPoint[]>()
  for (const p of preview.value.points) {
    if (!bySegment.has(p.segment_index)) bySegment.set(p.segment_index, [])
    bySegment.get(p.segment_index)!.push(p)
  }
  const segEntries = [...bySegment.entries()].sort((a, b) => a[0] - b[0])

  for (const [segIndex, points] of segEntries) {
    if (points.length < 2) continue
    const color = segmentColor(segIndex)
    const wgs84Positions: Array<[number, number]> = points.map(p => [p.latitude_wgs84, p.longitude_wgs84])
    // GCJ02/BD09 全部可用时才提供，否则由引擎回退 WGS84
    const gcj02All = points.every(p => p.latitude_gcj02 != null && p.longitude_gcj02 != null)
    const bd09All = points.every(p => p.latitude_bd09 != null && p.longitude_bd09 != null)

    overlays.push({
      type: 'polyline',
      positions: wgs84Positions,
      positions_gcj02: gcj02All
        ? points.map(p => [p.latitude_gcj02!, p.longitude_gcj02!] as [number, number])
        : undefined,
      positions_bd09: bd09All
        ? points.map(p => [p.latitude_bd09!, p.longitude_bd09!] as [number, number])
        : undefined,
      color,
      weight: 4,
      opacity: 0.9,
    })
  }

  // 段间衔接线：保证合并结果视觉连续；空缺处醒目橙色虚线着重提示
  const gapMap = new Map<string, MergeGapInfo>()
  for (const g of preview.value.gaps) gapMap.set(`${g.from_segment}->${g.to_segment}`, g)
  for (let i = 0; i + 1 < segEntries.length; i++) {
    const [fromIdx, fromPoints] = segEntries[i]
    const [toIdx, toPoints] = segEntries[i + 1]
    const gapInfo = gapMap.get(`${fromIdx}->${toIdx}`)
    overlays.push(makeLinkLine(fromPoints[fromPoints.length - 1], toPoints[0], gapInfo?.is_gap ?? false))
  }

  // 合并整体起点（绿）/终点（红）标记
  const allPoints = preview.value.points
  if (allPoints.length > 0) {
    const start = allPoints[0]
    const end = allPoints[allPoints.length - 1]
    overlays.push(makeMarker(start, '#67c23a', '起'))
    overlays.push(makeMarker(end, '#f56c6c', '终'))
  }

  return overlays
})

// 时间空缺明细（间隔超过 5 分钟的衔接处）
const gapList = computed(() => preview.value?.gaps.filter(g => g.is_gap) ?? [])

// 构造段间衔接线（两点连线；空缺用橙色虚线着重提示，正常衔接用灰色弱化实线）
function makeLinkLine(from: MergePreviewPoint, to: MergePreviewPoint, isGap: boolean): MergeOverlayPolyline {
  // 优先使用点自带的 GCJ02/BD09，缺失时由 WGS84 转换补齐（与起终点标记一致）
  const toGcj02 = (p: MergePreviewPoint): [number, number] => {
    if (p.latitude_gcj02 != null && p.longitude_gcj02 != null) return [p.latitude_gcj02, p.longitude_gcj02]
    const [lng, lat] = wgs84ToGcj02(p.longitude_wgs84, p.latitude_wgs84)
    return [lat, lng]
  }
  const toBd09 = (p: MergePreviewPoint): [number, number] => {
    if (p.latitude_bd09 != null && p.longitude_bd09 != null) return [p.latitude_bd09, p.longitude_bd09]
    const [lng, lat] = wgs84ToBd09(p.longitude_wgs84, p.latitude_wgs84)
    return [lat, lng]
  }
  return {
    type: 'polyline',
    positions: [
      [from.latitude_wgs84, from.longitude_wgs84],
      [to.latitude_wgs84, to.longitude_wgs84],
    ],
    positions_gcj02: [toGcj02(from), toGcj02(to)],
    positions_bd09: [toBd09(from), toBd09(to)],
    color: isGap ? GAP_LINK_COLOR : NORMAL_LINK_COLOR,
    weight: isGap ? 5 : 2,
    opacity: isGap ? 0.95 : 0.6,
    dashArray: isGap ? '12 8' : undefined,
  }
}

// 构造起终点圆形标记（缺失坐标系时由 WGS84 转换补齐）
function makeMarker(p: MergePreviewPoint, color: string, label: string): MergeOverlayMarker {
  let gcj02: [number, number] | null = null
  let bd09: [number, number] | null = null
  if (p.latitude_gcj02 != null && p.longitude_gcj02 != null) {
    gcj02 = [p.latitude_gcj02, p.longitude_gcj02]
  } else {
    const [lng, lat] = wgs84ToGcj02(p.longitude_wgs84, p.latitude_wgs84)
    gcj02 = [lat, lng]
  }
  if (p.latitude_bd09 != null && p.longitude_bd09 != null) {
    bd09 = [p.latitude_bd09, p.longitude_bd09]
  } else {
    const [lng, lat] = wgs84ToBd09(p.longitude_wgs84, p.latitude_wgs84)
    bd09 = [lat, lng]
  }
  return {
    type: 'marker',
    position: [p.latitude_wgs84, p.longitude_wgs84],
    latitude_wgs84: p.latitude_wgs84,
    longitude_wgs84: p.longitude_wgs84,
    latitude_gcj02: gcj02[0],
    longitude_gcj02: gcj02[1],
    latitude_bd09: bd09[0],
    longitude_bd09: bd09[1],
    icon: {
      type: 'circle',
      radius: 8,
      fillColor: color,
      fillOpacity: 0.95,
      strokeColor: '#fff',
      strokeWidth: 2,
    },
    label,
  }
}

// 调整地图视野到合并轨迹范围
function fitToPreview() {
  if (!mapRef.value?.fitToBounds || !preview.value || preview.value.points.length === 0) return
  let minLat = Infinity, maxLat = -Infinity, minLon = Infinity, maxLon = -Infinity
  for (const p of preview.value.points) {
    minLat = Math.min(minLat, p.latitude_wgs84)
    maxLat = Math.max(maxLat, p.latitude_wgs84)
    minLon = Math.min(minLon, p.longitude_wgs84)
    maxLon = Math.max(maxLon, p.longitude_wgs84)
  }
  mapRef.value.fitToBounds({ minLat, maxLat, minLon, maxLon }, 15)
}

// 切换地图引擎后地图会重建，需重新调整视野
function handleProviderChanged() {
  if (step.value === 1 && preview.value) {
    setTimeout(fitToPreview, 600)
  }
}

// 执行合并
async function handleMerge() {
  if (!preview.value) return
  const name = mergeName.value.trim()
  if (!name) {
    ElMessage.warning('请输入新轨迹名称')
    return
  }
  merging.value = true
  try {
    const newTrack = await trackApi.mergeTracks(
      selectedTracks.value.map(t => t.id),
      name,
      mergeDescription.value.trim() || undefined,
    )
    ElMessage.success(`合并成功，新轨迹「${newTrack.name}」已创建，原轨迹全部保留`)
    router.push(`/tracks/${newTrack.id}`)
  } catch {
    // 错误已由拦截器统一提示，留在预览步骤
  } finally {
    merging.value = false
  }
}

function handleBack() {
  router.push('/tracks')
}

function goHome() {
  router.push('/home')
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
  loadAllTracks()
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.track-merge-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.el-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color-light);
  padding: 0 16px;
  height: 56px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-left h1 {
  font-size: 18px;
  margin: 0;
}

.merge-main {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.merge-steps {
  flex-shrink: 0;
}

/* 选择步骤 */
.select-toolbar {
  margin-bottom: 12px;
}

.loading-wrapper {
  padding: 8px 0;
}

.mobile-track-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mobile-track-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.mobile-track-card.selected {
  border-color: var(--el-color-primary);
  background-color: var(--el-color-primary-light-9);
}

.mobile-track-card.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.mobile-track-info {
  flex: 1;
  min-width: 0;
}

.mobile-track-name {
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mobile-track-meta {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}

/* 已选摘要 */
.selected-header {
  font-size: 14px;
  color: var(--el-text-color-regular);
  margin-bottom: 8px;
}

.selected-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.selected-tag {
  border: none;
}

.overlap-alert {
  margin-top: 12px;
}

.step-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 8px 0;
}

/* 预览步骤布局：桌面左地图右面板 */
.merge-layout {
  flex: 1;
  display: flex;
  gap: 16px;
  min-height: 0;
}

.map-section {
  flex: 1;
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--el-border-color-lighter);
  min-height: 400px;
}

.map-legend {
  position: absolute;
  bottom: 12px;
  left: 12px;
  z-index: 100;
  background-color: rgba(255, 255, 255, 0.9);
  border-radius: 6px;
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-width: 60%;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.15);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.legend-divider {
  border-top: 1px solid rgba(0, 0, 0, 0.12);
  margin: 4px 0;
}

/* 图例/明细中的线段样式（实线=正常衔接，虚线=空缺） */
.legend-link {
  display: inline-block;
  width: 18px;
  flex-shrink: 0;
}

.legend-link-normal {
  height: 2px;
  background-color: #909399;
}

.legend-link-gap {
  height: 0;
  border-top: 3px dashed #e6a23c;
}

.legend-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.panel-section {
  width: 380px;
  flex-shrink: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.stat-desc {
  flex-shrink: 0;
}

/* 段列表 */
.segment-list {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 12px;
}

/* 空缺明细列表（警告色弱底，与空缺虚线呼应） */
.gap-list {
  border: 1px solid var(--el-color-warning-light-7);
  background-color: var(--el-color-warning-light-9);
  border-radius: 8px;
  padding: 12px;
}

.gap-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 0;
}

.gap-item + .gap-item {
  border-top: 1px dashed var(--el-border-color-lighter);
}

.gap-link-icon {
  margin-top: 9px;
}

.segment-title {
  font-weight: 600;
  margin-bottom: 8px;
}

.segment-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 0;
}

.segment-item + .segment-item {
  border-top: 1px solid var(--el-border-color-extra-light);
}

.segment-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 5px;
}

.segment-info {
  flex: 1;
  min-width: 0;
}

.segment-name {
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.segment-meta {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 2px;
}

.segment-points {
  margin-left: 8px;
}

.segment-removed {
  margin-left: 8px;
  color: var(--el-color-warning);
}

.keep-alert {
  flex-shrink: 0;
}

.preview-loading {
  padding: 24px 0;
}

/* 移动端：上下堆叠 */
@media (max-width: 1366px) {
  .merge-layout {
    flex-direction: column;
  }

  .map-section {
    min-height: 320px;
    height: 45vh;
  }

  .panel-section {
    width: 100%;
    flex-shrink: 0;
  }

  .merge-main {
    padding: 12px;
  }
}
</style>
