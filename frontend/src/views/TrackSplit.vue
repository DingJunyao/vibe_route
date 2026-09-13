<template>
  <el-container class="track-split-container">
    <el-header>
      <div class="header-left">
        <el-button :icon="ArrowLeft" class="nav-btn" @click="goBack" />
        <el-button :icon="HomeFilled" class="nav-btn" @click="router.push('/home')" />
        <div class="header-title">
          <h1>拆分轨迹</h1>
          <span>{{ track?.name || '加载中' }}</span>
        </div>
      </div>
      <div class="header-meta">
        <span>{{ formatNumber(points.length) }} 个原始点</span>
        <span>{{ formatDistance(track?.distance) }}</span>
      </div>
    </el-header>

    <el-main class="split-main">
      <div v-if="loading" class="page-loading" v-loading="true" element-loading-text="加载轨迹数据中" />

      <div v-else-if="!track || points.length === 0" class="empty-state">
        <el-empty description="轨迹或轨迹点不存在">
          <el-button type="primary" @click="goBack">返回轨迹详情</el-button>
        </el-empty>
      </div>

      <div v-else class="split-layout">
        <section class="map-section">
          <UniversalMap
            ref="mapRef"
            :custom-overlays="mapOverlays"
            :disable-point-hover="true"
            :highlight-track-id="track.id"
            :tracks="[trackWithPoints]"
            mode="detail"
            @map-click="handleMapClick"
            @map-provider-changed="handleProviderChanged"
          />

          <div class="map-legend">
            <div class="legend-item">
              <span class="legend-line selected-line"></span>
              <span>已选区段</span>
            </div>
            <div class="legend-item">
              <span class="legend-line unselected-line"></span>
              <span>未选区段</span>
            </div>
            <div class="legend-item">
              <span class="legend-dot candidate-dot"></span>
              <span>当前切点</span>
            </div>
          </div>

          <div class="map-hint">点击地图任意位置会立即添加切点；切点会吸附到完整原始点序列中的最近点</div>
        </section>

        <aside class="panel-section">
          <section class="panel-block rules-panel">
            <div class="panel-heading">
              <h2>划分规则</h2>
              <el-switch v-model="autoGroup" active-text="自动" inactive-text="手动" />
            </div>

            <div class="rules-controls">
              <el-select v-model="groupMode" :disabled="!autoGroup" class="dimension-select">
                <el-option label="行政区划：省 / 州" value="province" />
                <el-option label="行政区划：市 / 县" value="city" />
                <el-option label="行政区划：区" value="district" />
                <el-option label="道路编号" value="roadNumber" />
                <el-option label="道路名称" value="roadName" />
              </el-select>
              <div class="minimum-points">
                <span>最短区段点数</span>
                <el-input-number
                  v-model="minimumSegmentPoints"
                  :min="2"
                  :max="100"
                  :step="1"
                  step-strictly
                  size="small"
                  controls-position="right"
                  :disabled="!autoGroup"
                />
              </div>
            </div>

            <div class="rule-summary">
              <span>{{ filteredGroups.length }} 个分组</span>
              <span>{{ workingSegments.length }} 个连续区段</span>
              <span>{{ manualCuts.length }} 个手动切点</span>
            </div>

            <div class="selection-actions">
              <el-button size="small" @click="selectSavableSegments">全选可保存</el-button>
              <el-button size="small" @click="clearSelection">清空选择</el-button>
            </div>
          </section>

          <section class="panel-block candidate-panel">
            <div class="panel-heading">
              <h2>当前切点</h2>
              <el-tag
                v-if="candidatePoint"
                :type="isManualCut ? 'warning' : 'info'"
                size="small"
              >
                {{ candidateStatusLabel }}
              </el-tag>
              <span v-if="candidatePoint" class="candidate-distance">
                偏差 {{ formatDistance(candidateDistance) }}
              </span>
            </div>

            <el-alert
              v-if="!candidatePoint"
              type="info"
              :closable="false"
              title="点击地图立即添加切点；切点会吸附到最近原始点，并可在下方逐点微调。"
            />

            <template v-else>
              <div class="candidate-row">
                <el-button
                  :icon="ArrowLeft"
                  :disabled="candidateIndex <= 0"
                  circle
                  title="上一个原始点"
                  @click="moveCandidate(-1)"
                />
                <el-input-number
                  v-model="candidateIndexModel"
                  :min="1"
                  :max="points.length"
                  :step="1"
                  step-strictly
                  controls-position="right"
                />
                <el-button
                  :icon="ArrowRight"
                  :disabled="candidateIndex >= points.length - 1"
                  circle
                  title="下一个原始点"
                  @click="moveCandidate(1)"
                />
              </div>

              <dl class="point-detail-grid">
                <div>
                  <dt>时间</dt>
                  <dd>{{ formatDateTime(candidatePoint.time) }}</dd>
                </div>
                <div>
                  <dt>坐标</dt>
                  <dd>{{ candidatePoint.latitude_wgs84.toFixed(6) }}, {{ candidatePoint.longitude_wgs84.toFixed(6) }}</dd>
                </div>
                <div>
                  <dt>行政区划</dt>
                  <dd>{{ candidateRegion }}</dd>
                </div>
                <div>
                  <dt>道路</dt>
                  <dd>{{ candidateRoad }}</dd>
                </div>
              </dl>

              <div class="candidate-actions">
                <el-button v-if="isManualCut" type="danger" plain @click="removeSelectedCut">
                  移除切点
                </el-button>
                <el-button @click="clearCandidate">取消选择</el-button>
              </div>
            </template>
          </section>

          <section class="panel-block groups-panel">
            <div class="panel-heading">
              <h2>区段预览</h2>
              <el-input
                v-model="groupQuery"
                :prefix-icon="Search"
                clearable
                placeholder="搜索分组 / 区段"
                class="group-search"
              />
            </div>

            <div v-if="filteredGroups.length === 0" class="groups-empty">没有匹配的分组</div>

            <div v-else class="group-list">
              <article v-for="group in filteredGroups" :key="group.key || 'unknown'" class="group-item">
                <header class="group-header">
                  <span class="group-dot" :style="{ backgroundColor: group.segments[0]?.color || '#909399' }"></span>
                  <div class="group-title">
                    <strong>{{ group.label }}</strong>
                    <span>
                      {{ group.runCount }} 次出现 · {{ formatNumber(group.pointCount) }} 点 ·
                      {{ formatDistance(group.distanceMeters) }}
                    </span>
                  </div>
                </header>

                <div class="segment-list">
                  <div
                    v-for="segment in group.segments"
                    :key="segment.id"
                    class="segment-card"
                    :class="{
                      selected: segment.selected,
                      focused: segment.id === focusedSegmentId,
                      disabled: !segment.savable,
                    }"
                    @click="focusSegment(segment)"
                  >
                    <div class="segment-card-body">
                      <div class="segment-card-main">
                        <el-checkbox
                          :model-value="segment.selected"
                          :disabled="!segment.savable || (!segment.selected && selectedSegments.length >= 100)"
                          label=""
                          @click.stop
                          @change="toggleSegment(segment)"
                        />
                        <div class="segment-copy">
                          <strong>区段 {{ segment.sequence }}</strong>
                          <span>
                            #{{ segment.startIndex + 1 }} - #{{ segment.endIndex + 1 }} ·
                            {{ segment.pointCount }} 点 · {{ formatDistance(segment.distanceMeters) }}
                          </span>
                          <span>{{ formatTimeRange(segment.startTime, segment.endTime) }}</span>
                          <span v-if="!segment.savable" class="invalid-segment">少于 2 点，不能单独创建轨迹</span>
                        </div>
                      </div>

                      <el-input
                        v-model="segmentNames[segment.id]"
                        :placeholder="defaultSegmentName(segment)"
                        class="segment-name-input"
                        size="small"
                        @click.stop
                      />
                    </div>

                    <div class="segment-card-actions">
                      <el-tooltip content="定位到区段" placement="top">
                        <el-button :icon="Aim" circle size="small" @click.stop="focusSegment(segment)" />
                      </el-tooltip>
                      <el-tooltip
                        v-if="segment.startIndex > 0"
                        content="并入上一区段"
                        placement="top"
                      >
                        <el-button
                          :icon="ArrowUp"
                          circle
                          size="small"
                          @click.stop="mergeIntoPrevious(segment)"
                        />
                      </el-tooltip>
                    </div>
                  </div>
                </div>
              </article>
            </div>
          </section>

          <section class="panel-block submit-panel">
            <div class="panel-heading">
              <h2>保存摘要</h2>
              <el-tag :type="selectedSegments.length > 100 ? 'danger' : 'success'" size="small">
                {{ selectedSegments.length }}/100
              </el-tag>
            </div>

            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="将创建新轨迹">
                {{ selectedSegments.length }} 条
              </el-descriptions-item>
              <el-descriptions-item label="覆盖原始点">
                {{ formatNumber(selectedPointCount) }} / {{ formatNumber(points.length) }}
              </el-descriptions-item>
              <el-descriptions-item label="覆盖距离">
                {{ formatDistance(selectedDistance) }}
              </el-descriptions-item>
              <el-descriptions-item label="原轨迹">
                保留，不做修改
              </el-descriptions-item>
            </el-descriptions>

            <div v-if="createdTracks.length > 0" class="created-list">
              <div class="created-title">已创建：</div>
              <router-link
                v-for="created in createdTracks"
                :key="created.id"
                :to="`/tracks/${created.id}`"
                class="created-link"
              >
                {{ created.name }}
              </router-link>
            </div>

            <el-button
              type="primary"
              class="submit-button"
              :loading="splitting"
              :disabled="selectedSegments.length === 0 || selectedSegments.length > 100"
              @click="submitSplit"
            >
              <el-icon><Scissor /></el-icon>
              按所选区段创建新轨迹
            </el-button>
          </section>
        </aside>
      </div>
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Aim,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  HomeFilled,
  Scissor,
  Search,
} from '@element-plus/icons-vue'
import UniversalMap from '@/components/map/UniversalMap.vue'
import { trackApi, type Track, type TrackPoint } from '@/api/track'
import {
  addManualCut,
  buildContiguousSegments,
  findNearestSplitPoint,
  mergeShortSegments,
  moveManualCut,
  refineSegmentsWithCuts,
  type ContiguousSplitSegment,
  type SplitGroupMode,
} from '@/utils/trackSplitSegments'
import { formatDateTime, formatDistance, formatTimeRange } from '@/utils/format'
import { wgs84ToBd09, wgs84ToGcj02 } from '@/utils/coordTransform'

