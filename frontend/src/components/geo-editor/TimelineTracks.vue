<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import type { TrackTimeline, TrackSegment, TrackType } from '@/stores/geo_editor'
import { ElMessageBox, ElMessage } from 'element-plus'
import { useGeoEditorStore } from '@/stores/geoEditor'
import { geoEditorApi } from '@/api/geoEditor'

interface Props {
  tracks: TrackTimeline[]
  selectedSegmentIds: Set<string>
  hoveredSegmentId: string | null
  zoomStart: number
  zoomEnd: number
}

const props = defineProps<Props>()

const emit = defineEmits<{
  select: [segmentId: string | null, addToSelection: boolean]
  hover: [segmentId: string | null]
  save: [data: { trackType: TrackType; segmentId: string; value: string; valueEn: string | null }]
  'multi-select-change': [isActive: boolean]
  resize: [data: { trackType: TrackType; segmentId: string; newStartIndex: number; newEndIndex: number }]
  move: [data: { trackType: TrackType; segmentId: string; targetStartIndex: number }]
  'dialog-open': [isOpen: boolean]
}>()

const geoEditorStore = useGeoEditorStore()

// 移动端检测
const isMobile = computed(() => window.innerWidth <= 1366)

// 修饰键状态（用于多选）
const isCtrlPressed = ref(false)
const isShiftPressed = ref(false)

// 键盘事件处理
function handleKeyDown(e: KeyboardEvent) {
  if (e.key === 'Control') isCtrlPressed.value = true
  if (e.key === 'Shift') isShiftPressed.value = true
}

function handleKeyUp(e: KeyboardEvent) {
  if (e.key === 'Control') isCtrlPressed.value = false
  if (e.key === 'Shift') isShiftPressed.value = false
}

// 生命周期钩子
onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
  window.addEventListener('keyup', handleKeyUp)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
  window.removeEventListener('keyup', handleKeyUp)
})

// 移动端双击检测
const lastTapTime = ref(0)
const lastTapSegmentId = ref('')
const DOUBLE_TAP_DELAY = 300  // 双击间隔（毫秒）

// 移动端多选模式（长按进入）
const isMultiSelectMode = ref(false)
const longPressTimer = ref<number | null>(null)
const LONG_PRESS_DURATION = 500  // 长按触发时长（毫秒）
const longPressElement = ref<HTMLElement | null>(null)

// 移动端编辑模式（长按选中块进入）
const isEditMode = ref(false)
const editModeSegmentId = ref<string | null>(null)

// 桌面端拖动状态
const isDragging = ref(false)
const dragType = ref<'resize-left' | 'resize-right' | 'move' | null>(null)
const dragTrackType = ref<TrackType | null>(null)  // 拖动所在的轨道类型
const dragSegmentId = ref<string | null>(null)
const dragStartX = ref(0)
const dragOriginalSegment = ref<{ startIndex: number; endIndex: number; pointCount: number } | null>(null)
const dragCurrentIndex = ref(0)  // 当前拖动到的索引
const previewLeft = ref(0)  // 预览框位置（百分比）
const previewWidth = ref(0)  // 预览框宽度（百分比）

// 移动端拖动状态
const isMobileDragging = ref(false)
const mobileDragStartX = ref(0)
const mobileDragStartIndex = ref(0)

// 长按开始
function handleLongPressStart(segmentId: string, e: TouchEvent) {
  // 清除之前的定时器
  if (longPressTimer.value) {
    clearTimeout(longPressTimer.value)
  }

  const touch = e.touches[0]
  longPressElement.value = e.target as HTMLElement

  longPressTimer.value = window.setTimeout(() => {
    // 检查是否是已选中的块
    const isAlreadySelected = props.selectedSegmentIds.has(segmentId)

    if (isAlreadySelected) {
      // 已选中的块：进入编辑模式
      isEditMode.value = true
      editModeSegmentId.value = segmentId

      // 触觉反馈（三次短震动表示编辑模式）
      if ('vibrate' in navigator) {
        navigator.vibrate([50, 50, 50])
      }
    } else {
      // 未选中的块：进入多选模式
      isMultiSelectMode.value = true
      emit('select', segmentId, true)  // addToSelection = true

      // 触觉反馈
      if ('vibrate' in navigator) {
        navigator.vibrate(50)
      }
    }
  }, LONG_PRESS_DURATION)
}

