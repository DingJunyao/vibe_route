# 地理编辑器重新设计实施计划

> **For Claude:** 重新实现地理编辑器，使用 Premiere 风格三轨道竖向时间轴

**目标：** 构建类似 Premiere 的地理信息编辑器，三轨道竖向时间轴，地图为主视图

**架构：** 地图占满主体区域，右侧三轨道时间轴（行政区划、道路编号、道路名称）

**技术栈：** Vue 3 (Composition API), Element Plus

---

## 设计确认

### 布局结构（右侧竖向三轨道）

```
┌─────────────────────────────────────────────────────────────┐
│ Header: [返回] [主页] 轨迹名称    [撤销] [重做] [保存]        │
├───────────────────────────┬──────────────────────────────────────┤
│                             │                                      │
│     地图 (全屏显示)         │     右侧时间轴 (120px)              │
│                             │  ┌────────────────────────────────┐   │
│                             │  │ 轨道1: 行政区划             │   │
│                             │  ├────────────────────────────────┤   │
│                             │  │ 轨道2: 道路编号             │   │
│                             │  ├────────────────────────────────┤   │
│                             │  │ 轨道3: 道路名称             │   │
│                             │  └────────────────────────────────┘   │
│                             │                                      │
└───────────────────────────┴──────────────────────────────────────┘
```

### 三轨道设计

**轨道1：行政区划** → 显示：北京市、朝阳区...
**轨道2：道路编号** → 显示：G2、G4...
**轨道3：道路名称** → 显示：京沪高速...

### 交互规则

| 操作 | 效果 |
|------|------|
| 单击段落块 | 选中该段落（地图高亮） |
| 双击段落块 | 弹出编辑对话框 |
| 鼠标悬停轨道段落 | 地图上高亮对应段落区域 |
| 地图上悬停点 | 显示当前点信息 tooltip |
| 时间轴滚动 | 地图跟随滚动定位 |
| 段落宽度 | 按点数比例计算 |

---

## Task 1: 重写 GeoEditor.vue

**删除：** 旧组件引用和状态
**创建：** 新的三轨道时间轴结构

### 核心数据结构

```typescript
// 单个轨道的段落
interface TimelineSegment {
  id: string
  startIndex: number
  endIndex: number
  pointCount: number
  value: string  // 行政区划、道路编号或道路名称
}

// 计算属性
const adminSegments = computed(() => buildSegments('admin'))      // 行政区划
const roadNumberSegments = computed(() => buildSegments('roadNumber')) // 道路编号
const roadNameSegments = computed(() => buildSegments('roadName'))    // 道路名称
```

---

## Task 2: 创建 TimelineTracks 组件

**文件：** `frontend/src/components/geo-editor/TimelineTracks.vue`

**三轨道结构：**

```vue
<template>
  <div class="timeline-tracks">
    <!-- 轨道1: 行政区划 -->
    <div class="track">
      <div class="track-label">行政区划</div>
      <div class="track-content">
        <div v-for="segment in adminSegments" class="segment-block">
          {{ segment.value }}
        </div>
      </div>
    </div>
    <!-- 轨道2: 道路编号 -->
    <div class="track">
      <div class="track-label">道路编号</div>
      <div class="track-content">
        <div v-for="segment in roadNumberSegments" class="segment-block">
          {{ segment.value }}
        </div>
      </div>
    </div>
    <!-- 轨道3: 道路名称 -->
    <div class="track">
      <div class="track-label">道路名称</div>
      <div class="track-content">
        <div v-for="segment in roadNameSegments" class="segment-block">
          {{ segment.value }}
        </div>
      </div>
    </div>
  </div>
</template>
```

---

## Task 3: 更新 SegmentEditDialog

**文件：** `frontend/src/components/geo-editor/SegmentEditDialog.vue`

---

## Task 4: 清理旧组件

**删除：**
- `GeoTimeline.vue`
- `TimelineTable.vue`
- `SharedMapPanel.vue`

---

## 样式定义

```css
.timeline-tracks {
  width: 120px;
  height: 100%;
  background: var(--el-bg-color);
  border-left: 1px solid var(--el-border-color);
  display: flex;
  flex-direction: column;
  gap: 0;
  overflow-y: auto;
}

.track {
  border-bottom: 1� 0 solid var(--el-border-color);
}

.track-label {
  padding: 8px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  text-align: center;
  background: var(--el-fill-color-light);
  font-weight: 500;
}

.segment-block {
  background: var(--el-fill-color);
  border-radius: 4px;
  cursor: pointer;
  min-height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 4px;
}

.segment-block.selected {
  background: var(--el-color-primary);
}
```

---

## 待确认的问题

1. **三个轨道的数据同步**：编辑一个轨道后，其他轨道对应段落是否也需要同步修改？

2. **段落合并逻辑**：每个轨道独立分段，还是基于同一个索引范围？

3. **编辑对话框内容**：
   - 编辑行政区划轨道 → 只编辑行政区划字段？
   - 编辑道路编号轨道 → 只编辑道路编号字段？
   - 还是需要一个综合对话框包含所有字段？

请确认后开始实施。