interface SplitSegmentView extends ContiguousSplitSegment {
  sequence: number
  color: string
  selected: boolean
  savable: boolean
  startTime: string | null
  endTime: string | null
}

interface SplitGroupView {
  key: string
  label: string
  runCount: number
  pointCount: number
  distanceMeters: number
  segments: SplitSegmentView[]
}

interface SplitOverlayPolyline {
  type: 'polyline'
  positions: Array<[number, number]>
  positions_gcj02?: Array<[number, number]>
  positions_bd09?: Array<[number, number]>
  color: string
  weight: number
  opacity: number
}

interface SplitOverlayMarker {
  type: 'marker'
  position: [number, number]
  latitude_wgs84: number
  longitude_wgs84: number
  latitude_gcj02: number
  longitude_gcj02: number
  latitude_bd09: number
  longitude_bd09: number
  icon: {
    type: 'circle'
    radius: number
    fillColor: string
    fillOpacity: number
    strokeColor: string
    strokeWidth: number
  }
  label: string
}

type SplitOverlay = SplitOverlayPolyline | SplitOverlayMarker

const SEGMENT_COLORS = [
  '#2563eb',
  '#16a34a',
  '#d97706',
  '#dc2626',
  '#7c3aed',
  '#0891b2',
  '#db2777',
  '#65a30d',
]

