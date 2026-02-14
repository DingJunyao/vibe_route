# 地理信息编辑器：拖动调整与拖动移动设计

**日期**: 2026-02-05
**状态**: 实现中
**优先级**: 高

## 概述

为地理信息编辑器的轨道时间轴添加拖动调整（resize）和拖动移动（move）功能，允许用户通过直观的拖拽操作调整段落边界和位置。

## 功能需求

### 1. 拖动调整（Resize）

| 操作 | 触发方式 | 行为 |
|------|---------|------|
| 调整左边界 | 拖动左侧手柄 | 改变段落起始位置 |
| 调整右边界 | 拖动右侧手柄 | 改变段落结束位置 |
| 实时预览 | 拖动过程中 | 显示虚线预览边界 |
| 确认调整 | 松开鼠标/手指 | 应用更改，记录历史 |

### 2. 拖动移动（Move）

| 操作 | 触发方式 | 行为 |
|------|---------|------|
| 移动段落 | 拖动段落中心区域 | 移动整个段落 |
| 实时预览 | 拖动过程中 | 显示虚线预览位置 |
| 确认移动 | 松开鼠标/手指 | 应用更改，记录历史 |

### 3. 交互方式

**桌面端**：
- 悬停段落时显示左右手柄（4-6px 宽度）
- 拖动边缘手柄进行 resize
- 拖动中心区域进行 move
- 鼠标指针变化指示操作类型

**移动端**：
- 长按选中的段落进入"编辑模式"
- 编辑模式下显示手柄和高亮状态
- 拖动后弹出确认对话框
- 触觉反馈（如果设备支持）

### 4. 约束规则

| 约束 | 描述 |
|------|------|
| 不交叉 | 不能移动/调整到与其他段落重叠 |
| 最小尺寸 | 段落不能小于 3 个点 |
| 唯一性 | 同一轨道内不能有相邻的同值段落 |
| 自动合并 | 移动后与同值段落相邻时自动合并 |

### 5. 移动端确认对话框

```
┌─────────────────────────────┐
│  确认修改                    │
├─────────────────────────────┤
│  将段落移动到新位置          │
│  起点: 123 → 456             │
│  终点: 234 → 567             │
├─────────────────────────────┤
│  [取消]     [确认]           │
└─────────────────────────────┘
```

## 数据模型变更

```typescript
// stores/geoEditor.ts 新增方法

interface DragResizeResult {
  success: boolean
  message?: string
  autoMerged?: boolean
}

// 拖动调整段落
function resizeSegment(
  trackType: TrackType,
  segmentId: string,
  newStartIndex: number,
  newEndIndex: number
): DragResizeResult

// 拖动移动段落
function moveSegment(
  trackType: TrackType,
  segmentId: string,
  targetStartIndex: number
): DragResizeResult
```

## 文件变更清单

| 文件 | 变更内容 |
|------|---------|
| `stores/geoEditor.ts` | 新增 resizeSegment、moveSegment、validateSegmentPosition 方法 |
| `components/geo-editor/TimelineTracks.vue` | 添加手柄元素、拖动事件处理、移动端编辑模式 |
| `views/GeoEditor.vue` | 传递 resize/move 事件到 store |

## UI 设计

### 手柄样式

```css
.segment-handle {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 6px;
  background: var(--el-color-primary);
  opacity: 0;
  transition: opacity 0.2s;
  cursor: col-resize;
}

.segment-block:hover .segment-handle {
  opacity: 0.5;
}

.segment-handle:hover {
  opacity: 1 !important;
}
```

### 拖动预览

```css
.segment-block.is-dragging {
  opacity: 0.5;
}

.segment-preview {
  position: absolute;
  border: 2px dashed var(--el-color-primary);
  background: rgba(64, 158, 255, 0.1);
  pointer-events: none;
}
```

### 移动端编辑模式

```css
.segment-block.is-edit-mode {
  border-width: 2px;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.3);
  animation: edit-pulse 1.5s ease-in-out infinite;
}

@keyframes edit-pulse {
  0%, 100% { box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.3); }
  50% { box-shadow: 0 0 0 4px rgba(64, 158, 255, 0.5); }
}
```

## 事件流程

### 桌面端拖动调整

1. `mouseenter` 段落 → 显示手柄
2. `mousedown` 手柄 → 记录起始位置和方向
3. `mousemove` → 计算新边界，显示预览
4. `mouseup` → 验证约束，应用更改，记录历史

### 桌面端拖动移动

1. `mouseenter` 段落 → 显示移动光标
2. `mousedown` 中心区域 → 记录起始位置
3. `mousemove` → 计算新位置，显示预览
4. `mouseup` → 验证约束，应用更改，检查合并，记录历史

### 移动端编辑

1. `touchstart` 选中段落 + 长按 → 进入编辑模式
2. 触觉反馈
3. `touchmove` → 计算新位置，显示预览
4. `touchend` → 显示确认对话框
5. 确认后应用更改

## 约束验证逻辑

### 不交叉

```typescript
function checkNoOverlap(
  track: TrackTimeline,
  segmentId: string,
  newStart: number,
  newEnd: number
): boolean {
  for (const seg of track.segments) {
    if (seg.id === segmentId) continue
    if (newStart <= seg.endIndex && newEnd >= seg.startIndex) {
      return false  // 重叠
    }
  }
  return true
}
```

### 最小尺寸

```typescript
const MIN_SEGMENT_SIZE = 3

if (newEndIndex - newStartIndex + 1 < MIN_SEGMENT_SIZE) {
  return { success: false, message: '段落不能小于 3 个点' }
}
```

### 唯一性

```typescript
function checkUniqueness(
  track: TrackTimeline,
  segmentId: string,
  newStart: number,
  newEnd: number,
  value: string | null
): boolean {
  // 检查相邻段落是否同值
  // 如果是，需要合并
}
```

### 自动合并

```typescript
function autoMergeIfNeeded(
  track: TrackTimeline,
  segmentId: string
): boolean {
  // 检查前后是否有同值段落
  // 如果有，合并并返回 true
}
```

## 撤销/重做

所有 resize 和 move 操作都通过现有的 `recordHistory()` 机制记录，支持撤销和重做。

```typescript
recordHistory('resize', `调整段落边界`)
recordHistory('move', `移动段落位置`)
```

## 后续扩展

此功能为后续操作奠定基础：

- **拖动创建**：在空区域拖动创建新段落
- **复制粘贴**：复制段落到其他位置
- **快捷键**：Delete 删除、Ctrl+Z 撤销等
