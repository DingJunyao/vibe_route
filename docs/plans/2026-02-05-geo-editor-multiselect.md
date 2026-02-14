# 地理信息编辑器：多选与批量操作实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为地理信息编辑器的轨道时间轴添加多选和批量操作功能，支持 Ctrl/Shift 多选、批量清空、批量合并。

**Architecture:**
1. Store 层：将选择状态从单 ID 改为 Set，添加多选/批量方法
2. 组件层：TimelineTracks 处理修饰键检测和点击逻辑，GeoEditor 添加控制栏 UI
3. 地图层：UniversalMap 支持多个高亮区域

**Tech Stack:** Vue 3 Composition API, Pinia, TypeScript, Element Plus

---

## Task 1: Store 层 - 选择状态重构

**Files:**
- Modify: `frontend/src/stores/geoEditor.ts`

**Step 1: 修改选择状态类型**

将 `selectedSegmentId` 改为 `selectedSegmentIds` (Set 类型)，并更新相关计算属性。

在 `frontend/src/stores/geoEditor.ts` 中找到：

```typescript
// 选择状态
const selectedSegmentId = ref<string | null>(null)
const hoveredSegmentId = ref<string | null>(null)
```

替换为：

```typescript
// 选择状态
const selectedSegmentIds = ref<Set<string>>(new Set())
const hoveredSegmentId = ref<string | null>(null)

// 选中数量（用于 UI 显示）
const selectedCount = computed(() => selectedSegmentIds.value.size)
```

**Step 2: 修改选择相关方法**

找到原有的 `selectSegment` 方法：

```typescript
// 选择段落
function selectSegment(segmentId: string) {
  selectedSegmentId.value = segmentId
}
```

替换为：

```typescript
// 选择段落（支持多选）
function selectSegment(segmentId: string | null, addToSelection: boolean = false) {
  if (segmentId === null) {
    // 取消所有选择
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

// 获取每个轨道选中的段落（按位置排序）
function getSelectedSegmentsByTrack(): Map<string, TrackSegment[]> {
  const result = new Map<string, TrackSegment[]>()
  for (const track of tracks.value) {
    const selected = track.segments
      .filter(s => selectedSegmentIds.value.has(s.id))
      .sort((a, b) => a.startIndex - b.startIndex)
    if (selected.length > 0) {
      result.set(track.type, selected)
    }
  }
  return result
}
```

**Step 3: 添加批量操作方法**

在 `saveToServer` 方法后添加批量操作方法：

```typescript
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
```

**Step 4: 更新 return 导出**

找到 `return {` 部分，更新导出：

```typescript
return {
  // State
  trackId,
  trackName,
  points,
  tracks,
  totalDuration,
- selectedSegmentId,
+ selectedSegmentIds,
+ selectedCount,
  hoveredSegmentId,
  // ... 其他 state

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
- selectSegment,
+ selectSegment,
+ clearSelection,
+ clearSelectedSegments,
+ canMergeSelected,
+ mergeSelectedSegments,
+ getSelectedSegmentsByTrack,
  hoverSegment,
  // ... 其他 actions
}
```

**Step 5: 更新 recordHistory 中的 selectedSegmentId 引用**

找到 `recordHistory` 方法，更新对 `selectedSegmentId` 的引用：

```typescript
after: {
  tracks: JSON.parse(JSON.stringify(tracks.value)),
- selectedSegmentId: selectedSegmentId.value,
+ selectedSegmentIds: Array.from(selectedSegmentIds.value),
},
```

**Step 6: 更新 restoreState 方法**

```typescript
function restoreState(state: EditHistory['before'] | EditHistory['after']) {
  tracks.value = JSON.parse(JSON.stringify(state.tracks))
- selectedSegmentId.value = state.selectedSegmentId
+ selectedSegmentIds.value = new Set(state.selectedSegmentIds || [])
  hasUnsavedChanges.value = true
}
```

**Step 7: 更新历史记录初始化**

