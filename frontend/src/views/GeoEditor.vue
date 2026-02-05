<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, HomeFilled, RefreshLeft, RefreshRight, Check, ZoomIn, ZoomOut, Refresh, User, ArrowDown, Setting, SwitchButton, Delete, Close, Connection, Histogram, Clock } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useGeoEditorStore, type TrackType } from '@/stores/geoEditor'
import { useAuthStore } from '@/stores/auth'
import UniversalMap from '@/components/map/UniversalMap.vue'
import GeoChartPanel from '@/components/geo-editor/GeoChartPanel.vue'
import TimelineScale from '@/components/geo-editor/TimelineScale.vue'
import TimelineTracks from '@/components/geo-editor/TimelineTracks.vue'

const route = useRoute()
const router = useRouter()
const geoEditorStore = useGeoEditorStore()
const authStore = useAuthStore()

const trackId = ref<number>(parseInt(route.params.id as string))
const isLoading = ref(true)
const isSaving = ref(false)

// 页面标题
const trackTitle = computed(() => `编辑：${geoEditorStore.trackName || '轨迹 #' + trackId.value}`)

// 移动端检测
const isMobile = computed(() => window.innerWidth <= 1366)

// 时间轴内容区引用（用于尺寸计算）
const timelineContentRef = ref<HTMLElement | null>(null)

// TimelineTracks 组件引用（用于退出多选模式）
const timelineTracksRef = ref<{ exitMultiSelectMode?: () => void } | null>(null)

// 地图区域引用（用于滚轮缩放检测）
const mapSectionRef = ref<HTMLElement | null>(null)

// 高亮区域（支持多段）
const highlightedSegments = computed(() => {
  const segments: Array<{ start: number; end: number }> = []

  // 添加悬停的段落
  if (geoEditorStore.hoveredSegmentId) {
    for (const track of geoEditorStore.tracks) {
      const segment = track.segments.find(s => s.id === geoEditorStore.hoveredSegmentId)
      if (segment) {
        segments.push({ start: segment.startIndex, end: segment.endIndex })
        break
      }
    }
  }

  // 添加选中的段落
  for (const track of geoEditorStore.tracks) {
    for (const segment of track.segments) {
      if (geoEditorStore.selectedSegmentIds.has(segment.id)) {
        segments.push({ start: segment.startIndex, end: segment.endIndex })
      }
    }
  }

  return segments.length > 0 ? segments : null
})

// 高亮区域（单个范围，用于图表组件）
const highlightedSegment = computed(() => {
  const segments = highlightedSegments.value
  if (!segments || segments.length === 0) return null

  // 返回合并后的范围
  const minStart = Math.min(...segments.map(s => s.start))
  const maxEnd = Math.max(...segments.map(s => s.end))

  return { start: minStart, end: maxEnd }
})

// 转换点数据为 UniversalMap 格式（tracks 数组）
const mapTracks = computed(() => {
  return [
    {
      id: trackId.value,
      points: geoEditorStore.points.map(p => ({
        latitude: p.latitude,        // WGS84
        longitude: p.longitude,       // WGS84
        latitude_wgs84: p.latitude,   // WGS84
        longitude_wgs84: p.longitude, // WGS84
        latitude_gcj02: p.latitude_gcj02,
        longitude_gcj02: p.longitude_gcj02,
        latitude_bd09: p.latitude_bd09,
        longitude_bd09: p.longitude_bd09,
        elevation: p.elevation,
        time: p.time,
        speed: p.speed,
      })),
    },
  ]
})

// 轨道数据（用于时间轴显示）
const tracksData = computed(() => geoEditorStore.tracks)

// 滚动条相关
const scrollbarTrackRef = ref<HTMLElement>()
const isDraggingScrollbar = ref(false)

// 滚动条滑块样式
const scrollbarThumbStyle = computed(() => {
  const range = geoEditorStore.zoomEnd - geoEditorStore.zoomStart
  const left = geoEditorStore.zoomStart * 100
  const width = range * 100
  return {
    left: `${left}%`,
    width: `${width}%`,
  }
})

// 滚动条点击处理
function handleScrollbarClick(e: MouseEvent) {
  if (!scrollbarTrackRef.value) return
  const rect = scrollbarTrackRef.value.getBoundingClientRect()
  const x = e.clientX - rect.left
  const position = x / rect.width

  // 将点击位置作为新的中心，移动缩放窗口
  const range = geoEditorStore.zoomEnd - geoEditorStore.zoomStart
  const newStart = Math.max(0, Math.min(1 - range, position - range / 2))
  const newEnd = newStart + range
  geoEditorStore.setZoom(newStart, newEnd)
}

// 滚动条拖动开始
function handleScrollbarDragStart(e: MouseEvent) {
  e.preventDefault()
  e.stopPropagation()
  isDraggingScrollbar.value = true

  const startX = e.clientX
  const startRange = geoEditorStore.zoomEnd - geoEditorStore.zoomStart
  const startZoomStart = geoEditorStore.zoomStart

  const handleMouseMove = (e: MouseEvent) => {
    if (!isDraggingScrollbar.value) return
    if (!scrollbarTrackRef.value) return

    const rect = scrollbarTrackRef.value.getBoundingClientRect()
    const deltaX = e.clientX - startX
    const deltaRatio = deltaX / rect.width

    // 计算新的缩放位置
    let newStart = startZoomStart + deltaRatio
    newStart = Math.max(0, Math.min(1 - startRange, newStart))
    const newEnd = newStart + startRange

    geoEditorStore.setZoom(newStart, newEnd)
  }

  const handleMouseUp = () => {
    isDraggingScrollbar.value = false
    window.removeEventListener('mousemove', handleMouseMove)
    window.removeEventListener('mouseup', handleMouseUp)
  }

  window.addEventListener('mousemove', handleMouseMove)
  window.addEventListener('mouseup', handleMouseUp)
}

