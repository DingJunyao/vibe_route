import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { geoEditorApi, type GeoEditorData, type TrackPointGeoData, type GeoSegmentUpdate } from '@/api/geoEditor'

// 轨道类型
export type TrackType = 'province' | 'city' | 'district' | 'roadNumber' | 'roadName'

// 段落接口
export interface TrackSegment {
  id: string
  startIndex: number
  endIndex: number
  pointCount: number
  value: string | null
  valueEn: string | null
  isEdited?: boolean
}

// 轨道接口
export interface TrackTimeline {
  type: TrackType
  label: string
  segments: TrackSegment[]
  hasEnglish: boolean
}

// 历史记录接口
export interface EditHistory {
  id: string
  timestamp: number
  action: 'edit' | 'resize'
  description: string
  before: {
    tracks: TrackTimeline[]
    selectedSegmentIds: string[]
  }
  after: {
    tracks: TrackTimeline[]
    selectedSegmentIds: string[]
  }
}

// 轨道定义
const TRACK_DEFINITIONS: Record<TrackType, { label: string; hasEnglish: boolean; fieldCn: string; fieldEn: string | null }> = {
  province: { label: '省级', hasEnglish: true, fieldCn: 'province', fieldEn: 'province_en' },
  city: { label: '地级', hasEnglish: true, fieldCn: 'city', fieldEn: 'city_en' },
  district: { label: '县级', hasEnglish: true, fieldCn: 'district', fieldEn: 'district_en' },
  roadNumber: { label: '道路编号', hasEnglish: false, fieldCn: 'road_number', fieldEn: null },
  roadName: { label: '道路名称', hasEnglish: true, fieldCn: 'road_name', fieldEn: 'road_name_en' },
}

// 生成唯一ID
const generateId = () => `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`

