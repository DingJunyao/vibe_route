<script setup lang="ts">
import { ref, computed } from 'vue'
import type { TrackTimeline, TrackSegment, TrackType } from '@/stores/geo_editor'
import { ElMessageBox } from 'element-plus'
import { useGeoEditorStore } from '@/stores/geoEditor'

interface Props {
  tracks: TrackTimeline[]
  selectedSegmentId: string | null
  hoveredSegmentId: string | null
  zoomStart: number
  zoomEnd: number
  pointerPosition: number
}

const props = defineProps<Props>()

const emit = defineEmits<{
  select: [segmentId: string]
  hover: [segmentId: string | null]
  save: [data: { trackType: TrackType; segmentId: string; value: string; valueEn: string | null }]
}>()

const geoEditorStore = useGeoEditorStore()

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

// 计算指针位置（相对于可见区域）
const pointerVisiblePosition = computed(() => {
  if (props.pointerPosition < props.zoomStart || props.pointerPosition > props.zoomEnd) return null
  return ((props.pointerPosition - props.zoomStart) / (props.zoomEnd - props.zoomStart)) * 100
})

// 双击编辑
function handleDoubleClick(trackType: TrackType, segment: TrackSegment) {
  editTrackType.value = trackType
  editSegmentId.value = segment.id
  editValue.value = segment.value || ''
  editValueEn.value = segment.valueEn || ''
  editDialogVisible.value = true
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
function handleSelect(segmentId: string) {
  emit('select', segmentId)
}

// 悬停
function handleHover(segmentId: string | null) {
  emit('hover', segmentId)
}

// 轨道配置
function getTrackConfig(trackType: TrackType) {
  return TRACK_CONFIG[trackType]
}

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
</script>

<template>
  <div class="timeline-tracks">
    <!-- 轨道行 -->
    <div
      v-for="track in tracks"
      :key="track.type"
      class="track-row"
    >
      <div class="track-label">
        {{ track.label }}
      </div>
      <div class="track-content">
        <!-- 段落块 -->
        <div
          v-for="item in (segmentsByTrack[track.type] || [])"
          :key="item.segment.id"
          class="segment-block"
          :class="{
            'is-selected': item.segment.id === selectedSegmentId,
            'is-hovered': item.segment.id === hoveredSegmentId,
            'is-edited': item.segment.isEdited,
            'is-empty': !item.segment.value
          }"
          :style="{
            left: `${item.visibleStart}%`,
            width: `${item.visibleWidth}%`
          }"
          @click="handleSelect(item.segment.id)"
          @dblclick="handleDoubleClick(track.type, item.segment)"
          @mouseenter="handleHover(item.segment.id)"
          @mouseleave="handleHover(null)"
        >
          <span v-if="item.segment.value || (item.segment.id === selectedSegmentId || item.segment.id === hoveredSegmentId)" class="segment-text">
            {{ item.segment.value || '(空)' }}
          </span>
        </div>

        <!-- 指针线 -->
        <div
          v-if="pointerVisiblePosition !== null"
          class="track-pointer"
          :style="{ left: `${pointerVisiblePosition}%` }"
        ></div>
      </div>
    </div>

    <!-- 编辑对话框 -->
    <el-dialog
      v-model="editDialogVisible"
      :title="`编辑${getTrackConfig(editTrackType).label}`"
      width="400px"
      :close-on-click-modal="false"
    >
      <el-form label-width="80px">
        <el-form-item :label="getTrackConfig(editTrackType).label">
          <el-input
            v-model="editValue"
            :placeholder="getTrackConfig(editTrackType).placeholder"
            clearable
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
  padding: 4px 0;
}

.track-row {
  display: flex;
  align-items: center;
  height: 32px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.track-label {
  width: 65px;
  flex-shrink: 0;
  padding-left: 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  border-right: 1px solid var(--el-border-color-lighter);
}

.track-content {
  flex: 1;
  position: relative;
  min-height: 100%;
}

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

.segment-block.is-edited {
  background: var(--el-color-warning-light-9);
  border-color: var(--el-color-warning-light-7);
}

.segment-block.is-edited.is-selected {
  background: var(--el-color-warning);
  border-color: var(--el-color-warning-dark-2);
}

.segment-block.is-empty {
  background: var(--el-fill-color-light);
  border-color: var(--el-border-color);
  border-style: dashed;
}

.segment-text {
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.track-pointer {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 1px;
  background: #f56c6c;
  pointer-events: none;
  z-index: 20;
}
</style>