// 计算指针对应的点索引（用于地图 tooltip 同步）
// 优先使用悬浮索引（刻度悬浮或地图悬浮），否则使用指针位置
const highlightPointIndex = computed(() => {
  if (geoEditorStore.points.length === 0) return undefined

  // 优先使用悬浮索引
  if (scaleHighlightIndex.value !== null) {
    return Math.max(0, Math.min(geoEditorStore.points.length - 1, scaleHighlightIndex.value))
  }

  // pointerPosition 现在是点索引位置（0-1），直接计算对应的点索引
  const pointIndex = Math.round(geoEditorStore.pointerPosition * (geoEditorStore.points.length - 1))
  return Math.max(0, Math.min(geoEditorStore.points.length - 1, pointIndex))
})

// 计算指针在可见区域的位置
const isPointerVisible = computed(() => {
  return geoEditorStore.pointerPosition >= geoEditorStore.zoomStart &&
         geoEditorStore.pointerPosition <= geoEditorStore.zoomEnd
})

const playheadXPosition = computed(() => {
  // 拖动时优先使用像素位置（避免跳变）
  if (dragPixelPosition.value) {
    return dragPixelPosition.value
  }

  if (geoEditorStore.points.length === 0) return '0%'

  // 使用实际的指针位置（而非悬浮索引）
  const pointerPos = geoEditorStore.pointerPosition

  // 计算在可见区域内的相对位置
  const percent = (pointerPos - geoEditorStore.zoomStart) /
                  (geoEditorStore.zoomEnd - geoEditorStore.zoomStart)

  // 将位置钳制在 0-1 范围内
  const clampedPercent = Math.max(0, Math.min(1, percent))

  // 使用缓存的容器宽度计算正确的百分比位置
  const contentWidthPx = timelineContentWidth.value - contentAreaLeftOffset.value - 50
  const leftPx = contentAreaLeftOffset.value + clampedPercent * contentWidthPx + 1

  // 转换为百分比
  const leftPercent = timelineContentWidth.value > 0
    ? (leftPx / timelineContentWidth.value) * 100
    : 75 // fallback

  return `${leftPercent}%`
})

// 指针时间文本
const pointerTimeText = computed(() => {
  if (geoEditorStore.points.length === 0) return '--'

  // 使用实际指针对应的点的时间（而非悬浮索引）
  const pointIndex = Math.round(geoEditorStore.pointerPosition * (geoEditorStore.points.length - 1))
  if (pointIndex < 0 || pointIndex >= geoEditorStore.points.length) {
    return '--'
  }

  const point = geoEditorStore.points[pointIndex]

  // 根据刻度单位显示不同格式
  if (geoEditorStore.timeScaleUnit === 'index') {
    // 索引模式：显示点索引
    return String(pointIndex)
  }

  if (!point?.time) return '--'

  if (geoEditorStore.timeScaleUnit === 'duration') {
    // 时长模式：显示从起点开始的时长 HH:MM:SS
    const startTime = geoEditorStore.points[0]?.time
      ? new Date(geoEditorStore.points[0].time).getTime()
      : 0
    const pointTime = new Date(point.time).getTime()
    const elapsedMs = pointTime - startTime
    const totalSeconds = Math.floor(elapsedMs / 1000)
    const hours = Math.floor(totalSeconds / 3600)
    const minutes = Math.floor((totalSeconds % 3600) / 60)
    const seconds = totalSeconds % 60
    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
  }

  // 时间模式：显示时间 HH:MM:SS
  const date = new Date(point.time)
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')
  return `${hours}:${minutes}:${seconds}`
})

// 拖动指针
const isDraggingPlayhead = ref(false)
const autoPanTimer = ref<number | null>(null)
// 拖动时的像素位置（null 表示未拖动）
const dragPixelPosition = ref<string | null>(null)
// 缓存的容器宽度（用于百分比计算）
const timelineContentWidth = ref(0)
// 缓存的内容区域左边距（像素）
const contentAreaLeftOffset = ref(0)

// 更新缓存的尺寸
function updateCachedDimensions() {
  nextTick(() => {
    if (!timelineContentRef.value) return

    const contentArea = timelineContentRef.value.querySelector('.scale-content-area') as HTMLElement
    if (!contentArea) return

    const timelineRect = timelineContentRef.value.getBoundingClientRect()
    const contentRect = contentArea.getBoundingClientRect()

    timelineContentWidth.value = timelineRect.width
    contentAreaLeftOffset.value = contentRect.left - timelineRect.left
  })
}

// 监听缩放变化，更新缓存的尺寸
watch(() => [geoEditorStore.zoomStart, geoEditorStore.zoomEnd], () => {
  if (!isDraggingPlayhead.value) {
    updateCachedDimensions()
  }
}, { deep: true })

// 监听轨迹名称变化（调试）
watch(() => geoEditorStore.trackName, (newName) => {
  console.log('[GeoEditor] trackName changed:', newName)
  console.log('[GeoEditor] trackTitle:', trackTitle.value)
}, { immediate: true })