// 长按取消（移动或松开）
function handleLongPressCancel() {
  if (longPressTimer.value) {
    clearTimeout(longPressTimer.value)
    longPressTimer.value = null
  }
  longPressElement.value = null
}

// 记录触摸开始位置，用于判断是否是点击（而非拖动）
const touchStartPos = ref({ x: 0, y: 0 })

// 移动端触摸处理（单击选中 + 双击编辑 + 长按多选）
function handleTouchStart(trackType: TrackType, segment: TrackSegment, e: TouchEvent) {
  if (e.touches.length !== 1) return

  const now = Date.now()
  const touch = e.touches[0]
  const isDoubleTap =
    now - lastTapTime.value < DOUBLE_TAP_DELAY &&
    lastTapSegmentId.value === segment.id

  // 记录触摸开始位置
  touchStartPos.value = { x: touch.clientX, y: touch.clientY }

  if (isDoubleTap) {
    // 双击：打开编辑对话框
    e.preventDefault()
    handleDoubleClick(trackType, segment)
    // 重置状态
    lastTapTime.value = 0
    lastTapSegmentId.value = ''
    handleLongPressCancel()
  } else if (isEditMode.value && editModeSegmentId.value === segment.id) {
    // 编辑模式：开始拖动
    e.preventDefault()
    handleMobileDragStart(trackType, segment, e)
  } else if (isMultiSelectMode.value) {
    // 多选模式：切换选中状态
    e.preventDefault()
    emit('select', segment.id, true)  // addToSelection = true
    // 记录单击时间但不重置多选模式
    lastTapTime.value = now
    lastTapSegmentId.value = segment.id
  } else {
    // 普通模式：记录单击时间和块ID，启动长按检测
    lastTapTime.value = now
    lastTapSegmentId.value = segment.id
    handleLongPressStart(segment.id, e)
  }
}

// 触摸移动，取消长按
function handleTouchMove(e: TouchEvent) {
  // 如果在拖动中，不取消
  if (!isMobileDragging.value) {
    handleLongPressCancel()
  }
}

function handleTouchEnd(e: TouchEvent) {
  // 如果长按已触发（进入多选模式或编辑模式），不做处理
  if (isMultiSelectMode.value || isEditMode.value) {
    handleLongPressCancel()
    return
  }

  // 取消长按定时器
  const hadLongPress = longPressTimer.value !== null
  handleLongPressCancel()

  // 如果已经触发了长按，不处理单击
  if (hadLongPress) return

  // 检查是否是轻微移动（算作点击）
  const touch = e.changedTouches[0]
  const deltaX = Math.abs(touch.clientX - touchStartPos.value.x)
  const deltaY = Math.abs(touch.clientY - touchStartPos.value.y)
  const isClick = deltaX < 10 && deltaY < 10

  if (isClick && lastTapSegmentId.value) {
    // 单击：选中该块（短暂延迟以检测双击）
    setTimeout(() => {
      // 检查是否仍然是单击（没有变成双击）
      if (lastTapTime.value > 0 && lastTapSegmentId.value) {
        emit('select', lastTapSegmentId.value, false)
      }
    }, DOUBLE_TAP_DELAY)
  }
}

// ==================== 拖动相关函数 ====================

// 将像素位置转换为点索引
function positionToIndex(xPercent: number): number {
  // xPercent 是相对于可见区域的位置 (0-100)
  // 需要转换为相对于整个轨迹的位置
  const globalPosition = (props.zoomStart + xPercent / 100 * (props.zoomEnd - props.zoomStart))
  return Math.round(globalPosition * totalPoints.value)
}

// 将点索引转换为可见区域内的百分比位置（左边缘）
function indexToVisiblePercent(index: number): number {
  const globalPosition = index / totalPoints.value
  return ((globalPosition - props.zoomStart) / (props.zoomEnd - props.zoomStart)) * 100
}