const route = useRoute()
const router = useRouter()
const trackId = computed(() => Number(route.params.id))
const track = shallowRef<Track | null>(null)
const points = shallowRef<TrackPoint[]>([])
const loading = ref(false)
const splitting = ref(false)
const createdTracks = shallowRef<Track[]>([])

const autoGroup = ref(true)
const groupMode = ref<SplitGroupMode>('province')
const minimumSegmentPoints = ref(5)
const disabledAutoBoundaries = ref<Set<number>>(new Set())
const manualCuts = ref<number[]>([])
const selectedSegmentIds = ref<Set<string>>(new Set())
const segmentNames = reactive<Record<string, string>>({})
const groupQuery = ref('')
const focusedSegmentId = ref<string | null>(null)
const candidateIndex = ref<number | null>(null)
const candidateDistance = ref(0)
const mapRef = ref()

const validPoints = computed(() => points.value)

const trackWithPoints = computed(() => {
  if (!track.value) return null
  return { ...track.value, points: validPoints.value }
})

const automaticSegments = computed(() => {
  if (!autoGroup.value || validPoints.value.length === 0) return []
  const contiguousSegments = buildContiguousSegments(validPoints.value, groupMode.value)
  return mergeShortSegments(
    contiguousSegments,
    validPoints.value,
    minimumSegmentPoints.value,
    groupMode.value,
  )
})