function handlePlayheadMouseDown(e: MouseEvent) {
  e.preventDefault()
  isDraggingPlayhead.value = true
  geoEditorStore.startPointerDrag()

  // 清除悬浮高亮（拖动指针时优先显示指针）
  scaleHighlightIndex.value = null

  // 确保尺寸已缓存
  updateCachedDimensions()

  // 在 mousedown 时获取 timeline-content 和内容区域引用
  const timelineContent = (e.currentTarget as HTMLElement).closest('.timeline-content') as HTMLElement
  if (!timelineContent) return

  // 获取实际内容区域（子组件中有 padding 的区域）
  const contentArea = timelineContent.querySelector('.scale-content-area') as HTMLElement
  if (!contentArea) {
    console.warn('[GeoEditor] 无法找到内容区域 .scale-content-area')
    return
  }

  // 拖动时的点索引（用于直接显示）
  const draggedPointIndex = ref<number>(0)

  const handleMouseMove = (e: MouseEvent) => {
    if (!isDraggingPlayhead.value) return

    // 直接使用内容区域的 rect，无需额外的 padding 计算
    const rect = contentArea.getBoundingClientRect()
    const timelineRect = timelineContent.getBoundingClientRect()

    // 内容区域实际宽度
    const contentWidth = rect.width

    // 内容区域相对于 timeline-content 的左边距
    const contentLeft = rect.left - timelineRect.left

    // 鼠标位置相对于内容区域的 x 坐标
    let x = e.clientX - rect.left

    // 自动平移：当鼠标接近边缘时，自动移动缩放窗口
    const EDGE_THRESHOLD = 30  // 边缘阈值（像素）

    if (x < EDGE_THRESHOLD) {
      // 接近左边缘，向左平移
      startAutoPan('left')
    } else if (x > contentWidth - EDGE_THRESHOLD) {
      // 接近右边缘，向右平移
      startAutoPan('right')
    } else {
      // 停止自动平移
      stopAutoPan()
    }

    // 限制 x 在内容区域内
    x = Math.max(0, Math.min(contentWidth, x))

    // 计算在缩放窗口中的相对位置 (0-1)
    const positionInZoomWindow = x / contentWidth

    // 转换为全局点索引位置 (0-1)
    const globalPosition = geoEditorStore.zoomStart + positionInZoomWindow * (geoEditorStore.zoomEnd - geoEditorStore.zoomStart)

    // 计算对应的点索引
    const pointIndex = Math.round(globalPosition * geoEditorStore.points.length)
    draggedPointIndex.value = Math.max(0, Math.min(geoEditorStore.points.length - 1, pointIndex))

    // 更新拖动像素位置（由计算属性使用）
    const newLeft = contentLeft + x + 1
    dragPixelPosition.value = `${newLeft}px`

    // 更新 store（使用点索引位置）
    geoEditorStore.setPointerPosition(draggedPointIndex.value / geoEditorStore.points.length)
  }

  const handleMouseUp = () => {
    isDraggingPlayhead.value = false
    stopAutoPan()
    geoEditorStore.stopPointerDrag()
    // 清除拖动位置，恢复使用计算属性的百分比位置
    dragPixelPosition.value = null
    window.removeEventListener('mousemove', handleMouseMove)
    window.removeEventListener('mouseup', handleMouseUp)
  }

  window.addEventListener('mousemove', handleMouseMove)
  window.addEventListener('mouseup', handleMouseUp)
}

// 移动端：触摸拖动指针
function handlePlayheadTouchStart(e: Event) {
  const touchEvent = e as TouchEvent
  if (touchEvent.touches.length !== 1) return  // 只处理单指触摸

  e.preventDefault()
  isDraggingPlayhead.value = true
  geoEditorStore.startPointerDrag()

  // 清除悬浮高亮（拖动指针时优先显示指针）
  scaleHighlightIndex.value = null

  // 确保尺寸已缓存
  updateCachedDimensions()

  // 在 touchstart 时获取 timeline-content 和内容区域引用
  const target = e.currentTarget as HTMLElement
  const timelineContent = target.closest('.timeline-content') as HTMLElement
  if (!timelineContent) return

  // 获取实际内容区域
  const contentArea = timelineContent.querySelector('.scale-content-area') as HTMLElement
  if (!contentArea) {
    console.warn('[GeoEditor] 无法找到内容区域 .scale-content-area')
    return
  }

  // 拖动时的点索引（用于直接显示）
  const draggedPointIndex = ref<number>(0)

  const handleTouchMove = (e: Event) => {
    const te = e as TouchEvent
    if (!isDraggingPlayhead.value || te.touches.length !== 1) return

    e.preventDefault()

    const rect = contentArea.getBoundingClientRect()
    const timelineRect = timelineContent.getBoundingClientRect()
    const contentWidth = rect.width
    const contentLeft = rect.left - timelineRect.left

    // 触摸位置相对于内容区域的 x 坐标
    let x = te.touches[0].clientX - rect.left

    // 自动平移
    const EDGE_THRESHOLD = 30
    if (x < EDGE_THRESHOLD) {
      startAutoPan('left')
    } else if (x > contentWidth - EDGE_THRESHOLD) {
      startAutoPan('right')
    } else {
      stopAutoPan()
    }

    x = Math.max(0, Math.min(contentWidth, x))

    const positionInZoomWindow = x / contentWidth

    // 转换为全局点索引位置 (0-1)
    const globalPosition = geoEditorStore.zoomStart + positionInZoomWindow * (geoEditorStore.zoomEnd - geoEditorStore.zoomStart)

    // 计算对应的点索引
    const pointIndex = Math.round(globalPosition * geoEditorStore.points.length)
    draggedPointIndex.value = Math.max(0, Math.min(geoEditorStore.points.length - 1, pointIndex))

    const newLeft = contentLeft + x + 1
    dragPixelPosition.value = `${newLeft}px`

    // 更新 store（使用点索引位置）
    geoEditorStore.setPointerPosition(draggedPointIndex.value / geoEditorStore.points.length)
  }

  const handleTouchEnd = () => {
    isDraggingPlayhead.value = false
    stopAutoPan()
    geoEditorStore.stopPointerDrag()
    dragPixelPosition.value = null
    window.removeEventListener('touchmove', handleTouchMove, { passive: false } as any)
    window.removeEventListener('touchend', handleTouchEnd)
    window.removeEventListener('touchcancel', handleTouchCancel as any)
  }

  const handleTouchCancel = () => {
    isDraggingPlayhead.value = false
    stopAutoPan()
    geoEditorStore.stopPointerDrag()
    dragPixelPosition.value = null
    window.removeEventListener('touchmove', handleTouchMove, { passive: false } as any)
    window.removeEventListener('touchend', handleTouchEnd)
    window.removeEventListener('touchcancel', handleTouchCancel as any)
  }

  window.addEventListener('touchmove', handleTouchMove, { passive: false } as any)
  window.addEventListener('touchend', handleTouchEnd)
  window.addEventListener('touchcancel', handleTouchCancel as any)
}