// 计算段落在可见区域内的宽度和位置
function getSegmentBounds(startIndex: number, endIndex: number): { left: number; width: number } {
  // 左边界：startIndex 的位置
  const left = indexToVisiblePercent(startIndex)

  // 右边界：(endIndex + 1) 的位置，但不能超过总点数
  const rightIndex = Math.min(endIndex + 1, totalPoints.value)
  const right = indexToVisiblePercent(rightIndex)

  return {
    left,
    width: Math.max(0, right - left)
  }
}

// 桌面端：检测鼠标在段落上的位置（左侧手柄、右侧手柄、中心区域）
function getMouseArea(e: MouseEvent, element: HTMLElement): 'left' | 'right' | 'center' {
  const rect = element.getBoundingClientRect()
  const x = e.clientX - rect.left
  const width = rect.width
  const HANDLE_WIDTH = 6  // 手柄宽度

  if (x <= HANDLE_WIDTH) return 'left'
  if (x >= width - HANDLE_WIDTH) return 'right'
  return 'center'
}

// 桌面端：开始拖动
function handleDragStart(trackType: TrackType, segment: TrackSegment, e: MouseEvent) {
  const element = e.currentTarget as HTMLElement
  const area = getMouseArea(e, element)

  if (area === 'center') {
    // 移动模式
    dragType.value = 'move'
  } else {
    // 调整大小模式
    dragType.value = area === 'left' ? 'resize-left' : 'resize-right'
  }

  isDragging.value = true
  dragTrackType.value = trackType
  dragSegmentId.value = segment.id
  dragStartX.value = e.clientX
  dragOriginalSegment.value = {
    startIndex: segment.startIndex,
    endIndex: segment.endIndex,
    pointCount: segment.pointCount
  }
  dragCurrentIndex.value = segment.startIndex

  // 记录原始位置用于预览（使用 getSegmentBounds 确保宽度正确）
  const bounds = getSegmentBounds(segment.startIndex, segment.endIndex)
  previewLeft.value = bounds.left
  previewWidth.value = bounds.width

  // 添加全局事件监听
  document.addEventListener('mousemove', handleDragMove)
  document.addEventListener('mouseup', handleDragEnd)

  e.preventDefault()
}

// 桌面端：拖动中
function handleDragMove(e: MouseEvent) {
  if (!isDragging.value || !dragSegmentId.value || !dragOriginalSegment.value) return

  const deltaX = e.clientX - dragStartX.value
  const pointsPerPixel = (props.zoomEnd - props.zoomStart) * totalPoints.value / window.innerWidth

  if (dragType.value === 'move') {
    // 移动模式：计算新位置
    const deltaIndex = Math.round(deltaX * pointsPerPixel)
    const original = dragOriginalSegment.value
    const newStartIndex = Math.max(0, Math.min(
      totalPoints.value - original.pointCount,
      original.startIndex + deltaIndex
    ))
    dragCurrentIndex.value = newStartIndex

    // 更新预览位置（使用 getSegmentBounds）
    const bounds = getSegmentBounds(newStartIndex, newStartIndex + original.pointCount - 1)
    previewLeft.value = bounds.left
    previewWidth.value = bounds.width
  } else if (dragType.value === 'resize-left') {
    // 调整左边界
    const deltaIndex = Math.round(deltaX * pointsPerPixel)
    const original = dragOriginalSegment.value
    const newStartIndex = Math.max(0, Math.min(
      original.endIndex - 2,  // 保持最小3个点的间距
      original.startIndex + deltaIndex
    ))
    dragCurrentIndex.value = newStartIndex

    // 更新预览（使用 getSegmentBounds）
    const bounds = getSegmentBounds(newStartIndex, original.endIndex)
    previewLeft.value = bounds.left
    previewWidth.value = bounds.width
  } else if (dragType.value === 'resize-right') {
    // 调整右边界
    const deltaIndex = Math.round(deltaX * pointsPerPixel)
    const original = dragOriginalSegment.value
    const newEndIndex = Math.max(
      original.startIndex + 2,  // 保持最小3个点的间距
      Math.min(totalPoints.value - 1, original.endIndex + deltaIndex)
    )
    dragCurrentIndex.value = newEndIndex

    // 更新预览（使用 getSegmentBounds）
    const bounds = getSegmentBounds(original.startIndex, newEndIndex)
    previewLeft.value = bounds.left
    previewWidth.value = bounds.width
  }
}