const activeAutomaticSegments = computed(() => automaticSegments.value.filter(segment =>
  segment.startIndex === 0 || !disabledAutoBoundaries.value.has(segment.startIndex)
))

const workingSegments = computed<ContiguousSplitSegment[]>(() => {
  if (validPoints.value.length === 0) return []
  const baseSegments = autoGroup.value ? activeAutomaticSegments.value : []
  return refineSegmentsWithCuts(baseSegments, manualCuts.value, validPoints.value, groupMode.value)
})

const segmentBoundaryStarts = computed(() =>
  new Set(workingSegments.value.map(segment => segment.startIndex))
)

const segmentViews = computed<SplitSegmentView[]>(() => workingSegments.value.map((segment, index) => {
  const startPoint = validPoints.value[segment.startIndex]
  const endPoint = validPoints.value[segment.endIndex]
  return {
    ...segment,
    sequence: index + 1,
    color: selectedSegmentIds.value.has(segment.id)
      ? SEGMENT_COLORS[index % SEGMENT_COLORS.length]
      : '#94a3b8',
    selected: selectedSegmentIds.value.has(segment.id),
    savable: segment.pointCount >= 2,
    startTime: startPoint?.time || null,
    endTime: endPoint?.time || null,
  }
}))

const selectedSegments = computed(() => segmentViews.value.filter(segment => segment.selected && segment.savable))
const selectedPointCount = computed(() => selectedSegments.value.reduce((sum, segment) => sum + segment.pointCount, 0))
const selectedDistance = computed(() => selectedSegments.value.reduce((sum, segment) => sum + segment.distanceMeters, 0))

const filteredGroups = computed<SplitGroupView[]>(() => {
  const query = groupQuery.value.trim().toLowerCase()
  const groups: SplitGroupView[] = []
  const groupMap = new Map<string, SplitGroupView>()

  for (const segment of segmentViews.value) {
    if (query && !segment.label.toLowerCase().includes(query) && !`${segment.sequence}`.includes(query)) continue
    let group = groupMap.get(segment.key)
    if (!group) {
      group = {
        key: segment.key,
        label: segment.label,
        runCount: 0,
        pointCount: 0,
        distanceMeters: 0,
        segments: [],
      }
      groupMap.set(segment.key, group)
      groups.push(group)
    }
    group.runCount += 1
    group.pointCount += segment.pointCount
    group.distanceMeters += segment.distanceMeters
    group.segments.push(segment)
  }

  return groups
})