// 自动平移时间轴
function startAutoPan(direction: 'left' | 'right') {
  if (autoPanTimer.value) return

  const panSpeed = 0.002  // 每次平移的距离（相对于缩放范围）

  autoPanTimer.value = window.setInterval(() => {
    const range = geoEditorStore.zoomEnd - geoEditorStore.zoomStart

    if (direction === 'left') {
      // 向左平移
      const newStart = Math.max(0, geoEditorStore.zoomStart - panSpeed)
      const newEnd = newStart + range
      geoEditorStore.setZoom(newStart, newEnd)

      // 如果到达左边界，停止平移
      if (newStart === 0) {
        stopAutoPan()
      }
    } else {
      // 向右平移
      const newEnd = Math.min(1, geoEditorStore.zoomEnd + panSpeed)
      const newStart = newEnd - range
      geoEditorStore.setZoom(newStart, newEnd)

      // 如果到达右边界，停止平移
      if (newEnd === 1) {
        stopAutoPan()
      }
    }
  }, 16)  // 约 60fps
}

function stopAutoPan() {
  if (autoPanTimer.value) {
    clearInterval(autoPanTimer.value)
    autoPanTimer.value = null
  }
}

// 双指缩放相关
const pinchZoomState = ref({
  isPinching: false,
  initialDistance: 0,
  initialRange: 0,      // zoomEnd - zoomStart
  initialCenter: 0,     // 缩放中心点位置 (0-1)
  centerX: 0,            // 双指中心的 x 坐标
})

// 时间轴容器引用（用于 touch 事件）
const timelineContainerRef = ref<HTMLElement>()

// 处理双指缩放的 touchstart
function handleTouchStart(e: Event) {
  const touchEvent = e as TouchEvent
  if (touchEvent.touches.length === 2) {
    // 双指触摸，开始缩放
    e.preventDefault()

    const touch1 = touchEvent.touches[0]
    const touch2 = touchEvent.touches[1]

    // 计算双指距离
    const distance = Math.hypot(
      touch2.clientX - touch1.clientX,
      touch2.clientY - touch1.clientY
    )

    // 计算双指中心点（屏幕坐标）
    const centerScreenX = (touch1.clientX + touch2.clientX) / 2

    // 获取内容区域（用于计算相对位置）
    const contentArea = timelineContentRef.value?.querySelector('.scale-content-area') as HTMLElement
    let centerRatio = 0.5  // 默认中心

    if (contentArea) {
      const contentRect = contentArea.getBoundingClientRect()
      const x = centerScreenX - contentRect.left
      const contentWidth = contentRect.width
      centerRatio = Math.max(0, Math.min(1, x / contentWidth))
    }

    pinchZoomState.value = {
      isPinching: true,
      initialDistance: distance,
      initialRange: geoEditorStore.zoomEnd - geoEditorStore.zoomStart,
      initialCenter: geoEditorStore.zoomStart + centerRatio * (geoEditorStore.zoomEnd - geoEditorStore.zoomStart),
      centerX: centerRatio,
    }
  }
}

// 处理双指缩放的 touchmove
function handleTouchMove(e: Event) {
  const touchEvent = e as TouchEvent
  if (!pinchZoomState.value.isPinching || touchEvent.touches.length !== 2) return

  e.preventDefault()

  const touch1 = touchEvent.touches[0]
  const touch2 = touchEvent.touches[1]

  // 计算当前双指距离
  const currentDistance = Math.hypot(
    touch2.clientX - touch1.clientX,
    touch2.clientY - touch1.clientY
  )

  // 计算缩放比例
  const scaleRatio = currentDistance / pinchZoomState.value.initialDistance

  // 限制缩放范围（避免过度缩放）
  if (scaleRatio < 0.5 || scaleRatio > 3) return

  const newRange = pinchZoomState.value.initialRange / scaleRatio

  // 确保缩放范围在有效区间
  if (newRange < 0.01 || newRange > 1) return

  // 以初始中心点为基准进行缩放
  let newCenter = pinchZoomState.value.initialCenter
  let newStart = newCenter - newRange * pinchZoomState.value.centerX
  let newEnd = newCenter + newRange * (1 - pinchZoomState.value.centerX)

  // 确保边界
  if (newStart < 0) {
    newStart = 0
    newEnd = Math.min(1, newRange)
  } else if (newEnd > 1) {
    newEnd = 1
    newStart = Math.max(0, 1 - newRange)
  }

  geoEditorStore.setZoom(newStart, newEnd)
}

// 处理双指缩放的 touchend
function handleTouchEnd(e: Event) {
  const touchEvent = e as TouchEvent
  if (touchEvent.touches.length < 2) {
    pinchZoomState.value.isPinching = false
  }
}

// 处理双指缩放的 touchcancel（Safari 兼容）
function handleTouchCancel() {
  pinchZoomState.value.isPinching = false
}