// 桌面端：结束拖动
function handleDragEnd(e: MouseEvent) {
  if (!isDragging.value || !dragSegmentId.value || !dragOriginalSegment.value) return

  document.removeEventListener('mousemove', handleDragMove)
  document.removeEventListener('mouseup', handleDragEnd)

  // 找到对应的轨道和段落
  const track = props.tracks.find(t =>
    t.segments.some(s => s.id === dragSegmentId.value)
  )
  if (!track) {
    resetDragState()
    return
  }

  const original = dragOriginalSegment.value

  // 执行操作
  if (dragType.value === 'move') {
    const newStartIndex = dragCurrentIndex.value
    // 只有位置真正改变时才发送事件
    if (newStartIndex !== original.startIndex) {
      emit('move', {
        trackType: track.type,
        segmentId: dragSegmentId.value,
        targetStartIndex: newStartIndex
      })
    }
  } else if (dragType.value === 'resize-left') {
    const newStartIndex = dragCurrentIndex.value
    if (newStartIndex !== original.startIndex) {
      emit('resize', {
        trackType: track.type,
        segmentId: dragSegmentId.value,
        newStartIndex,
        newEndIndex: original.endIndex
      })
    }
  } else if (dragType.value === 'resize-right') {
    const newEndIndex = dragCurrentIndex.value
    if (newEndIndex !== original.endIndex) {
      emit('resize', {
        trackType: track.type,
        segmentId: dragSegmentId.value,
        newStartIndex: original.startIndex,
        newEndIndex
      })
    }
  }

  resetDragState()
}

// 重置拖动状态
function resetDragState() {
  isDragging.value = false
  dragType.value = null
  dragTrackType.value = null
  dragSegmentId.value = null
  dragStartX.value = 0
  dragOriginalSegment.value = null
  dragCurrentIndex.value = 0
  previewLeft.value = 0
  previewWidth.value = 0
}

// 移动端：进入编辑模式（长按已选中的块）
function enterEditMode(trackType: TrackType, segment: TrackSegment) {
  // 只有已选中的块才能进入编辑模式
  if (!props.selectedSegmentIds.has(segment.id)) return

  isEditMode.value = true
  editModeSegmentId.value = segment.id

  // 触觉反馈
  if ('vibrate' in navigator) {
    navigator.vibrate([50, 50, 50])  // 三次短震动
  }
}

// 退出编辑模式
function exitEditMode() {
  isEditMode.value = false
  editModeSegmentId.value = null
}

// 移动端：开始拖动（编辑模式下）
function handleMobileDragStart(trackType: TrackType, segment: TrackSegment, e: TouchEvent) {
  if (!isEditMode.value || editModeSegmentId.value !== segment.id) return

  e.preventDefault()
  isMobileDragging.value = true
  mobileDragStartX.value = e.touches[0].clientX
  mobileDragStartIndex.value = segment.startIndex

  // 使用 getSegmentBounds 确保预览正确
  const bounds = getSegmentBounds(segment.startIndex, segment.endIndex)
  previewLeft.value = bounds.left
  previewWidth.value = bounds.width

  document.addEventListener('touchmove', handleMobileDragMove, { passive: false })
  document.addEventListener('touchend', handleMobileDragEnd)
}

// 移动端：拖动中
function handleMobileDragMove(e: TouchEvent) {
  if (!isMobileDragging.value) return

  e.preventDefault()
  const touch = e.touches[0]
  const deltaX = touch.clientX - mobileDragStartX.value

  // 计算新位置（简化为移动模式）
  const pointsPerPixel = (props.zoomEnd - props.zoomStart) * totalPoints.value / window.innerWidth
  const deltaIndex = Math.round(deltaX * pointsPerPixel)
  const newIndex = Math.max(0, mobileDragStartIndex.value + deltaIndex)

  // 获取原始段落大小来计算新边界
  const track = props.tracks.find(t => t.segments.some(s => s.id === editModeSegmentId.value))
  if (track) {
    const segment = track.segments.find(s => s.id === editModeSegmentId.value)
    if (segment) {
      dragCurrentIndex.value = newIndex
      const pointCount = segment.endIndex - segment.startIndex + 1
      const newEndIndex = newIndex + pointCount - 1
      const bounds = getSegmentBounds(newIndex, newEndIndex)
      previewLeft.value = bounds.left
      previewWidth.value = bounds.width
    }
  }
}