在 `updateSegmentValue` 方法中找到历史初始化部分：

```typescript
before: {
  tracks: JSON.parse(JSON.stringify(tracks.value)),
- selectedSegmentId: selectedSegmentId.value,
+ selectedSegmentIds: Array.from(selectedSegmentIds.value),
},
after: {
  tracks: JSON.parse(JSON.stringify(tracks.value)),
- selectedSegmentId: selectedSegmentId.value,
+ selectedSegmentIds: Array.from(selectedSegmentIds.value),
},
```

**Step 8: Commit**

```bash
cd frontend
git add src/stores/geoEditor.ts
git commit -m "refactor: 重构选择状态为 Set，支持多选"
```

---

## Task 2: TimelineTracks 组件 - 多选交互

**Files:**
- Modify: `frontend/src/components/geo-editor/TimelineTracks.vue`

**Step 1: 更新 Props 定义**

将 `selectedSegmentId` 改为 `selectedSegmentIds`：

```typescript
interface Props {
  tracks: TrackTimeline[]
- selectedSegmentId: string | null
+ selectedSegmentIds: Set<string>
  hoveredSegmentId: string | null
  zoomStart: number
  zoomEnd: number
}
```

**Step 2: 更新 emit 定义**

```typescript
const emit = defineEmits<{
- select: [segmentId: string]
+ select: [segmentId: string | null, addToSelection: boolean]
+ clearSelection: []
  hover: [segmentId: string | null]
  save: [data: { trackType: TrackType; segmentId: string; value: string; valueEn: string | null }]
}>()
```

**Step 3: 添加修饰键状态**

在 script setup 中添加：

```typescript
// 修饰键状态
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
```

**Step 4: 更新点击处理函数**

替换 `handleSelect` 函数：

```typescript
function handleSelect(segmentId: string, e: MouseEvent) {
  const addToSelection = e.ctrlKey || e.shiftKey
  emit('select', segmentId, addToSelection)
}
```

**Step 5: 添加轨道行空白点击处理**

在 `handleSelect` 后添加：

```typescript
// 点击轨道行空白区域
function handleTrackRowClick() {
  emit('select', null, false)
}
```

**Step 6: 更新模板中的 class 绑定**

找到 `.segment-block` 的 class 绑定：

```vue
:class="{
- 'is-selected': item.segment.id === selectedSegmentId,
+ 'is-selected': selectedSegmentIds.has(item.segment.id),
  'is-hovered': item.segment.id === hoveredSegmentId,
  'is-edited': item.segment.isEdited,
  'is-empty': !item.segment.value
}"
```

**Step 7: 更新模板中的点击事件**

```vue
@click="handleSelect(item.segment.id, $event)"
```

**Step 8: 添加轨道行点击事件**

在 `.track-row` 上添加点击事件：

```vue
<div
  v-for="track in tracks"
  :key="track.type"
  class="track-row"
+ @click="handleTrackRowClick"
>
```

**Step 9: 更新可见性判断逻辑**

找到 `segment-text` 的条件判断：

```vue
<span v-if="item.segment.value || (selectedSegmentIds.has(item.segment.id) || item.segment.id === hoveredSegmentId)" class="segment-text">
```

**Step 10: 添加多选视觉样式**

在 style 部分添加选中角标样式：

```css
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
```

**Step 11: 确保添加 onMounted/onUnmounted 导入**

检查 script 开头的导入：

```typescript
import { ref, computed, onMounted, onUnmounted } from 'vue'
```

**Step 12: Commit**

```bash
cd frontend
git add src/components/geo-editor/TimelineTracks.vue
git commit -m "feat: 支持轨道块多选交互（Ctrl/Shift）"
```

---

## Task 3: GeoEditor 页面 - 控制栏 UI

**Files:**
- Modify: `frontend/src/views/GeoEditor.vue`

**Step 1: 更新 selectedSegmentId 引用**

