<script setup lang="ts">
import { ref, computed } from 'vue'
import type { TrackTimeline, TrackSegment, TrackType } from '@/stores/geo_editor'
import { ElMessageBox } from 'element-plus'
import { useGeoEditorStore } from '@/stores/geoEditor'

interface Props {
  tracks: TrackTimeline[]
  selectedSegmentId: string | null
  hoveredSegmentId: string | null
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
    // 如果清除值，需要确认
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
          v-for="segment in track.segments"
          :key="segment.id"
          class="segment-block"
          :class="{
            'is-selected': segment.id === selectedSegmentId,
            'is-hovered': segment.id === hoveredSegmentId,
            'is-edited': segment.isEdited,
            'is-empty': !segment.value
          }"
          :style="{
            left: `${(segment.startIndex / totalPoints) * 100}%`,
            width: `${(segment.pointCount / totalPoints) * 100}%`
          }"
          @click="handleSelect(segment.id)"
          @dblclick="handleDoubleClick(track.type, segment)"
          @mouseenter="handleHover(segment.id)"
          @mouseleave="handleHover(null)"
        >
          <span v-if="segment.value || (segment.id === selectedSegmentId || segment.id === hoveredSegmentId)" class="segment-text">
            {{ segment.value || '(空)' }}
          </span>
        </div>
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
  padding: 8px 0;
}

.track-row {
  display: flex;
  align-items: center;
  height: 36px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.track-label {
  width: 80px;
  flex-shrink: 0;
  padding-left: 16px;
  font-size: 13px;
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
  height: 24px;
  display: flex;
  align-items: center;
  padding: 0 4px;
  background: var(--el-color-primary-light-9);
  border: 1px solid var(--el-color-primary-light-7);
  border-radius: 4px;
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.2s;
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
</style>