// 移动端：结束拖动
async function handleMobileDragEnd(e: TouchEvent) {
  if (!isMobileDragging.value) return

  document.removeEventListener('touchmove', handleMobileDragMove)
  document.removeEventListener('touchend', handleMobileDragEnd)

  isMobileDragging.value = false

  // 显示确认对话框
  await showMoveConfirmDialog()
}

// 显示移动确认对话框
async function showMoveConfirmDialog() {
  const track = props.tracks.find(t =>
    t.segments.some(s => s.id === editModeSegmentId.value)
  )
  if (!track) return

  const segment = track.segments.find(s => s.id === editModeSegmentId.value)
  if (!segment) return

  const oldStart = segment.startIndex
  const newStart = dragCurrentIndex.value
  const oldEnd = segment.endIndex
  const newEnd = newStart + (oldEnd - oldStart)

  try {
    await ElMessageBox.confirm(
      `起点: ${oldStart} → ${newStart}\n终点: ${oldEnd} → ${newEnd}`,
      '确认移动段落',
      {
        confirmButtonText: '确认',
        cancelButtonText: '取消',
        type: 'info',
      }
    )

    // 用户确认，执行移动
    emit('move', {
      trackType: track.type,
      segmentId: editModeSegmentId.value!,
      targetStartIndex: newStart
    })
  } catch {
    // 用户取消
  }

  exitEditMode()
  resetDragState()
}

// 轨道配置
const TRACK_CONFIG = {
  province: { label: '省级', hasEnglish: true, placeholder: '如：北京市' },
  city: { label: '地级', hasEnglish: true, placeholder: '如：北京市' },
  district: { label: '县级', hasEnglish: true, placeholder: '如：朝阳区' },
  roadNumber: { label: '道路编号', hasEnglish: false, placeholder: '如：G221' },
  roadName: { label: '道路名称', hasEnglish: true, placeholder: '如：京哈高速' },
}

// 编辑对话框状态
const editDialogVisible = ref(false)
const editTrackType = ref<TrackType>('province')
const editSegmentId = ref('')
const editValue = ref('')
const editValueEn = ref('')
const isTranslating = ref(false)

// 记录用户是否手动编辑过英文（在对话框打开期间持久有效）
const userManuallyEditedEnglish = ref(false)

// 记录是否通过 Tab 键切换焦点（用于阻止 blur 时的自动填充）
const isTabSwitching = ref(false)

// 轨道类型到 API 类型的映射
function trackTypeToApiType(trackType: TrackType): 'province' | 'city' | 'district' | 'road_name' | null {
  const typeMap: Record<TrackType, 'province' | 'city' | 'district' | 'road_name' | null> = {
    province: 'province',
    city: 'city',
    district: 'district',
    roadNumber: null,  // 道路编号不支持英文翻译
    roadName: 'road_name',
  }
  return typeMap[trackType]
}

// 计算总点数
const totalPoints = computed(() => {
  if (props.tracks.length === 0) return 0
  return props.tracks[0]?.segments.reduce((sum, seg) => sum + seg.pointCount, 0) || 0
})

// 计算可见段落（只显示缩放范围内的段落）
const visibleSegments = computed(() => {
  const result: Array<{ segment: TrackSegment; trackType: TrackType; visibleStart: number; visibleWidth: number }> = []

  for (const track of props.tracks) {
    for (const segment of track.segments) {
      const segmentStart = segment.startIndex / totalPoints.value
      const segmentEnd = (segment.startIndex + segment.pointCount) / totalPoints.value

      // 计算段落与可见区域的交集
      const overlapStart = Math.max(props.zoomStart, segmentStart)
      const overlapEnd = Math.min(props.zoomEnd, segmentEnd)

      if (overlapStart < overlapEnd) {
        // 转换为相对于可见区域的百分比
        const visibleStart = (overlapStart - props.zoomStart) / (props.zoomEnd - props.zoomStart)
        const visibleWidth = (overlapEnd - overlapStart) / (props.zoomEnd - props.zoomStart)

        result.push({
          segment,
          trackType: track.type,
          visibleStart: visibleStart * 100,
          visibleWidth: visibleWidth * 100,
        })
      }
    }
  }

  return result
})