export const useGeoEditorStore = defineStore('geoEditor', () => {
  // State
  const trackId = ref<number | null>(null)
  const trackName = ref<string>('')
  const points = ref<TrackPointGeoData[]>([])
  const tracks = ref<TrackTimeline[]>([])
  const totalDuration = ref(0)

  // 选择状态
  const selectedSegmentIds = ref<Set<string>>(new Set())
  const hoveredSegmentId = ref<string | null>(null)

  // 刻度显示
  const timeScaleUnit = ref<'time' | 'duration' | 'index'>('time')

  // 折叠状态
  const isChartExpanded = ref(true)
  const isTimelineExpanded = ref(true)

  // 历史记录
  const history = ref<EditHistory[]>([])
  const historyIndex = ref(-1)

  // 持久化
  const hasUnsavedChanges = ref(false)
  const lastSavedAt = ref<number | null>(null)

  // 指针位置（0-1 表示在时间轴上的位置）
  const pointerPosition = ref(0)
  const isPointerDragging = ref(false)

  // 缩放状态（0-1）
  const zoomStart = ref(0)
  const zoomEnd = ref(1)

  // Getters
  const canUndo = computed(() => historyIndex.value > 0)
  const canRedo = computed(() => historyIndex.value < history.value.length - 1)
  const selectedCount = computed(() => selectedSegmentIds.value.size)

  // 获取轨道定义
  const getTrackDefinition = (type: TrackType) => TRACK_DEFINITIONS[type]

  // 获取所有轨道类型
  const getAllTrackTypes = (): TrackType[] => {
    return ['province', 'city', 'district', 'roadNumber', 'roadName']
  }

  // Actions
  async function loadEditorData(trackIdParam: number) {
    const data = await geoEditorApi.getEditorData(trackIdParam)

    trackId.value = data.track_id
    trackName.value = data.name
    points.value = data.points
    totalDuration.value = data.total_duration

    // 初始化轨道
    initializeTracks()

    // 尝试恢复历史记录
    restoreSession(trackIdParam)
  }

  // 初始化轨道（自动分段）
  function initializeTracks() {
    const newTracks: TrackTimeline[] = []

    for (const trackType of getAllTrackTypes()) {
      const definition = getTrackDefinition(trackType)
      const segments = autoSegmentByTrack(trackType)
      newTracks.push({
        type: trackType,
        label: definition.label,
        segments,
        hasEnglish: definition.hasEnglish,
      })
    }

    tracks.value = newTracks
  }

  // 自动分段算法
  function autoSegmentByTrack(trackType: TrackType): TrackSegment[] {
    const definition = getTrackDefinition(trackType)
    const segments: TrackSegment[] = []
    let currentSegment: Omit<TrackSegment, 'id'> | null = null

    for (let index = 0; index < points.value.length; index++) {
      const point = points.value[index]
      const value = point[definition.fieldCn as keyof TrackPointGeoData] as string | null
      const valueEn = definition.fieldEn
        ? (point[definition.fieldEn as keyof TrackPointGeoData] as string | null)
        : null

      if (currentSegment && value === currentSegment.value && valueEn === currentSegment.valueEn) {
        currentSegment.endIndex = index
        currentSegment.pointCount++
      } else {
        if (currentSegment) {
          segments.push({ ...currentSegment, id: generateId() })
        }
        currentSegment = {
          startIndex: index,
          endIndex: index,
          pointCount: 1,
          value,
          valueEn,
        }
      }
    }

    if (currentSegment) {
      segments.push({ ...currentSegment, id: generateId() })
    }

    return segments
  }

  // 记录历史
  function recordHistory(action: EditHistory['action'], description: string) {
    // 如果历史记录为空，先保存初始状态
    if (history.value.length === 0) {
      const initialState = {
        tracks: JSON.parse(JSON.stringify(tracks.value)),
        selectedSegmentIds: Array.from(selectedSegmentIds.value),
      }
      history.value.push({
        id: generateId(),
        timestamp: Date.now(),
        action: 'edit',
        description: '初始状态',
        before: JSON.parse(JSON.stringify(initialState)),
        after: JSON.parse(JSON.stringify(initialState)),
      })
      historyIndex.value = 0
      return // 初始状态不需要再次记录
    }

    const before = history.value[historyIndex.value]?.after
    if (!before) return

    const historyItem: EditHistory = {
      id: generateId(),
      timestamp: Date.now(),
      action,
      description,
      before: {
        tracks: JSON.parse(JSON.stringify(before.tracks)),
        selectedSegmentIds: Array.from(before.selectedSegmentIds),
      },
      after: {
        tracks: JSON.parse(JSON.stringify(tracks.value)),
        selectedSegmentIds: Array.from(selectedSegmentIds.value),
      },
    }

    // 如果在历史中间进行了新操作，删除当前位置之后的所有记录
    if (historyIndex.value < history.value.length - 1) {
      history.value = history.value.slice(0, historyIndex.value + 1)
    }

    history.value.push(historyItem)
    historyIndex.value = history.value.length - 1

    // 限制历史数量
    if (history.value.length > 50) {
      history.value.shift()
      historyIndex.value--
    }

    hasUnsavedChanges.value = true
    persist()
  }

  // 撤销
  function undo() {
    if (!canUndo.value) return
    historyIndex.value--
    restoreState(history.value[historyIndex.value].before)
  }

  // 重做
  function redo() {
    if (!canRedo.value) return
    historyIndex.value++
    restoreState(history.value[historyIndex.value].after)
  }

  // 恢复状态
  function restoreState(state: EditHistory['before'] | EditHistory['after']) {
    tracks.value = JSON.parse(JSON.stringify(state.tracks))
    selectedSegmentIds.value = new Set(state.selectedSegmentIds || [])
    hasUnsavedChanges.value = true
  }

  // 持久化到 LocalStorage
  function persist() {
    if (!trackId.value) return

    const data = {
      history: history.value,
      historyIndex: historyIndex.value,
      tracks: tracks.value,
      savedAt: Date.now(),
    }
    localStorage.setItem(
      `geo-editor-draft-${trackId.value}`,
      JSON.stringify(data)
    )
  }

  // 恢复会话
  function restoreSession(trackIdParam: number) {
    const key = `geo-editor-draft-${trackIdParam}`
    const data = localStorage.getItem(key)
    if (!data) return

    try {
      const parsed = JSON.parse(data)
      history.value = parsed.history || []
      historyIndex.value = parsed.historyIndex || -1
      tracks.value = parsed.tracks || tracks.value

      if (parsed.savedAt) {
        lastSavedAt.value = parsed.savedAt
        hasUnsavedChanges.value = true
      }
    } catch (e) {
      console.error('Failed to restore session:', e)
    }
  }

  // 清除草稿
  function clearDraft() {
    if (!trackId.value) return
    localStorage.removeItem(`geo-editor-draft-${trackId.value}`)
    hasUnsavedChanges.value = false
  }

  // 更新段落值
  function updateSegmentValue(
    trackType: TrackType,
    segmentId: string,
    value: string | null,
    valueEn: string | null
  ) {
    const track = tracks.value.find(t => t.type === trackType)
    if (!track) return

    const segment = track.segments.find(s => s.id === segmentId)
    if (!segment) return

    segment.value = value
    segment.valueEn = valueEn
    segment.isEdited = true

    recordHistory('edit', `编辑${TRACK_DEFINITIONS[trackType].label}`)
  }

  // 保存到服务器
  async function saveToServer() {
    if (!trackId.value) return

    const segments: GeoSegmentUpdate[] = []

    for (const track of tracks.value) {
      const definition = getTrackDefinition(track.type)

      for (const segment of track.segments) {
        if (segment.isEdited) {
          segments.push({
            track_type: track.type === 'roadNumber' ? 'road_number' : 'road_name',
            start_index: segment.startIndex,
            end_index: segment.endIndex,
            value: segment.value,
            value_en: segment.valueEn,
          })
        }
      }
    }

    if (segments.length === 0) return

    await geoEditorApi.updateSegments(trackId.value, { segments })

    // 清除草稿
    clearDraft()

    // 重新加载数据
    await loadEditorData(trackId.value)
  }

  // 选择段落（支持多选）
  function selectSegment(segmentId: string | null, addToSelection: boolean = false) {
    if (segmentId === null) {
      selectedSegmentIds.value.clear()
      return
    }

    if (addToSelection) {
      // 切换选中状态
      if (selectedSegmentIds.value.has(segmentId)) {
        selectedSegmentIds.value.delete(segmentId)
      } else {
        selectedSegmentIds.value.add(segmentId)
      }
    } else {
      // 单选：清除其他，只选中当前
      selectedSegmentIds.value.clear()
      selectedSegmentIds.value.add(segmentId)
    }
  }

  // 清除所有选择
  function clearSelection() {
    selectedSegmentIds.value.clear()
  }

  // 批量清空选中的段落
  function clearSelectedSegments() {
    let clearedCount = 0
    for (const track of tracks.value) {
      for (const segment of track.segments) {
        if (selectedSegmentIds.value.has(segment.id)) {
          segment.value = null
          segment.valueEn = null
          segment.isEdited = true
          clearedCount++
        }
      }
    }

    if (clearedCount > 0) {
      recordHistory('edit', `批量清空 ${clearedCount} 个段落`)
    }
  }

  // 检查是否可以合并（至少有两个连续选中的块）
  function canMergeSelected(): boolean {
    for (const track of tracks.value) {
      const selectedSegments = track.segments
        .filter(s => selectedSegmentIds.value.has(s.id))
        .sort((a, b) => a.startIndex - b.startIndex)

      for (let i = 1; i < selectedSegments.length; i++) {
        if (selectedSegments[i].startIndex === selectedSegments[i - 1].endIndex + 1) {
          return true
        }
      }
    }
    return false
  }

  // 批量合并选中的段落
  function mergeSelectedSegments() {
    let mergedCount = 0
    const idsToKeep = new Set<string>()

    for (const track of tracks.value) {
      // 获取该轨道选中的段落，按位置排序
      const selectedSegments = track.segments
        .filter(s => selectedSegmentIds.value.has(s.id))
        .sort((a, b) => a.startIndex - b.startIndex)

      if (selectedSegments.length < 2) continue

      // 找出连续选中的段落组
      const groups: TrackSegment[][] = []
      let currentGroup: TrackSegment[] = [selectedSegments[0]]

      for (let i = 1; i < selectedSegments.length; i++) {
        const prev = selectedSegments[i - 1]
        const curr = selectedSegments[i]

        // 检查是否连续
        const isConsecutive = curr.startIndex === prev.endIndex + 1

        if (isConsecutive) {
          currentGroup.push(curr)
        } else {
          groups.push([...currentGroup])
          currentGroup = [curr]
        }
      }
      groups.push(currentGroup)

      // 合并每个连续组
      for (const group of groups) {
        if (group.length < 2) continue

        // 找到第一个非空块的值
        const firstNonEmpty = group.find(s => s.value !== null)
        const mergeValue = firstNonEmpty?.value ?? null
        const mergeValueEn = firstNonEmpty?.valueEn ?? null

        // 合并：更新第一个块，标记要保留的 ID
        const first = group[0]
        const last = group[group.length - 1]

        first.endIndex = last.endIndex
        first.pointCount = last.endIndex - first.startIndex + 1
        first.value = mergeValue
        first.valueEn = mergeValueEn
        first.isEdited = true

        idsToKeep.add(first.id)

        // 从轨道中移除其他块
        const idsToRemove = new Set(group.slice(1).map(s => s.id))
        track.segments = track.segments.filter(s => !idsToRemove.has(s.id))

        mergedCount++
      }
    }

    // 更新选择状态：只保留有效的 ID
    selectedSegmentIds.value = idsToKeep

    if (mergedCount > 0) {
      recordHistory('edit', `合并 ${mergedCount} 组段落`)
    }
  }

  // 按轨道获取选中的段落
  function getSelectedSegmentsByTrack(): Record<TrackType, TrackSegment[]> {
    const result: Record<TrackType, TrackSegment[]> = {
      province: [],
      city: [],
      district: [],
      roadNumber: [],
      roadName: [],
    }
    for (const track of tracks.value) {
      for (const segment of track.segments) {
        if (selectedSegmentIds.value.has(segment.id)) {
          result[track.type].push(segment)
        }
      }
    }
    return result
  }

  // 悬停段落
  function hoverSegment(segmentId: string | null) {
    hoveredSegmentId.value = segmentId
  }

  // 缩放控制
  function zoomIn() {
    const range = zoomEnd.value - zoomStart.value
    const center = (zoomStart.value + zoomEnd.value) / 2
    const newRange = range * 0.8
    zoomStart.value = Math.max(0, center - newRange / 2)
    zoomEnd.value = Math.min(1, center + newRange / 2)
  }

  function zoomOut() {
    const range = zoomEnd.value - zoomStart.value
    const center = (zoomStart.value + zoomEnd.value) / 2
    const newRange = Math.min(1, range * 1.25)
    zoomStart.value = Math.max(0, center - newRange / 2)
    zoomEnd.value = Math.min(1, center + newRange / 2)
  }

  // 以指定位置为中心缩放
  // centerPosition: 缩放中心的全局位置 (0-1)
  // factor: 缩放因子，>1 放大，<1 缩小
  function zoomAround(centerPosition: number, factor: number) {
    // 确保中心位置在 [0, 1] 范围内
    const clampedCenter = Math.max(0, Math.min(1, centerPosition))

    // 计算中心在可见范围内的相对位置（如果中心在可见范围外，则钳制到边界）
    let centerRatio = 0.5
    const range = zoomEnd.value - zoomStart.value
    if (range > 0) {
      const centerInRange = Math.max(zoomStart.value, Math.min(zoomEnd.value, clampedCenter))
      centerRatio = (centerInRange - zoomStart.value) / range
    }

    let newRange: number

    if (factor > 1) {
      // 放大：范围变小
      newRange = range / factor
      newRange = Math.max(0.01, newRange) // 最小范围限制
    } else {
      // 缩小：范围变大
      newRange = range * (1 / factor)
      newRange = Math.min(1, newRange) // 最大范围限制
    }

    // 计算新的起点和终点，保持中心位置不变
    let newStart = clampedCenter - newRange * centerRatio
    let newEnd = clampedCenter + newRange * (1 - centerRatio)

    // 边界处理
    if (newStart < 0) {
      newStart = 0
      newEnd = Math.min(1, newRange)
    } else if (newEnd > 1) {
      newEnd = 1
      newStart = Math.max(0, 1 - newRange)
    }

    zoomStart.value = newStart
    zoomEnd.value = newEnd
  }

  function resetZoom() {
    zoomStart.value = 0
    zoomEnd.value = 1
  }

  function setZoom(start: number, end: number) {
    zoomStart.value = Math.max(0, Math.min(1, start))
    zoomEnd.value = Math.max(0, Math.min(1, end))
  }

  // 指针控制
  function setPointerPosition(position: number) {
    pointerPosition.value = Math.max(0, Math.min(1, position))
  }

  function startPointerDrag() {
    isPointerDragging.value = true
  }

  function stopPointerDrag() {
    isPointerDragging.value = false
  }

  return {
    // State
    trackId,
    trackName,
    points,
    tracks,
    totalDuration,
    selectedSegmentIds,
    selectedCount,
    hoveredSegmentId,
    timeScaleUnit,
    isChartExpanded,
    isTimelineExpanded,
    history,
    historyIndex,
    hasUnsavedChanges,
    lastSavedAt,
    pointerPosition,
    isPointerDragging,
    zoomStart,
    zoomEnd,

    // Getters
    canUndo,
    canRedo,

    // Actions
    loadEditorData,
    initializeTracks,
    undo,
    redo,
    persist,
    restoreSession,
    clearDraft,
    updateSegmentValue,
    saveToServer,
    getTrackDefinition,
    getAllTrackTypes,
    selectSegment,
    clearSelection,
    clearSelectedSegments,
    canMergeSelected,
    mergeSelectedSegments,
    getSelectedSegmentsByTrack,
    hoverSegment,
    zoomIn,
    zoomOut,
    zoomAround,
    resetZoom,
    setZoom,
    setPointerPosition,
    startPointerDrag,
    stopPointerDrag,
  }
})