// 加载数据
onMounted(async () => {
  try {
    await geoEditorStore.loadEditorData(trackId.value)
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '加载编辑器数据失败')
    router.back()
  } finally {
    isLoading.value = false
  }

  // 更新缓存的尺寸
  updateCachedDimensions()

  // 添加离页提示
  window.addEventListener('beforeunload', handleBeforeUnload)
  // 添加滚轮缩放监听
  window.addEventListener('wheel', handleWheel, { passive: false })
  // 添加全局键盘事件
  window.addEventListener('keydown', handleGlobalKeydown)

  // 等待 DOM 更新后添加移动端双指缩放监听
  nextTick(() => {
    const container = timelineContainerRef.value
    if (container) {
      container.addEventListener('touchstart', handleTouchStart, { passive: false })
      container.addEventListener('touchmove', handleTouchMove, { passive: false })
      container.addEventListener('touchend', handleTouchEnd, { passive: false })
      container.addEventListener('touchcancel', handleTouchCancel, { passive: false })
    }
  })
})

onUnmounted(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
  window.removeEventListener('wheel', handleWheel)
  window.removeEventListener('keydown', handleGlobalKeydown)

  // 移除移动端双指缩放监听
  const container = timelineContainerRef.value
  if (container) {
    container.removeEventListener('touchstart', handleTouchStart)
    container.removeEventListener('touchmove', handleTouchMove)
    container.removeEventListener('touchend', handleTouchEnd)
    container.removeEventListener('touchcancel', handleTouchCancel)
  }
})

// 离页提示
function handleBeforeUnload(e: BeforeUnloadEvent) {
  if (geoEditorStore.hasUnsavedChanges) {
    e.preventDefault()
  }
}

// 滚轮缩放（需要按 Ctrl 或 Alt）
function handleWheel(e: WheelEvent) {
  if (e.ctrlKey || e.altKey) {
    // 检查鼠标是否在地图区域内，如果是则不处理缩放
    if (mapSectionRef.value && mapSectionRef.value.contains(e.target as Node)) {
      return
    }

    e.preventDefault()

    // 确定缩放中心位置，默认使用指针位置
    let zoomCenter = geoEditorStore.pointerPosition

    // 检查鼠标是否在时间轴容器内
    if (timelineContainerRef.value && timelineContainerRef.value.contains(e.target as Node)) {
      // 检查鼠标是否在控制栏上
      const controlsBar = timelineContainerRef.value.querySelector('.controls-bar') as HTMLElement
      if (controlsBar && controlsBar.contains(e.target as Node)) {
        // 控制栏使用指针位置（已在默认值中设置）
      } else {
        // 鼠标在时间轴容器内但不在控制栏上，计算鼠标位置
        // 获取刻度内容区域作为参考（所有内容区域共享相同的横向坐标系统）
        const scaleContentArea = timelineContainerRef.value.querySelector('.scale-content-area') as HTMLElement
        if (scaleContentArea) {
          const rect = scaleContentArea.getBoundingClientRect()
          // 计算鼠标在内容区域内的相对位置 (0-1)
          const x = e.clientX - rect.left
          const contentWidth = rect.width

          if (x >= 0 && x <= contentWidth) {
            // 转换为全局位置 (0-1)
            const positionInZoomWindow = x / contentWidth
            zoomCenter = geoEditorStore.zoomStart + positionInZoomWindow * (geoEditorStore.zoomEnd - geoEditorStore.zoomStart)
          }
        }
      }
    }

    // 使用缩放因子 1.25 进行缩放
    const factor = e.deltaY < 0 ? 1.25 : 0.8 // deltaY < 0 是放大
    geoEditorStore.zoomAround(zoomCenter, factor)
  }
}

// 返回
function handleBack() {
  if (geoEditorStore.hasUnsavedChanges) {
    ElMessageBox.confirm(
      '有未保存的更改，要保存吗？',
      '提示',
      {
        distinguishCancelAndClose: true,
        confirmButtonText: '保存',
        cancelButtonText: '放弃',
      }
    )
      .then(() => handleSave())
      .then(() => router.back())
      .catch((action) => {
        if (action === 'cancel') {
          router.back()
        }
      })
  } else {
    router.back()
  }
}

// 返回主页
function goHome() {
  if (geoEditorStore.hasUnsavedChanges) {
    ElMessageBox.confirm(
      '有未保存的更改，要保存吗？',
      '提示',
      {
        distinguishCancelAndClose: true,
        confirmButtonText: '保存',
        cancelButtonText: '放弃',
      }
    )
      .then(() => handleSave())
      .then(() => router.push('/home'))
      .catch((action) => {
        if (action === 'cancel') {
          router.push('/home')
        }
      })
  } else {
    router.push('/home')
  }
}

// 撤销
function handleUndo() {
  geoEditorStore.undo()
}

// 重做
function handleRedo() {
  geoEditorStore.redo()
}

// 下拉菜单命令处理
function handleCommand(command: string) {
  switch (command) {
    case 'undo':
      handleUndo()
      break
    case 'redo':
      handleRedo()
      break
    case 'admin':
      router.push('/admin')
      break
    case 'logout':
      authStore.logout()
      router.push('/login')
      break
  }
}