// 双击编辑
function handleDoubleClick(trackType: TrackType, segment: TrackSegment) {
  editTrackType.value = trackType
  editSegmentId.value = segment.id
  editValue.value = segment.value || ''
  editValueEn.value = segment.valueEn || ''
  editDialogVisible.value = true
  // 重置用户编辑标记
  userManuallyEditedEnglish.value = false
}

// 中文输入框失焦时自动翻译（仅在未手动编辑过英文时）
async function handleChineseBlur() {
  // 如果是通过 Tab 键切换焦点，不触发自动填充
  if (isTabSwitching.value) {
    isTabSwitching.value = false
    return
  }
  await translateEnglish({ checkUserEdited: true })
}

// 中文输入框按键事件
async function handleChineseKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') {
    // 回车：无条件填充
    e.preventDefault()
    await translateEnglish({ checkUserEdited: false })
  } else if (e.key === 'Tab') {
    // Tab 键：标记正在切换焦点，阻止 blur 时的自动填充
    isTabSwitching.value = true
  }
}

// 执行翻译的公共函数
// options.checkUserEdited: 是否检查用户是否手动编辑过英文
async function translateEnglish(options: { checkUserEdited: boolean }) {
  const trimmedValue = editValue.value.trim()
  if (!trimmedValue) {
    // 如果中文为空，清空英文
    editValueEn.value = ''
    return
  }

  // 如果需要检查用户编辑状态，且用户已经手动编辑过英文，则不自动覆盖
  if (options.checkUserEdited && userManuallyEditedEnglish.value) {
    return
  }

  // 只对有英文字段的轨道类型进行自动翻译
  if (!getTrackConfig(editTrackType.value).hasEnglish) {
    return
  }

  const apiType = trackTypeToApiType(editTrackType.value)
  if (!apiType) {
    return
  }

  isTranslating.value = true
  try {
    const result = await geoEditorApi.translatePlaceName({
      name: trimmedValue,
      type: apiType
    })
    editValueEn.value = result.name_en
  } catch (error) {
    console.error('翻译失败:', error)
    ElMessage.warning('自动翻译失败，请手动输入英文')
  } finally {
    isTranslating.value = false
  }
}

// 英文输入框输入事件：标记用户已手动编辑
function handleEnglishInput() {
  // 一旦用户在英文框输入过任何内容，就标记为已手动编辑
  // 这个标记会持续到对话框关闭，之后所有失焦都不会再自动填充
  userManuallyEditedEnglish.value = true
}

// 对话框关闭时重置状态
function handleDialogClose() {
  userManuallyEditedEnglish.value = false
  isTranslating.value = false
}

// 保存编辑
async function handleSave() {
  const cleanedValue = editValue.value.trim()
  const cleanedValueEn = editValueEn.value.trim() || null

  if (!cleanedValue) {
    try {
      await ElMessageBox.confirm(
        '确定要清除该字段吗？',
        '确认清除',
        { type: 'warning' }
      )
    } catch {
      return
    }
  }

  emit('save', {
    trackType: editTrackType.value,
    segmentId: editSegmentId.value,
    value: cleanedValue || null,
    valueEn: cleanedValueEn
  })

  editDialogVisible.value = false
}

// 点击选择
function handleSelect(segmentId: string, e: MouseEvent) {
  const addToSelection = e.ctrlKey || e.shiftKey
  emit('select', segmentId, addToSelection)
}

// 点击轨道行空白区域取消选择（普通模式）
function handleTrackRowClick(e: MouseEvent) {
  // 只在直接点击轨道行时触发（通过段落块的事件冒泡会被阻止）
  if ((e.target as HTMLElement).classList.contains('track-row')) {
    // 普通模式：取消所有选择
    if (!isMultiSelectMode.value) {
      emit('select', null, false)
    }
  }
}

// 悬停
function handleHover(segmentId: string | null) {
  emit('hover', segmentId)
}

// 轨道配置
function getTrackConfig(trackType: TrackType) {
  return TRACK_CONFIG[trackType]
}