找到所有使用 `geoEditorStore.selectedSegmentId` 的地方并更新：

找到：
```typescript
const highlightedSegment = computed(() => {
- const id = geoEditorStore.selectedSegmentId || geoEditorStore.hoveredSegmentId
+ const ids = geoEditorStore.selectedSegmentIds
+ const id = ids.size > 0 ? Array.from(ids)[0] : geoEditorStore.hoveredSegmentId
```

**Step 2: 更新 TimelineTracks 组件 props**

找到 TimelineTracks 组件的使用：

```vue
<TimelineTracks
  :tracks="tracksData"
- :selected-segment-id="geoEditorStore.selectedSegmentId"
+ :selected-segment-ids="geoEditorStore.selectedSegmentIds"
  :hovered-segment-id="geoEditorStore.hoveredSegmentId"
  :zoom-start="geoEditorStore.zoomStart"
  :zoom-end="geoEditorStore.zoomEnd"
- @select="geoEditorStore.selectSegment"
+ @select="handleSegmentSelect"
+ @clear-selection="geoEditorStore.clearSelection"
  @hover="geoEditorStore.hoverSegment"
  @save="handleSaveSegment"
/>
```

**Step 3: 添加选择处理函数**

在 script setup 中添加：

```typescript
// 处理轨道块选择
function handleSegmentSelect(segmentId: string | null, addToSelection: boolean) {
  if (segmentId === null) {
    geoEditorStore.clearSelection()
  } else {
    geoEditorStore.selectSegment(segmentId, addToSelection)
  }
}

// 批量清空
async function handleBatchClear() {
  const count = geoEditorStore.selectedCount
  if (count === 0) return

  geoEditorStore.clearSelectedSegments()
  ElMessage.success(`已清空 ${count} 个段落`)
}

// 批量合并
async function handleBatchMerge() {
  if (!geoEditorStore.canMergeSelected()) {
    ElMessage.warning('请选择连续的段落进行合并')
    return
  }

  geoEditorStore.mergeSelectedSegments()
  ElMessage.success('合并完成')
}
```

**Step 4: 添加页面级键盘事件**

找到 `onMounted` 和 `onUnmounted` 钩子，添加键盘事件：

```typescript
onMounted(() => {
  // ... 现有代码
  window.addEventListener('keydown', handleGlobalKeydown)
})

onUnmounted(() => {
  // ... 现有代码
  window.removeEventListener('keydown', handleGlobalKeydown)
})

// 全局键盘事件
function handleGlobalKeydown(e: KeyboardEvent) {
  // Esc 取消选择
  if (e.key === 'Escape') {
    if (geoEditorStore.selectedCount > 0) {
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
```

**Step 5: 更新控制栏 UI**

找到 `.controls-center` 部分，替换为：

```vue
<div class="controls-center">
  <!-- 选中数量和批量操作 -->
  <transition name="el-fade-in">
    <div v-if="geoEditorStore.selectedCount > 0" class="selection-controls">
      <span class="selection-info">
        已选择 <strong>{{ geoEditorStore.selectedCount }}</strong> 个块
      </span>
      <el-button-group size="small">
        <el-tooltip content="清空选中 (Delete)" placement="top">
          <el-button @click="handleBatchClear">清空</el-button>
        </el-tooltip>
        <el-tooltip content="合并选中" placement="top">
          <el-button
            @click="handleBatchMerge"
            :disabled="!geoEditorStore.canMergeSelected()"
          >
            合并
          </el-button>
        </el-tooltip>
      </el-button-group>
    </div>
  </transition>

  <!-- 时间刻度单位选择器 -->
  <el-select v-model="geoEditorStore.timeScaleUnit" size="small" style="width: 70px;">
    <el-option value="time" label="时间" />
    <el-option value="duration" label="时长" />
    <el-option value="index" label="索引" />
  </el-select>
</div>
```

**Step 6: 添加样式**

在 style 部分添加：

