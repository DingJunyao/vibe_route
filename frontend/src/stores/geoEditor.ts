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
  action: 'edit' | 'resize' | 'move'
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
  async function loadEditorData(trackIdParam: number, skipRestoreSession: boolean = false) {
    const data = await geoEditorApi.getEditorData(trackIdParam)

    trackId.value = data.track_id
    trackName.value = data.name
    points.value = data.points
    totalDuration.value = data.total_duration

    // 初始化轨道
    initializeTracks()

    // 尝试恢复历史记录（除非跳过）
    if (!skipRestoreSession) {
      restoreSession(trackIdParam)
    }

    // 如果历史记录为空或无效（historyIndex < 0），创建基准快照
    if (history.value.length === 0 || historyIndex.value < 0) {
      const initialSnapshot = {
        tracks: JSON.parse(JSON.stringify(tracks.value)),
        selectedSegmentIds: Array.from(selectedSegmentIds.value),
      }
      history.value = [{
        id: generateId(),
        timestamp: Date.now(),
        action: 'initialize',
        description: '初始状态',
        before: initialSnapshot,
        after: initialSnapshot,
      }]
      historyIndex.value = 0
    }
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
    // 获取 before 状态（使用当前历史记录的 after）
    const currentState = history.value[historyIndex.value].after

    const historyItem: EditHistory = {
      id: generateId(),
      timestamp: Date.now(),
      action,
      description,
      before: {
        tracks: JSON.parse(JSON.stringify(currentState.tracks)),
        selectedSegmentIds: Array.from(currentState.selectedSegmentIds),
      },
      after: {
        tracks: JSON.parse(JSON.stringify(tracks.value)),
        selectedSegmentIds: Array.from(selectedSegmentIds.value),
      },
    }

    // 检查是否有实际变化
    const beforeTracks = JSON.stringify(historyItem.before.tracks)
    const afterTracks = JSON.stringify(historyItem.after.tracks)
    const beforeSelected = JSON.stringify(historyItem.before.selectedSegmentIds)
    const afterSelected = JSON.stringify(historyItem.after.selectedSegmentIds)
    const hasNoChange = beforeTracks === afterTracks && beforeSelected === afterSelected

    // 如果没有实际变化，不记录历史
    if (hasNoChange) {
      return
    }

    // 如果在历史中间进行了新操作，删除当前位置之后的所有记录
    if (historyIndex.value < history.value.length - 1) {
      history.value = history.value.slice(0, historyIndex.value + 1)
    }

    history.value.push(historyItem)
    historyIndex.value = history.value.length - 1

    // 限制历史数量（注意保留基准快照）
    if (history.value.length > 51) {
      history.value.splice(1, 1)  // 删除第二个元素，保留基准快照
      historyIndex.value--
    }

    hasUnsavedChanges.value = true
    persist()
  }

  // 撤销
  function undo() {
    if (!canUndo.value) return

    historyIndex.value--
    restoreState(history.value[historyIndex.value].after)
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
      historyIndex.value = parsed.historyIndex ?? -1
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

  // 清除历史记录
  function clearHistory() {
    history.value = []
    historyIndex.value = -1
  }

  // 重置编辑状态（用于重新载入）
  function resetEditorState() {
    clearHistory()
    selectedSegmentIds.value.clear()
    hoveredSegmentId.value = null
    resetZoom()
    setPointerPosition(0)
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

  // 检查是否可以拆分（有选中的块且指针位置在有效范围内）
  function canSplitSelected(): boolean {
    if (points.value.length === 0) return false
    const splitIndex = Math.round(pointerPosition.value * (points.value.length - 1))

    for (const track of tracks.value) {
      for (const segment of track.segments) {
        if (selectedSegmentIds.value.has(segment.id)) {
          // 拆分点必须在块内部（不能在边界）
          if (splitIndex > segment.startIndex && splitIndex < segment.endIndex) {
            return true
          }
        }
      }
    }
    return false
  }

  // 拆分选中的段落
  function splitSelectedSegments() {
    if (points.value.length === 0) return
    const splitIndex = Math.round(pointerPosition.value * (points.value.length - 1))
    const newSelectionIds = new Set<string>()
    let splitCount = 0

    for (const track of tracks.value) {
      const newSegments: TrackSegment[] = []

      for (const segment of track.segments) {
        if (selectedSegmentIds.value.has(segment.id)) {
          // 检查拆分点是否在块内部（不在边界上）
          if (splitIndex > segment.startIndex && splitIndex < segment.endIndex) {
            // 拆分为两个块
            const leftSegment: TrackSegment = {
              id: generateId(),
              startIndex: segment.startIndex,
              endIndex: splitIndex,
              pointCount: splitIndex - segment.startIndex + 1,
              value: segment.value,
              valueEn: segment.valueEn,
              isEdited: true,
            }
            const rightSegment: TrackSegment = {
              id: generateId(),
              startIndex: splitIndex + 1,
              endIndex: segment.endIndex,
              pointCount: segment.endIndex - splitIndex,
              value: segment.value,
              valueEn: segment.valueEn,
              isEdited: true,
            }
            newSegments.push(leftSegment, rightSegment)
            newSelectionIds.add(leftSegment.id)
            newSelectionIds.add(rightSegment.id)
            splitCount++
          } else {
            // 拆分点无效（在边界上），保留原块
            newSegments.push(segment)
          }
        } else {
          newSegments.push(segment)
        }
      }

      track.segments = newSegments
    }

    // 更新选中状态为新生成的两个块
    selectedSegmentIds.value = newSelectionIds

    if (splitCount > 0) {
      recordHistory('edit', `拆分 ${splitCount} 个段落`)
    }
  }

  // 最小段落大小（点数）
  const MIN_SEGMENT_SIZE = 3

  // 检查段落是否与其他段落重叠
  function checkNoOverlap(
    track: TrackTimeline,
    segmentId: string,
    newStart: number,
    newEnd: number
  ): boolean {
    for (const seg of track.segments) {
      if (seg.id === segmentId) continue

      // 跳过空块（空块不阻挡其他块的调整）
      if (!seg.value) continue

      // 检查是否有重叠：
      // - 新段落完全在左边：newEnd < seg.startIndex（允许）
      // - 新段落完全在右边：newStart > seg.endIndex（允许）
      // - 其他情况都有重叠（不允许）
      const isNewLeftOfOther = newEnd < seg.startIndex
      const isNewRightOfOther = newStart > seg.endIndex

      if (!isNewLeftOfOther && !isNewRightOfOther) {
        // 有重叠
        return false
      }
    }
    return true
  }

  // 获取指定位置处的相邻段落
  function getAdjacentSegments(
    track: TrackTimeline,
    segmentId: string,
    newStart: number,
    newEnd: number
  ): { before: TrackSegment | null; after: TrackSegment | null } {
    let before: TrackSegment | null = null
    let after: TrackSegment | null = null

    for (const seg of track.segments) {
      if (seg.id === segmentId) continue
      if (seg.endIndex === newStart - 1) before = seg
      if (seg.startIndex === newEnd + 1) after = seg
    }

    return { before, after }
  }

  // 检查是否需要合并（与相邻同值段落）
  // 空块不自动合并，保持各自的独立性
  function shouldAutoMerge(
    segment: TrackSegment,
    adjacent: TrackSegment | null
  ): boolean {
    if (!adjacent) return false
    // 空块不自动合并
    if (!segment.value || !adjacent.value) return false
    return segment.value === adjacent.value && segment.valueEn === adjacent.valueEn
  }

  // 处理与段落重叠的空块，并填补新空出来的区域
  // 空块不自动合并，保持各自的独立性
  function adjustOverlappingEmptyBlocks(
    track: TrackTimeline,
    segmentId: string,
    oldStart: number,
    oldEnd: number,
    newStart: number,
    newEnd: number
  ): number {
    const segment = track.segments.find(s => s.id === segmentId)
    if (!segment) return 0

    const isSegmentEmpty = !segment.value
    const segmentsToRemove: Set<string> = new Set()
    const segmentsToAdd: Omit<TrackSegment, 'id'>[] = []

    // 保存所有空块的原始位置（用于后续判断）
    const originalEmptyPositions = new Map<string, { start: number; end: number }>()
    for (const s of track.segments) {
      if (!s.value && s.id !== segmentId) {
        originalEmptyPositions.set(s.id, { start: s.startIndex, end: s.endIndex })
      }
    }

    // ========================================
    // 第一步：处理原位置留下的空隙（先处理原位置！）
    // ========================================

    // 检测是否是 resize 操作（只有一边改变）
    const isResize = oldStart === newStart || oldEnd === newEnd
    const isLeftResize = oldEnd === newEnd && oldStart !== newStart  // 调整左边界
    const isRightResize = oldStart === newStart && oldEnd !== newEnd  // 调整右边界

    if (isSegmentEmpty && isResize) {
      // ========================================
      // 空块 resize：不扩展邻居，创建新空块填补空白
      // ========================================
      if (isLeftResize) {
        // 调整左边界：右边空出来
        if (newStart > oldStart) {
          // 左边界右移，右边有空隙 (oldEnd+1 到 oldEnd 变成空隙? 不对)
          // 空块原本是 (oldStart, oldEnd)，现在是 (newStart, newEnd=newEnd)
          // 左边空出来的是 (oldStart, newStart-1)
          const gapStart = oldStart
          const gapEnd = newStart - 1
          if (gapStart <= gapEnd) {
            track.segments.push({
              id: generateId(),
              startIndex: gapStart,
              endIndex: gapEnd,
              pointCount: gapEnd - gapStart + 1,
              value: null,
              valueEn: null,
              isEdited: false,
            })
          }
        } else {
          // 左边界左移，需要检查是否覆盖了其他块
          // 这个情况由第二步处理
        }
      } else if (isRightResize) {
        // 调整右边界：右边空出来
        if (newEnd < oldEnd) {
          // 右边界左移，右边有空隙 (newEnd+1, oldEnd)
          const gapStart = newEnd + 1
          const gapEnd = oldEnd
          if (gapStart <= gapEnd) {
            track.segments.push({
              id: generateId(),
              startIndex: gapStart,
              endIndex: gapEnd,
              pointCount: gapEnd - gapStart + 1,
              value: null,
              valueEn: null,
              isEdited: false,
            })
          }
        } else {
          // 右边界右移，需要检查是否覆盖了其他块
          // 这个情况由第二步处理
        }
      }
    } else if (isSegmentEmpty) {
      // ========================================
      // 空块移动：找出原始位置的邻居并扩展
      // ========================================
      let originalLeftNeighbor: TrackSegment | null = null
      let originalRightNeighbor: TrackSegment | null = null

      for (const s of track.segments) {
        if (s.id === segmentId) continue
        const originalPos = originalEmptyPositions.get(s.id)
        if (!originalPos) continue

        // 基于原始位置判断邻居
        if (originalPos.end < oldStart) {
          // 左边邻居：找最右边的
          if (!originalLeftNeighbor || originalPos.end > (originalEmptyPositions.get(originalLeftNeighbor.id)?.end ?? -1)) {
            originalLeftNeighbor = s
          }
        }
        if (originalPos.start > oldEnd) {
          // 右边邻居：找最左边的
          if (!originalRightNeighbor || originalPos.start < (originalEmptyPositions.get(originalRightNeighbor.id)?.start ?? Infinity)) {
            originalRightNeighbor = s
          }
        }
      }

      // 先扩展邻居填补原位置（在移动之前）
      if (originalLeftNeighbor) {
        // 左邻居：扩展到包含原位置（暂时不考虑新位置重叠）
        originalLeftNeighbor.endIndex = oldEnd
        originalLeftNeighbor.pointCount = originalLeftNeighbor.endIndex - originalLeftNeighbor.startIndex + 1
      }

      if (originalRightNeighbor && !originalLeftNeighbor) {
        // 只有右邻居时才扩展右邻居
        originalRightNeighbor.startIndex = oldStart
        originalRightNeighbor.pointCount = originalRightNeighbor.endIndex - originalRightNeighbor.startIndex + 1
      }

      // 如果都没有邻居，创建新空块
      if (!originalLeftNeighbor && !originalRightNeighbor) {
        track.segments.push({
          id: generateId(),
          startIndex: oldStart,
          endIndex: oldEnd,
          pointCount: oldEnd - oldStart + 1,
          value: null,
          valueEn: null,
          isEdited: false,
        })
      }
    } else {
      // 正常块移动：填补原位置的空隙
      let currentPos = oldStart
      const segmentsInRange = track.segments
        .filter(s => s.id !== segmentId && s.startIndex <= oldEnd && s.endIndex >= oldStart)
        .sort((a, b) => a.startIndex - b.startIndex)

      for (const existing of segmentsInRange) {
        if (currentPos < existing.startIndex) {
          track.segments.push({
            id: generateId(),
            startIndex: currentPos,
            endIndex: existing.startIndex - 1,
            pointCount: existing.startIndex - currentPos,
            value: null,
            valueEn: null,
            isEdited: false,
          })
        }
        currentPos = Math.max(currentPos, existing.endIndex + 1)
      }

      if (currentPos <= oldEnd) {
        track.segments.push({
          id: generateId(),
          startIndex: currentPos,
          endIndex: oldEnd,
          pointCount: oldEnd - currentPos + 1,
          value: null,
          valueEn: null,
          isEdited: false,
        })
      }
    }

    // ========================================
    // 第二步：处理被移动段落在新位置与其他段落的重叠
    // ========================================
    const allOtherSegments = track.segments.filter(s => s.id !== segmentId)

    for (const other of allOtherSegments) {
      // 使用严格的重叠检测：必须有真正的交集，相接不算重叠
      const hasOverlap = newStart <= other.endIndex && newEnd >= other.startIndex

      if (!hasOverlap) continue

      // 两个空块之间的重叠：调整另一个的边界
      if (isSegmentEmpty && !other.value) {
        // 判断相对位置：比较原始起始位置
        const otherOriginalPos = originalEmptyPositions.get(other.id)
        const otherOriginalStart = otherOriginalPos?.start ?? other.startIndex

        if (otherOriginalStart < oldStart) {
          // other 原本在左边，调整其结束位置（不能超过新位置起点）
          const newOtherEnd = newStart - 1
          if (newOtherEnd >= other.startIndex) {
            other.endIndex = newOtherEnd
            other.pointCount = other.endIndex - other.startIndex + 1
          } else {
            segmentsToRemove.add(other.id)
          }
        } else {
          // other 原本在右边，调整其起始位置（不能小于新位置终点）
          const newOtherStart = newEnd + 1
          if (newOtherStart <= other.endIndex) {
            other.startIndex = newOtherStart
            other.pointCount = other.endIndex - other.startIndex + 1
          } else {
            segmentsToRemove.add(other.id)
          }
        }
        continue
      }

      // 正常块与空块的重叠
      if (!isSegmentEmpty && !other.value) {
        // 情况1：空块完全被正常块包含 -> 删除空块
        if (newStart <= other.startIndex && newEnd >= other.endIndex) {
          segmentsToRemove.add(other.id)
          continue
        }

        // 情况2：正常块完全在空块内部 -> 将空块分成两部分
        if (other.startIndex < newStart && other.endIndex > newEnd) {
          segmentsToRemove.add(other.id)

          if (other.startIndex <= newStart - 1) {
            segmentsToAdd.push({
              startIndex: other.startIndex,
              endIndex: newStart - 1,
              pointCount: newStart - other.startIndex,
              value: null,
              valueEn: null,
              isEdited: false,
            })
          }

          if (other.endIndex >= newEnd + 1) {
            segmentsToAdd.push({
              startIndex: newEnd + 1,
              endIndex: other.endIndex,
              pointCount: other.endIndex - newEnd,
              value: null,
              valueEn: null,
              isEdited: false,
            })
          }

          continue
        }

        // 情况3：正常块与空块左侧重叠
        if (newEnd >= other.startIndex && newStart <= other.startIndex) {
          const newEmptyStart = newEnd + 1
          if (newEmptyStart > other.endIndex) {
            segmentsToRemove.add(other.id)
          } else {
            other.startIndex = newEmptyStart
            other.pointCount = other.endIndex - other.startIndex + 1
          }
          continue
        }

        // 情况4：正常块与空块右侧重叠
        if (newStart <= other.endIndex && newEnd >= other.endIndex) {
          const newEmptyEnd = newStart - 1
          if (newEmptyEnd < other.startIndex) {
            segmentsToRemove.add(other.id)
          } else {
            other.endIndex = newEmptyEnd
            other.pointCount = other.endIndex - other.startIndex + 1
          }
          continue
        }
      }
    }

    // 移除被标记删除的段落
    if (segmentsToRemove.size > 0) {
      track.segments = track.segments.filter(s => !segmentsToRemove.has(s.id))
      segmentsToRemove.forEach(id => selectedSegmentIds.value.delete(id))
    }

    // 添加新分割的空块
    for (const newSegment of segmentsToAdd) {
      track.segments.push({
        ...newSegment,
        id: generateId(),
      })
    }

    // ========================================
    // 第二步补：对于空块移动，如果有右邻居，扩展它填补左侧的空白
    // ========================================
    if (isSegmentEmpty) {
      // 找出原始位置的右邻居
      let originalRightNeighbor: TrackSegment | null = null
      for (const s of track.segments) {
        if (s.id === segmentId) continue
        const originalPos = originalEmptyPositions.get(s.id)
        if (originalPos && originalPos.start > oldEnd) {
          if (!originalRightNeighbor || originalPos.start < (originalEmptyPositions.get(originalRightNeighbor.id)?.start ?? Infinity)) {
            originalRightNeighbor = s
          }
        }
      }

      // 如果有右邻居，检查它左侧是否有空白需要填补
      if (originalRightNeighbor) {
        // 计算被移动段落结束位置与右邻居开始位置之间的空白
        const gapAfterMovedSegment = newEnd + 1
        if (originalRightNeighbor.startIndex > gapAfterMovedSegment) {
          // 有空白，扩展右邻居
          originalRightNeighbor.startIndex = gapAfterMovedSegment
          originalRightNeighbor.pointCount = originalRightNeighbor.endIndex - originalRightNeighbor.startIndex + 1
        }
      }
    }

    // ========================================
    // 第三步：确保整个轨道被完全覆盖（无空白区域）
    // ========================================
    const totalPts = points.value.length

    // 收集所有段落（包括刚添加的）的范围
    const allRanges: Array<{ start: number; end: number }> = []
    for (const seg of track.segments) {
      allRanges.push({ start: seg.startIndex, end: seg.endIndex })
    }

    // 按起始位置排序
    allRanges.sort((a, b) => a.start - b.start)

    // 找出所有空隙并填补
    let currentPos = 0
    for (const range of allRanges) {
      if (currentPos < range.start) {
        track.segments.push({
          id: generateId(),
          startIndex: currentPos,
          endIndex: range.start - 1,
          pointCount: range.start - currentPos,
          value: null,
          valueEn: null,
          isEdited: false,
        })
      }
      currentPos = range.end + 1
    }

    // 处理末尾的空区域
    if (currentPos < totalPts) {
      track.segments.push({
        id: generateId(),
        startIndex: currentPos,
        endIndex: totalPts - 1,
        pointCount: totalPts - currentPos,
        value: null,
        valueEn: null,
        isEdited: false,
      })
    }

    // 重新排序段落
    track.segments.sort((a, b) => a.startIndex - b.startIndex)

    return segmentsToRemove.size + segmentsToAdd.length
  }

  // 拖动调整段落大小
  function resizeSegment(
    trackType: TrackType,
    segmentId: string,
    newStartIndex: number,
    newEndIndex: number
  ): { success: boolean; message?: string; autoMerged?: boolean } {
    const track = tracks.value.find(t => t.type === trackType)
    if (!track) {
      return { success: false, message: '轨道不存在' }
    }

    const segment = track.segments.find(s => s.id === segmentId)
    if (!segment) {
      return { success: false, message: '段落不存在' }
    }

    // 验证最小尺寸
    if (newEndIndex - newStartIndex + 1 < MIN_SEGMENT_SIZE) {
      return { success: false, message: `段落不能小于 ${MIN_SEGMENT_SIZE} 个点` }
    }

    // 验证不交叉
    if (!checkNoOverlap(track, segmentId, newStartIndex, newEndIndex)) {
      return { success: false, message: '段落位置与其他段落冲突' }
    }

    // 检查自动合并
    const { before, after } = getAdjacentSegments(track, segmentId, newStartIndex, newEndIndex)
    let autoMerged = false
    let finalSegmentId = segmentId

    // 更新段落位置
    const oldStart = segment.startIndex
    const oldEnd = segment.endIndex

    segment.startIndex = newStartIndex
    segment.endIndex = newEndIndex
    segment.pointCount = newEndIndex - newStartIndex + 1
    segment.isEdited = true

    // 处理重叠的空块
    adjustOverlappingEmptyBlocks(track, segmentId, oldStart, oldEnd, newStartIndex, newEndIndex)

    // 检查并执行合并
    const idsToMerge: string[] = []
    if (shouldAutoMerge(segment, before)) idsToMerge.push(before!.id)
    if (shouldAutoMerge(segment, after)) idsToMerge.push(after!.id)

    if (idsToMerge.length > 0) {
      // 合并逻辑：将所有同值段落合并为一个大段落
      const allRelatedSegments = [segment, ...idsToMerge.map(id => track.segments.find(s => s.id === id)!)]
        .filter(Boolean)
        .sort((a, b) => a.startIndex - b.startIndex)

      const mergedSegment = allRelatedSegments[0]
      mergedSegment.startIndex = Math.min(...allRelatedSegments.map(s => s.startIndex))
      mergedSegment.endIndex = Math.max(...allRelatedSegments.map(s => s.endIndex))
      mergedSegment.pointCount = mergedSegment.endIndex - mergedSegment.startIndex + 1
      mergedSegment.isEdited = true

      // 移除被合并的段落
      track.segments = track.segments.filter(s => !idsToMerge.includes(s.id))

      // 更新选中状态
      idsToMerge.forEach(id => selectedSegmentIds.value.delete(id))
      selectedSegmentIds.value.add(mergedSegment.id)

      finalSegmentId = mergedSegment.id
      autoMerged = true
    }

    // 记录历史
    const direction = newStartIndex < oldStart ? '左' : newStartIndex > oldStart ? '右' : '双向'
    recordHistory('resize', `调整${TRACK_DEFINITIONS[trackType].label}段落${direction}边界`)

    return { success: true, autoMerged }
  }

  // 拖动移动段落
  function moveSegment(
    trackType: TrackType,
    segmentId: string,
    targetStartIndex: number
  ): { success: boolean; message?: string; autoMerged?: boolean } {
    const track = tracks.value.find(t => t.type === trackType)
    if (!track) {
      return { success: false, message: '轨道不存在' }
    }

    const segment = track.segments.find(s => s.id === segmentId)
    if (!segment) {
      return { success: false, message: '段落不存在' }
    }

    const size = segment.pointCount
    const targetEndIndex = targetStartIndex + size - 1

    // 检查是否移动到了原位置
    if (targetStartIndex === segment.startIndex) {
      return { success: true, autoMerged: false }
    }

    // 验证边界
    if (targetStartIndex < 0 || targetEndIndex >= points.value.length) {
      return { success: false, message: '超出轨迹范围' }
    }

    // 验证不交叉
    if (!checkNoOverlap(track, segmentId, targetStartIndex, targetEndIndex)) {
      return { success: false, message: '目标位置与其他段落冲突' }
    }

    // 更新段落位置
    const oldStart = segment.startIndex
    const oldEnd = segment.endIndex

    segment.startIndex = targetStartIndex
    segment.endIndex = targetEndIndex
    segment.isEdited = true

    // 处理重叠的空块
    adjustOverlappingEmptyBlocks(track, segmentId, oldStart, oldEnd, targetStartIndex, targetEndIndex)

    // 检查自动合并
    const { before, after } = getAdjacentSegments(track, segmentId, targetStartIndex, targetEndIndex)
    let autoMerged = false
    let finalSegmentId = segmentId

    const idsToMerge: string[] = []
    if (shouldAutoMerge(segment, before)) idsToMerge.push(before!.id)
    if (shouldAutoMerge(segment, after)) idsToMerge.push(after!.id)

    if (idsToMerge.length > 0) {
      // 合并逻辑
      const allRelatedSegments = [segment, ...idsToMerge.map(id => track.segments.find(s => s.id === id)!)]
        .filter(Boolean)
        .sort((a, b) => a.startIndex - b.startIndex)

      const mergedSegment = allRelatedSegments[0]
      mergedSegment.startIndex = Math.min(...allRelatedSegments.map(s => s.startIndex))
      mergedSegment.endIndex = Math.max(...allRelatedSegments.map(s => s.endIndex))
      mergedSegment.pointCount = mergedSegment.endIndex - mergedSegment.startIndex + 1
      mergedSegment.isEdited = true

      track.segments = track.segments.filter(s => !idsToMerge.includes(s.id))

      idsToMerge.forEach(id => selectedSegmentIds.value.delete(id))
      selectedSegmentIds.value.add(mergedSegment.id)

      finalSegmentId = mergedSegment.id
      autoMerged = true
    }

    // 记录历史
    const moveDistance = targetStartIndex > oldStart ? `+${targetStartIndex - oldStart}` : `${targetStartIndex - oldStart}`
    recordHistory('move', `移动${TRACK_DEFINITIONS[trackType].label}段落 ${moveDistance} 点`)

    return { success: true, autoMerged }
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
    clearHistory,
    resetEditorState,
    updateSegmentValue,
    saveToServer,
    getTrackDefinition,
    getAllTrackTypes,
    selectSegment,
    clearSelection,
    clearSelectedSegments,
    canMergeSelected,
    mergeSelectedSegments,
    canSplitSelected,
    splitSelectedSegments,
    resizeSegment,
    moveSegment,
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