// 退出多选模式（供父组件调用）
function exitMultiSelectMode() {
  isMultiSelectMode.value = false
}

// 暴露方法给父组件
defineExpose({
  exitMultiSelectMode,
  exitEditMode
})

// 按轨道类型分组可见段落
const segmentsByTrack = computed(() => {
  const grouped: Record<string, typeof visibleSegments.value> = {}
  for (const item of visibleSegments.value) {
    const key = item.trackType
    if (!grouped[key]) grouped[key] = []
    grouped[key].push(item)
  }
  return grouped
})

// 监听多选模式变化，通知父组件
watch(isMultiSelectMode, (isActive) => {
  emit('multi-select-change', isActive)
})

// 监听对话框状态变化，通知父组件
watch(editDialogVisible, (isOpen) => {
  emit('dialog-open', isOpen)
})
</script>

<template>
  <div class="timeline-tracks">
    <!-- 轨道行 -->
    <div
      v-for="track in tracks"
      :key="track.type"
      class="track-row"
      :class="{ 'is-multi-select-mode': isMultiSelectMode }"
      @click="handleTrackRowClick"
    >
      <!-- 轨道标签（在padding区域内） -->
      <div class="track-label">
        {{ track.label }}
      </div>
      <!-- 段落块容器 -->
      <div class="track-content">
        <div
          v-for="item in (segmentsByTrack[track.type] || [])"
          :key="item.segment.id"
          class="segment-block"
          :class="{
            'is-selected': selectedSegmentIds.has(item.segment.id),
            'is-hovered': item.segment.id === hoveredSegmentId,
            'is-edited': item.segment.isEdited,
            'is-empty': !item.segment.value,
            'is-multi-select-mode': isMultiSelectMode,
            'is-edit-mode': isEditMode && editModeSegmentId === item.segment.id,
            'is-dragging': isDragging && dragSegmentId === item.segment.id
          }"
          :style="{
            left: `${item.visibleStart}%`,
            width: `${item.visibleWidth}%`
          }"
          @click="handleSelect(item.segment.id, $event)"
          @dblclick="handleDoubleClick(track.type, item.segment)"
          @touchstart="handleTouchStart(track.type, item.segment, $event)"
          @touchmove="handleTouchMove"
          @touchend="handleTouchEnd"
          @mouseenter="handleHover(item.segment.id)"
          @mouseleave="handleHover(null)"
          @mousedown="handleDragStart(track.type, item.segment, $event)"
        >
          <!-- 桌面端手柄（悬停时显示） -->
          <template v-if="!isMobile">
            <div class="segment-handle segment-handle-left" />
            <div class="segment-handle segment-handle-right" />
          </template>

          <!-- 段落文本 -->
          <span v-if="item.segment.value || (selectedSegmentIds.has(item.segment.id) || item.segment.id === hoveredSegmentId)" class="segment-text">
            {{ item.segment.value || '(空)' }}
          </span>
        </div>

        <!-- 拖动预览框（只在当前拖动的轨道上显示） -->
        <div
          v-if="((isDragging && dragTrackType === track.type) || (isMobileDragging && editModeSegmentId)) && previewWidth > 0"
          class="segment-preview"
          :style="{
            left: `${previewLeft}%`,
            width: `${previewWidth}%`
          }"
        />
      </div>
    </div>

    <!-- 编辑对话框 -->
    <el-dialog
      v-model="editDialogVisible"
      :title="`编辑${getTrackConfig(editTrackType).label}`"
      width="400px"
      :close-on-click-modal="false"
      @close="handleDialogClose"
    >
      <el-form label-width="80px">
        <el-form-item :label="getTrackConfig(editTrackType).label">
          <el-input
            v-model="editValue"
            :placeholder="getTrackConfig(editTrackType).placeholder"
            clearable
            @blur="handleChineseBlur"
            @keydown="handleChineseKeydown"
          />
        </el-form-item>
        <el-form-item
          v-if="getTrackConfig(editTrackType).hasEnglish"
          label="英文"
        >
          <el-input
            v-model="editValueEn"
            placeholder="如：Beijing"
            clearable
            :loading="isTranslating"
            @input="handleEnglishInput"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.timeline-tracks {
  position: relative;
  width: 100%;
  height: 100%;
  padding-left: var(--geo-editor-padding-left);
  padding-right: var(--geo-editor-padding-right);
  box-sizing: border-box;
  touch-action: none;
}