```css
.selection-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

.selection-info {
  font-size: 12px;
  color: var(--el-color-primary);
  white-space: nowrap;
}
```

**Step 7: Commit**

```bash
cd frontend
git add src/views/GeoEditor.vue
git commit -m "feat: 添加批量操作 UI 和快捷键支持"
```

---

## Task 4: UniversalMap 组件 - 多段高亮支持

**Files:**
- Modify: `frontend/src/components/map/UniversalMap.vue`

**Step 1: 更新 Props 定义**

找到 highlightSegment prop：

```typescript
interface Props {
  // ... 其他 props
- highlightSegment?: { start: number; end: number } | null
+ highlightSegments?: Array<{ start: number; end: number }> | null
  // ... 其他 props
}

const props = withDefaults(defineProps<Props>(), {
  // ...
- highlightSegment: null,
+ highlightSegments: null,
  // ...
})
```

**Step 2: 更新高亮计算属性**

如果有专门计算高亮的逻辑，需要更新为处理数组：

```typescript
// 兼容处理：将单个对象转为数组
const normalizedHighlightSegments = computed(() => {
  if (!props.highlightSegments || props.highlightSegments.length === 0) {
    return []
  }
  return props.highlightSegments
})
```

**Step 3: 更新地图组件传递**

对于各个地图引擎组件（AMap.vue、BMap.vue、TMap.vue、LeafletMap.vue），需要更新它们接收高亮区域的方式。

这部分需要根据具体实现调整。最简单的方案是：

```typescript
// 将多段合并为一个大的高亮区域
const mergedHighlightSegment = computed(() => {
  const segments = normalizedHighlightSegments.value
  if (segments.length === 0) return null

  // 找到最小起始和最大结束
  const minStart = Math.min(...segments.map(s => s.start))
  const maxEnd = Math.max(...segments.map(s => s.end))

  return { start: minStart, end: maxEnd }
})
```

然后在传递给子组件时使用 `mergedHighlightSegment`。

**Step 4: 更新 GeoEditor 传递给地图的 props**

回到 `GeoEditor.vue`，找到高亮区域的计算：

```typescript
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
```

然后传递给 UniversalMap：

```vue
<UniversalMap
  :highlight-segments="highlightedSegments"
  ...
/>
```

**Step 5: Commit**

```bash
cd frontend
git add src/components/map/UniversalMap.vue src/views/GeoEditor.vue
git commit -m "feat: 地图支持多段高亮显示"
```

---

## Task 5: 测试与验证

**Step 1: 启动开发服务器**

```bash
cd frontend
npm run dev
```

**Step 2: 手动测试清单**

- [ ] 单击轨道块：仅选中该块
- [ ] Ctrl + 点击：添加/移除选择
- [ ] Shift + 点击：添加/移除选择
- [ ] 点击轨道行空白：取消所有选择
- [ ] 按 Esc 键：取消所有选择
- [ ] 按 Delete 键：清空选中块
- [ ] 选中数量显示正确
- [ ] 合并按钮在无可合并块时禁用
- [ ] 合并连续块：正确合并
- [ ] 合并不连续块：提示或跳过
- [ ] 地图高亮：显示所有选中块
- [ ] 撤销/重做：正确恢复选择状态

**Step 3: 修复发现的问题**

记录并修复测试中发现的问题。

**Step 4: 最终 Commit**

```bash
cd frontend
git add -A
git commit -m "fix: 修复多选功能测试发现的问题"
```

---

## 完成检查

- [ ] Store 层选择状态重构完成
- [ ] TimelineTracks 多选交互完成
- [ ] GeoEditor 控制栏 UI 完成
- [ ] UniversalMap 多段高亮完成
- [ ] 所有测试通过
- [ ] 代码已提交

## 后续步骤

完成此功能后，可继续实现：
1. 轨道块拖动边缘扩展/缩小
2. 轨道块拖动移动
3. 按指针位置拆分
4. 级联约束（下级不超出上级）