const candidatePoint = computed(() => {
  if (candidateIndex.value === null) return null
  return validPoints.value[candidateIndex.value] || null
})

const isManualCut = computed(() => {
  if (candidateIndex.value === null) return false
  return manualCuts.value.includes(candidateIndex.value)
})

const isSegmentBoundary = computed(() => {
  if (candidateIndex.value === null) return false
  return segmentBoundaryStarts.value.has(candidateIndex.value)
})

const candidateStatusLabel = computed(() => {
  if (!candidatePoint.value) return ''
  if (isManualCut.value) return '手动切点'
  return isSegmentBoundary.value ? '自动边界' : '未设切点'
})

const candidateMarkerLabel = computed(() => {
  if (!candidatePoint.value) return ''
  if (isManualCut.value) return '切点'
  return isSegmentBoundary.value ? '边界' : '当前点'
})

const candidateMarkerColor = computed(() => isManualCut.value ? '#f97316' : '#1f2937')

const candidateIndexModel = computed({
  get: () => (candidateIndex.value === null ? 1 : candidateIndex.value + 1),
  set: (value: number | null) => {
    if (value === null) return
    selectCandidateIndex(value - 1)
  },
})

const candidateRegion = computed(() => {
  const point = candidatePoint.value
  if (!point) return '-'
  return [point.province, point.city, point.district].filter(Boolean).join(' / ') || '未识别'
})

const candidateRoad = computed(() => {
  const point = candidatePoint.value
  if (!point) return '-'
  return [point.road_number, point.road_name].filter(Boolean).join(' · ') || '未识别'
})

function formatNumber(value: number): string {
  return value.toLocaleString('zh-CN')
}

function defaultSegmentName(segment: SplitSegmentView): string {
  const sourceName = track.value?.name?.trim() || '轨迹'
  const label = segment.label === '未识别' ? `区段 ${segment.sequence}` : segment.label
  return `${sourceName} - ${label}`.slice(0, 200)
}

function resetSegments() {
  disabledAutoBoundaries.value = new Set()
  manualCuts.value = []
  focusedSegmentId.value = null
  Object.keys(segmentNames).forEach(key => delete segmentNames[key])
  selectSavableSegments()
}

function selectSavableSegments() {
  const ids = segmentViews.value
    .filter(segment => segment.savable)
    .slice(0, 100)
    .map(segment => segment.id)
  selectedSegmentIds.value = new Set(ids)
}

function clearSelection() {
  selectedSegmentIds.value = new Set()
}

function toggleSegment(segment: SplitSegmentView) {
  if (!segment.savable) return
  const next = new Set(selectedSegmentIds.value)
  if (next.has(segment.id)) {
    next.delete(segment.id)
  } else if (next.size < 100) {
    next.add(segment.id)
  }
  selectedSegmentIds.value = next
}

function handleMapClick(longitude: number, latitude: number) {
  if (validPoints.value.length === 0) return
  const nearest = findNearestSplitPoint(validPoints.value, longitude, latitude)
  if (nearest.index < 0) return
  candidateIndex.value = nearest.index
  candidateDistance.value = nearest.distanceMeters

  if (nearest.index === 0 || nearest.index === validPoints.value.length - 1) {
    ElMessage.warning('起点和终点不能作为切点')
    return
  }

  const nextCuts = addManualCut(
    manualCuts.value,
    nearest.index,
    validPoints.value.length,
    [...segmentBoundaryStarts.value],
  )
  if (nextCuts === manualCuts.value) {
    if (!manualCuts.value.includes(nearest.index)) {
      ElMessage.info('该点已经是区段边界，未重复添加切点')
    }
    return
  }

  manualCuts.value = nextCuts
  selectSavableSegments()
  ElMessage.success('已添加切点')
}