// 保存
async function handleSave() {
  isSaving.value = true
  try {
    await geoEditorStore.saveToServer()
    ElMessage.success('保存成功')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally {
    isSaving.value = false
  }
}

// 缩放控制
function handleZoomIn() {
  // 以指针位置为中心放大
  geoEditorStore.zoomAround(geoEditorStore.pointerPosition, 1.25)
}

function handleZoomOut() {
  // 以指针位置为中心缩小
  geoEditorStore.zoomAround(geoEditorStore.pointerPosition, 0.8)
}

function handleResetZoom() {
  geoEditorStore.resetZoom()
}

// 缩放倍数显示
const zoomLevelText = computed(() => {
  const range = geoEditorStore.zoomEnd - geoEditorStore.zoomStart
  const level = Math.round(1 / range)
  if (level >= 1000) {
    return `${(level / 1000).toFixed(1)}kx`
  }
  return `${level}x`
})

function handleSegmentHover(segmentId: string | null) {
  geoEditorStore.hoverSegment(segmentId)
}

// 处理轨道块选择（支持多选）
function handleSegmentSelect(segmentId: string | null, addToSelection: boolean) {
  if (segmentId === null) {
    geoEditorStore.clearSelection()
  } else {
    geoEditorStore.selectSegment(segmentId, addToSelection)
  }
}

// 批量清空选中的段落
async function handleBatchClear() {
  const count = geoEditorStore.selectedCount
  if (count === 0) return

  geoEditorStore.clearSelectedSegments()
  ElMessage.success(`已清空 ${count} 个段落`)
}

// 批量合并选中的段落
async function handleBatchMerge() {
  if (!geoEditorStore.canMergeSelected()) {
    ElMessage.warning('请选择连续的段落进行合并')
    return
  }

  geoEditorStore.mergeSelectedSegments()
  ElMessage.success('合并完成')
}

// 退出多选模式
function handleExitMultiSelect() {
  timelineTracksRef.value?.exitMultiSelectMode?.()
}

// 全局键盘事件
function handleGlobalKeydown(e: KeyboardEvent) {
  // Esc 退出多选或取消选择
  if (e.key === 'Escape') {
    if (isMultiSelectMode.value) {
      e.preventDefault()
      handleExitMultiSelect()
    } else if (geoEditorStore.selectedCount > 0) {
      e.preventDefault()
      geoEditorStore.clearSelection()
    }
  }
  // Delete 快捷键清空
  if (e.key === 'Delete' && geoEditorStore.selectedCount > 0) {
    e.preventDefault()
    handleBatchClear()
  }
}

// 时间轴段落保存
function handleSegmentSave(data: { trackType: TrackType; segmentId: string; value: string; valueEn: string | null }) {
  geoEditorStore.updateSegmentValue(data.trackType, data.segmentId, data.value, data.valueEn)
}

// 图表高亮
function handleChartHighlight(dataIndex: number) {
  for (const track of geoEditorStore.tracks) {
    for (const segment of track.segments) {
      if (dataIndex >= segment.startIndex && dataIndex <= segment.endIndex) {
        geoEditorStore.selectSegment(segment.id, false)
        // 不移动指针，只用于选择段落
        return
      }
    }
  }
}

// 指针位置变化
function handlePointerChange(position: number) {
  geoEditorStore.setPointerPosition(position)
}

// 刻度悬浮处理（同步到地图，不移动指针）
const scaleHighlightIndex = ref<number | null>(null)

// 多选模式状态（来自 TimelineTracks）
const isMultiSelectMode = ref(false)

function handleMultiSelectChange(isActive: boolean) {
  isMultiSelectMode.value = isActive
}

function handleScaleHover(pointIndex: number | null) {
  // 拖动指针时不响应悬浮，避免闪烁
  if (isDraggingPlayhead.value) return
  scaleHighlightIndex.value = pointIndex
}

// 刻度区域触摸滑动平移时间轴
function handleScalePan(deltaX: number) {
  const currentRange = geoEditorStore.zoomEnd - geoEditorStore.zoomStart
  // 滑动距离转换为范围变化（基于内容宽度）
  const contentWidth = timelineContentRef.value?.clientWidth || 800
  const deltaRange = (deltaX / contentWidth) * currentRange

  // 计算新的起止点
  let newStart = geoEditorStore.zoomStart - deltaRange
  let newEnd = geoEditorStore.zoomEnd - deltaRange

  // 边界处理
  if (newStart < 0) {
    newStart = 0
    newEnd = currentRange
  } else if (newEnd > 1) {
    newEnd = 1
    newStart = 1 - currentRange
  }

  geoEditorStore.setZoom(newStart, newEnd)
}

// 地图悬浮处理（同步到刻度，不移动指针）
function handleMapPointHover(_point: any, pointIndex: number) {
  // 拖动指针时不响应悬浮，避免闪烁
  if (isDraggingPlayhead.value) return
  // pointIndex 为 -1 时表示清除悬浮
  scaleHighlightIndex.value = pointIndex >= 0 ? pointIndex : null
}
</script>

<template>
  <div class="geo-editor-container">
    <!-- Header -->
    <el-header>
      <div class="header-left">
        <el-button @click="handleBack" :icon="ArrowLeft" class="nav-btn" />
        <el-button @click="goHome" :icon="HomeFilled" class="nav-btn home-nav-btn" />
        <h1>{{ trackTitle }}</h1>
      </div>
      <div class="header-right">
        <div class="header-actions">
          <el-button
            :icon="RefreshLeft"
            :disabled="!geoEditorStore.canUndo"
            @click="handleUndo"
            class="nav-btn desktop-only"
          >
          </el-button>
          <el-button
            :icon="RefreshRight"
            :disabled="!geoEditorStore.canRedo"
            @click="handleRedo"
            class="nav-btn desktop-only"
          >
          </el-button>
          <el-button
            type="primary"
            :icon="Check"
            :loading="isSaving"
            :disabled="!geoEditorStore.hasUnsavedChanges"
            @click="handleSave"
            class="nav-btn"
          >
            保存
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
              <el-dropdown-item command="undo" v-if="isMobile">
                <el-icon><RefreshLeft /></el-icon>
                撤销
              </el-dropdown-item>
              <el-dropdown-item command="redo" v-if="isMobile">
                <el-icon><RefreshRight /></el-icon>
                重做
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
    <el-main class="geo-editor-main">
      <el-empty v-if="isLoading" description="加载中..." />
      <div v-else-if="geoEditorStore.points.length === 0" class="empty-state">
        <el-empty description="暂无轨迹数据" />
      </div>
      <div v-else class="editor-content">
        <!-- 地图区域 -->
        <div ref="mapSectionRef" class="map-section">
          <UniversalMap
            :tracks="mapTracks"
            :highlight-segments="highlightedSegments"
            :highlight-point-index="highlightPointIndex"
            mode="detail"
            @point-hover="handleMapPointHover"
          />
        </div>

        <!-- 图表和时间轴区域 -->
        <div ref="timelineContainerRef" class="timeline-container">
          <!-- 控制栏（始终显示，方便展开内容） -->
          <div class="controls-bar">
            <div class="controls-left">
              <el-button-group>
                <el-tooltip content="放大 (Ctrl+滚轮)" placement="top">
                  <el-button :icon="ZoomIn" @click="handleZoomIn" class="icon-button" />
                </el-tooltip>
                <el-tooltip content="缩小 (Ctrl+滚轮)" placement="top">
                  <el-button :icon="ZoomOut" @click="handleZoomOut" class="icon-button" />
                </el-tooltip>
                <el-tooltip content="重置" placement="top">
                  <el-button :icon="Refresh" @click="handleResetZoom" class="icon-button" />
                </el-tooltip>
              </el-button-group>
            </div>
            <div class="controls-center">
              <!-- 选中数量和批量操作 -->
              <transition name="el-fade-in">
                <div v-if="geoEditorStore.selectedCount > 0" class="selection-controls">
                  <span class="selection-count-badge">{{ geoEditorStore.selectedCount }}</span>
                  <el-button-group size="small">
                    <el-tooltip content="清空选中 (Delete)" placement="top">
                      <el-button :icon="Delete" @click="handleBatchClear" class="icon-button" />
                    </el-tooltip>
                    <el-tooltip content="合并选中" placement="top">
                      <el-button
                        :icon="Connection"
                        @click="handleBatchMerge"
                        :disabled="!geoEditorStore.canMergeSelected()"
                        class="icon-button"
                      />
                    </el-tooltip>
                    <el-tooltip v-if="isMultiSelectMode" content="退出多选" placement="top">
                      <el-button :icon="Close" @click="handleExitMultiSelect" type="warning" class="icon-button" />
                    </el-tooltip>
                  </el-button-group>
                </div>
              </transition>
            </div>
            <div class="controls-right">
              <el-button-group>
                <el-tooltip content="图表" placement="top">
                  <el-button
                    :type="geoEditorStore.isChartExpanded ? 'primary' : ''"
                    :icon="Histogram"
                    @click="geoEditorStore.isChartExpanded = !geoEditorStore.isChartExpanded"
                    class="icon-button"
                  />
                </el-tooltip>
                <el-tooltip content="时间轴" placement="top">
                  <el-button
                    :type="geoEditorStore.isTimelineExpanded ? 'primary' : ''"
                    :icon="Clock"
                    @click="geoEditorStore.isTimelineExpanded = !geoEditorStore.isTimelineExpanded"
                    class="icon-button"
                  />
                </el-tooltip>
              </el-button-group>
            </div>
          </div>

          <!-- 滚动条 -->
          <div v-show="geoEditorStore.isChartExpanded || geoEditorStore.isTimelineExpanded" class="timeline-scrollbar">
            <div
              class="scrollbar-track"
              ref="scrollbarTrackRef"
              @click="handleScrollbarClick"
            >
              <div
                class="scrollbar-thumb"
                :style="scrollbarThumbStyle"
                @mousedown="handleScrollbarDragStart"
              />
            </div>
          </div>

          <!-- 内容区域（图表+时间刻度+时间轴） -->
          <div ref="timelineContentRef" class="timeline-content">
            <!-- 图表区域 -->
            <div v-show="geoEditorStore.isChartExpanded" class="chart-section">
              <GeoChartPanel
                :points="geoEditorStore.points"
                :time-scale-unit="geoEditorStore.timeScaleUnit"
                :highlighted-range="highlightedSegment"
                :zoom-start="geoEditorStore.zoomStart"
                :zoom-end="geoEditorStore.zoomEnd"
                :pointer-position="geoEditorStore.pointerPosition"
                @highlight="handleChartHighlight"
              />
            </div>

            <!-- 时间刻度 -->
            <div v-show="geoEditorStore.isTimelineExpanded" class="scale-section">
              <TimelineScale
                :points="geoEditorStore.points"
                :zoom-start="geoEditorStore.zoomStart"
                :zoom-end="geoEditorStore.zoomEnd"
                :time-scale-unit="geoEditorStore.timeScaleUnit"
                :highlight-index="scaleHighlightIndex"
                @pointer-change="handlePointerChange"
                @scale-hover="handleScaleHover"
                @pan="handleScalePan"
                @update:time-scale-unit="geoEditorStore.timeScaleUnit = $event"
              />
            </div>

            <!-- 时间轴区域 -->
            <div v-show="geoEditorStore.isTimelineExpanded" class="tracks-section">
              <TimelineTracks
                ref="timelineTracksRef"
                :tracks="tracksData"
                :selected-segment-ids="geoEditorStore.selectedSegmentIds"
                :hovered-segment-id="geoEditorStore.hoveredSegmentId"
                :zoom-start="geoEditorStore.zoomStart"
                :zoom-end="geoEditorStore.zoomEnd"
                @select="handleSegmentSelect"
                @hover="handleSegmentHover"
                @save="handleSegmentSave"
                @multi-select-change="handleMultiSelectChange"
              />
            </div>

            <!-- 全局指针线（贯穿图表和时间轴） -->
            <!-- 可拖动区域（透明，更大的点击区域） -->
            <div
              class="playhead-drag-area"
              :style="{ left: playheadXPosition }"
              @mousedown="handlePlayheadMouseDown"
              @touchstart="handlePlayheadTouchStart"
            >
              <!-- 可视化指针线（仅在可见区域显示） -->
              <div
                v-if="isPointerVisible"
                class="global-playhead"
              >
                <div class="playhead-line"></div>
                <div class="playhead-top"></div>
                <div class="playhead-time">{{ pointerTimeText }}</div>
                <div class="playhead-bottom"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-main>
  </div>
</template>

<style scoped>
.geo-editor-container {
  /* 使用动态视口高度，兼容移动浏览器工具栏 */
  height: 100vh;
  height: 100dvh; /* 回退到 100vh */
  display: flex;
  flex-direction: column;
  /* iOS 安全区域：底部添加内边距 */
  padding-bottom: env(safe-area-inset-bottom);
  box-sizing: border-box;
}

/* 导航按钮样式 */
.nav-btn {
  padding: 8px;
}

.home-nav-btn {
  margin-left: 0;
  margin-right: 12px;
}

h1 {
  margin: 0;
  font-size: 18px;
  font-weight: 500;
}

.el-header {
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

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.header-left h1 {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: background 0.2s;
}

.user-info:hover {
  background: var(--el-fill-color-light);
}

.username {
  font-size: 14px;
}

.desktop-only {
  display: inline-block;
}

@media (max-width: 1366px) {
  .desktop-only {
    display: none;
  }
}

.geo-editor-main {
  flex: 1;
  overflow: hidden;
  padding: 0;
  /* 确保主内容区不被底部安全区域遮挡 */
  min-height: 0;
}

.editor-content {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.empty-state {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.map-section {
  flex: 1;
  border-bottom: 1px solid var(--el-border-color);
  overflow: hidden;
}

.timeline-container {
  border-top: 1px solid var(--el-border-color);
  /* 防止移动端双指缩放导致页面缩放 */
  touch-action: none;
}

/* 确保子元素也阻止默认触摸行为 */
.timeline-container .chart-section,
.timeline-container .scale-section,
.timeline-container .tracks-section,
.timeline-container .geo-chart-panel,
.timeline-container .timeline-scale,
.timeline-container .timeline-tracks {
  touch-action: none;
}

.controls-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 12px;
  background: var(--el-bg-color-page);
  border-bottom: 1px solid var(--el-border-color-lighter);
  gap: 8px;
}

.controls-left,
.controls-center,
.controls-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.controls-right {
  margin-left: auto;
}

/* 选中控制和批量操作 */
.selection-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.selection-count-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 24px;
  padding: 0 6px;
  background: var(--el-color-primary);
  color: white;
  font-size: 12px;
  font-weight: bold;
  border-radius: 12px;
  line-height: 1;
}

/* 正方形图标按钮 */
.icon-button {
  padding: 0 !important;
  width: 32px !important;
  height: 32px !important;
  min-width: 32px !important;
}

.icon-button .el-icon {
  font-size: 16px;
}

/* 滚动条样式 */
.timeline-scrollbar {
  height: 12px;
  padding-left: var(--geo-editor-padding-left);
  padding-right: var(--geo-editor-padding-right);
  background: var(--el-bg-color-page);
  border-bottom: 1px solid var(--el-border-color-lighter);
  box-sizing: border-box;
}

.scrollbar-track {
  position: relative;
  width: 100%;
  height: 100%;
  background: var(--el-fill-color-light);
  border-radius: 6px;
  cursor: pointer;
}

.scrollbar-thumb {
  position: absolute;
  top: 2px;
  bottom: 2px;
  background: var(--el-color-primary);
  border-radius: 4px;
  cursor: grab;
  transition: background 0.2s;
}

.scrollbar-thumb:hover {
  background: var(--el-color-primary-dark-2);
}

.scrollbar-thumb:active {
  cursor: grabbing;
}

.chart-section {
  height: 120px;
  position: relative;
}

.scale-section {
  height: 32px;
  position: relative;
}

.tracks-section {
  flex: 1;
  min-height: 160px;
  max-height: 180px;
  overflow: hidden;
  position: relative;
  /* 移动端底部额外空间，防止被工具栏遮挡 */
  padding-bottom: max(0px, env(safe-area-inset-bottom));
  box-sizing: border-box;
}

.timeline-content {
  position: relative;
}

.global-playhead {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 2px;
  z-index: 100;
  pointer-events: none;  /* 让事件穿透到 drag-area */
}

/* 可拖动区域 */
.playhead-drag-area {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 30px;
  z-index: 100;
  cursor: ew-resize;
  pointer-events: auto;
  transform: translateX(-15px);
  background: var(--geo-editor-pointer-bg-idle);
  border-radius: 4px;
  transition: background 0.2s;
}

.playhead-drag-area:hover {
  background: var(--geo-editor-pointer-bg-hover);
}

.global-playhead .playhead-line {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 2px;
  background: var(--geo-editor-pointer-color);
  transform: translateX(14px);
}

.global-playhead .playhead-top,
.global-playhead .playhead-bottom {
  position: absolute;
  left: 9px;
  width: 0;
  height: 0;
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
}

.global-playhead .playhead-top {
  top: -4px;
  border-top: 8px solid var(--geo-editor-pointer-color);
}

.global-playhead .playhead-bottom {
  bottom: -4px;
  border-bottom: 8px solid var(--geo-editor-pointer-color);
}

.global-playhead .playhead-time {
  position: absolute;
  top: -22px;
  left: 50%;
  margin-left: 14px;  /* 与 playhead-line 的偏移对齐 */
  transform: translateX(-50%);
  background: var(--geo-editor-pointer-color);
  color: white;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
  white-space: nowrap;
}
</style>