.track-row {
  position: relative;
  height: var(--geo-editor-track-row-height);
  border-bottom: 1px solid var(--el-border-color-lighter);
  user-select: none;
  -webkit-user-select: none;
}

.track-label {
  position: absolute;
  left: calc(var(--geo-editor-label-width) * -1.6); /* -32px */
  top: 0;
  width: var(--geo-editor-label-width);
  height: 100%;
  padding-right: 4px;
  text-align: right;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  display: flex;
  align-items: center;
  justify-content: flex-end;
  white-space: nowrap;
  overflow: normal;
}

.track-label::after {
  content: '';
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 1px;
  background: var(--el-border-color-lighter);
}

.track-content {
  position: relative;
  width: 100%;
  height: 100%;
}

/* 段落块基础样式 */
.segment-block {
  position: absolute;
  height: 22px;
  display: flex;
  align-items: center;
  padding: 0 3px;
  background: var(--el-color-primary-light-9);
  border: 1px solid var(--el-color-primary-light-7);
  border-radius: 3px;
  font-size: 11px;
  white-space: nowrap;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.15s;
  user-select: none;
}

.segment-block.is-hovered {
  background: var(--el-color-primary-light-7);
  border-color: var(--el-color-primary-light-5);
  z-index: 10;
}

.segment-block.is-selected {
  background: var(--el-color-primary);
  border-color: var(--el-color-primary-dark-2);
}

/* 选中角标 */
.segment-block.is-selected::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: white;
  opacity: 0.8;
}

.segment-block.is-edited {
  background: var(--el-color-warning-light-9);
  border-color: var(--el-color-warning-light-7);
}

.segment-block.is-edited.is-selected {
  background: var(--el-color-warning);
  border-color: var(--el-color-warning-dark-2);
}

.segment-block.is-empty {
  /* 空块默认显示虚线边框 */
  background: transparent;
  border-color: var(--el-border-color);
  border-style: dashed;
  opacity: 0.6;
}

/* 选中、悬停或编辑模式时强调空块 */
.segment-block.is-empty.is-selected,
.segment-block.is-empty.is-hovered,
.segment-block.is-empty.is-edit-mode {
  opacity: 1;
  background: var(--el-fill-color-light);
  border-color: var(--el-color-primary);
  border-width: 2px;
}

.segment-text {
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

/* 多选模式样式 */
.track-row.is-multi-select-mode {
  background-color: var(--el-fill-color-lighter);
}

.segment-block.is-multi-select-mode {
  border-style: dashed;
  border-width: 2px;
  animation: pulse 1.5s ease-in-out infinite;
}

.segment-block.is-multi-select-mode.is-selected {
  border-style: solid;
  animation: none;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

/* 手柄样式 */
.segment-handle {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 6px;
  background: var(--el-color-primary);
  opacity: 0;
  transition: opacity 0.2s;
  cursor: col-resize;
  z-index: 5;
}

.segment-handle-left {
  left: 0;
}

.segment-handle-right {
  right: 0;
}

.segment-block:hover .segment-handle {
  opacity: 0.5;
}

.segment-handle:hover {
  opacity: 1 !important;
}

/* 拖动预览框 */
.segment-preview {
  position: absolute;
  height: 22px;
  border: 2px dashed var(--el-color-primary);
  background: rgba(64, 158, 255, 0.1);
  pointer-events: none;
  z-index: 100;
  border-radius: 3px;
}

/* 拖动中样式 */
.segment-block.is-dragging {
  opacity: 0.5;
}

/* 移动端编辑模式 */
.segment-block.is-edit-mode {
  border-width: 2px;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.3);
  animation: edit-pulse 1.5s ease-in-out infinite;
}

@keyframes edit-pulse {
  0%, 100% {
    box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.3);
  }
  50% {
    box-shadow: 0 0 0 4px rgba(64, 158, 255, 0.5);
  }
}

/* 移动端隐藏手柄 */
@media (max-width: 1366px) {
  .segment-handle {
    display: none;
  }
}
</style>