function selectCandidateIndex(index: number) {
  const targetIndex = Math.min(Math.max(index, 0), validPoints.value.length - 1)
  const currentIndex = candidateIndex.value

  if (currentIndex !== null && manualCuts.value.includes(currentIndex)) {
    const nextCuts = moveManualCut(
      manualCuts.value,
      currentIndex,
      targetIndex,
      validPoints.value.length,
      [...segmentBoundaryStarts.value],
    )
    if (nextCuts === manualCuts.value) {
      ElMessage.warning('目标点无效或已是区段边界，未移动切点')
      return
    }

    manualCuts.value = nextCuts
    candidateIndex.value = targetIndex
    selectSavableSegments()
    return
  }

  candidateIndex.value = targetIndex
}

function moveCandidate(delta: number) {
  if (candidateIndex.value === null) return
  selectCandidateIndex(candidateIndex.value + delta)
}

function clearCandidate() {
  candidateIndex.value = null
  candidateDistance.value = 0
}

function removeSelectedCut() {
  if (candidateIndex.value === null) return
  manualCuts.value = manualCuts.value.filter(cut => cut !== candidateIndex.value)
  selectSavableSegments()
  ElMessage.success('已移除切点')
}

function mergeIntoPrevious(segment: SplitSegmentView) {
  if (segment.startIndex <= 0) return
  const manualIndex = manualCuts.value.indexOf(segment.startIndex)
  if (manualIndex >= 0) {
    manualCuts.value = manualCuts.value.filter((_, index) => index !== manualIndex)
  } else {
    const next = new Set(disabledAutoBoundaries.value)
    next.add(segment.startIndex)
    disabledAutoBoundaries.value = next
  }
  selectSavableSegments()
}

function segmentBounds(segment: SplitSegmentView) {
  let minLat = Infinity
  let maxLat = -Infinity
  let minLon = Infinity
  let maxLon = -Infinity
  for (const point of validPoints.value.slice(segment.startIndex, segment.endIndex + 1)) {
    minLat = Math.min(minLat, point.latitude_wgs84)
    maxLat = Math.max(maxLat, point.latitude_wgs84)
    minLon = Math.min(minLon, point.longitude_wgs84)
    maxLon = Math.max(maxLon, point.longitude_wgs84)
  }
  return { minLat, maxLat, minLon, maxLon }
}

function focusSegment(segment: SplitSegmentView) {
  focusedSegmentId.value = segment.id
  const bounds = segmentBounds(segment)
  mapRef.value?.fitToBounds?.(bounds, 25)
}

function pointGcj02(point: TrackPoint): [number, number] {
  if (point.latitude_gcj02 != null && point.longitude_gcj02 != null) {
    return [point.latitude_gcj02, point.longitude_gcj02]
  }
  const [longitude, latitude] = wgs84ToGcj02(point.longitude_wgs84, point.latitude_wgs84)
  return [latitude, longitude]
}

function pointBd09(point: TrackPoint): [number, number] {
  if (point.latitude_bd09 != null && point.longitude_bd09 != null) {
    return [point.latitude_bd09, point.longitude_bd09]
  }
  const [longitude, latitude] = wgs84ToBd09(point.longitude_wgs84, point.latitude_wgs84)
  return [latitude, longitude]
}

function makeMarker(point: TrackPoint, label: string, fillColor: string, radius: number): SplitOverlayMarker {
  const gcj02 = pointGcj02(point)
  const bd09 = pointBd09(point)
  return {
    type: 'marker',
    position: [point.latitude_wgs84, point.longitude_wgs84],
    latitude_wgs84: point.latitude_wgs84,
    longitude_wgs84: point.longitude_wgs84,
    latitude_gcj02: gcj02[0],
    longitude_gcj02: gcj02[1],
    latitude_bd09: bd09[0],
    longitude_bd09: bd09[1],
    icon: {
      type: 'circle',
      radius,
      fillColor,
      fillOpacity: 1,
      strokeColor: '#ffffff',
      strokeWidth: 2,
    },
    label,
  }
}

const mapOverlays = computed<SplitOverlay[]>(() => {
  const overlays: SplitOverlay[] = []
  for (const segment of segmentViews.value) {
    const segmentPoints = validPoints.value.slice(segment.startIndex, segment.endIndex + 1)
    if (segmentPoints.length >= 2) {
      overlays.push({
        type: 'polyline',
        positions: segmentPoints.map(point => [point.latitude_wgs84, point.longitude_wgs84]),
        positions_gcj02: segmentPoints.map(pointGcj02),
        positions_bd09: segmentPoints.map(pointBd09),
        color: segment.color,
        weight: segment.selected ? 7 : 4,
        opacity: segment.selected ? 0.95 : 0.5,
      })
    } else {
      overlays.push(makeMarker(segmentPoints[0], `${segment.sequence}`, segment.color, 7))
    }

    if (segment.startIndex > 0) {
      overlays.push(makeMarker(validPoints.value[segment.startIndex], `B${segment.sequence}`, '#1f2937', 7))
    }
  }

  if (candidatePoint.value) {
    overlays.push(makeMarker(
      candidatePoint.value,
      candidateMarkerLabel.value,
      candidateMarkerColor.value,
      isManualCut.value ? 10 : 8,
    ))
  }
  return overlays
})

async function loadData() {
  if (!Number.isFinite(trackId.value) || trackId.value <= 0) return
  loading.value = true
  try {
    const [trackResponse, pointsResponse] = await Promise.all([
      trackApi.getDetail(trackId.value),
      trackApi.getPoints(trackId.value),
    ])
    track.value = trackResponse
    points.value = pointsResponse.points
    resetSegments()
    await nextTick()
    setTimeout(() => mapRef.value?.fitBounds?.(), 500)
  } catch {
    track.value = null
    points.value = []
  } finally {
    loading.value = false
  }
}

async function submitSplit() {
  if (selectedSegments.value.length === 0 || selectedSegments.value.length > 100) return
  splitting.value = true
  try {
    const response = await trackApi.splitTracks(
      trackId.value,
      selectedSegments.value.map(segment => ({
        start_index: segment.startIndex,
        end_index: segment.endIndex,
        name: segmentNames[segment.id]?.trim() || defaultSegmentName(segment),
      })),
    )
    createdTracks.value = response.tracks
    ElMessage.success(`已创建 ${response.tracks.length} 条新轨迹，原轨迹已保留`)
  } catch {
    // HTTP 拦截器已展示错误。
  } finally {
    splitting.value = false
  }
}

function goBack() {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push(`/tracks/${trackId.value}`)
  }
}

function handleProviderChanged() {
  setTimeout(() => mapRef.value?.fitBounds?.(), 600)
}

watch(autoGroup, () => resetSegments())
watch(groupMode, () => resetSegments())
watch(minimumSegmentPoints, () => resetSegments())

onMounted(loadData)
</script>

<style scoped>
.track-split-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.el-header {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--el-border-color-light);
  background: var(--el-bg-color);
  padding: 0 16px;
}

.header-left,
.header-title,
.header-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.header-title h1 {
  margin: 0;
  font-size: 18px;
}

.header-title span {
  max-width: 38vw;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.header-meta {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  flex-shrink: 0;
}

.split-main {
  flex: 1;
  min-height: 0;
  padding: 0;
}

.page-loading,
.empty-state {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.split-layout {
  height: 100%;
  display: flex;
}

.map-section {
  position: relative;
  flex: 1;
  min-width: 0;
}

.map-legend {
  position: absolute;
  left: 14px;
  bottom: 14px;
  z-index: 100;
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.16);
  font-size: 12px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.legend-line {
  width: 18px;
  height: 3px;
  border-radius: 2px;
}

.selected-line {
  background: #2563eb;
}

.unselected-line {
  background: #94a3b8;
}

.legend-dot,
.candidate-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
}

.candidate-dot {
  background: #f97316;
}

.map-hint {
  position: absolute;
  top: 14px;
  left: 14px;
  z-index: 100;
  max-width: min(430px, calc(100% - 28px));
  padding: 7px 10px;
  border-radius: 6px;
  background: rgba(15, 23, 42, 0.78);
  color: #fff;
  font-size: 12px;
}

.panel-section {
  width: 430px;
  flex-shrink: 0;
  overflow-y: auto;
  border-left: 1px solid var(--el-border-color-light);
  background: #f5f7fa;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.panel-block {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 7px;
  background: var(--el-bg-color);
  padding: 12px;
}

.panel-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.panel-heading h2 {
  margin: 0;
  font-size: 15px;
}

.dimension-select {
  width: 100%;
}

.rules-controls {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.minimum-points {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.minimum-points :deep(.el-input-number) {
  width: 104px;
}

.rule-summary,
.selection-actions,
.candidate-row,
.candidate-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.rule-summary {
  flex-wrap: wrap;
  margin-top: 10px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.selection-actions,
.candidate-actions {
  justify-content: flex-end;
  margin-top: 10px;
}

.candidate-row {
  justify-content: center;
}

.candidate-distance {
  color: var(--el-color-warning);
  font-size: 12px;
}

.point-detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin: 12px 0 0;
}

.point-detail-grid div {
  min-width: 0;
  padding: 7px 8px;
  border-radius: 5px;
  background: #f8fafc;
}

.point-detail-grid dt {
  color: var(--el-text-color-secondary);
  font-size: 11px;
}

.point-detail-grid dd {
  margin: 3px 0 0;
  font-size: 12px;
  overflow-wrap: anywhere;
}

.group-search {
  width: 180px;
}

.groups-empty {
  color: var(--el-text-color-secondary);
  padding: 12px 0;
  text-align: center;
}

.group-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.group-item + .group-item {
  border-top: 1px solid var(--el-border-color-extra-light);
  padding-top: 10px;
}

.group-header {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.group-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  margin-top: 5px;
  flex-shrink: 0;
}

.group-title {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.group-title strong {
  font-size: 13px;
  overflow-wrap: anywhere;
}

.group-title span {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.segment-list {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.segment-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
}

.segment-card.selected {
  border-color: var(--el-color-primary-light-5);
  background: var(--el-color-primary-light-9);
}

.segment-card.focused {
  box-shadow: 0 0 0 2px var(--el-color-primary-light-5);
}

.segment-card.disabled {
  opacity: 0.72;
}

.segment-card-body {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.segment-card-main {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  min-width: 0;
}

.segment-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.segment-copy strong {
  color: var(--el-text-color-primary);
  font-size: 13px;
}

.invalid-segment {
  color: var(--el-color-warning);
}

.segment-card-actions {
  display: flex;
  flex-shrink: 0;
  gap: 5px;
}

.submit-panel {
  position: sticky;
  bottom: 0;
  z-index: 2;
  box-shadow: 0 -4px 14px rgba(15, 23, 42, 0.08);
}

.created-list {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.created-title,
.created-link {
  font-size: 12px;
}

.created-link {
  color: var(--el-color-primary);
}

.submit-button {
  width: 100%;
  margin-top: 12px;
}

@media (max-width: 1366px) {
  .split-layout {
    flex-direction: column;
    overflow-y: auto;
  }

  .map-section {
    height: 48vh;
    min-height: 320px;
    flex-shrink: 0;
  }

  .panel-section {
    width: 100%;
    border-left: none;
    border-top: 1px solid var(--el-border-color-light);
    overflow: visible;
  }

  .header-title span {
    max-width: 32vw;
  }
}
</style>
