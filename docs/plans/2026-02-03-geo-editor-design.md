# 轨迹地理信息在线编辑功能设计文档

**创建日期**: 2026-02-03
**状态**: 设计已确认

---

## 1. 功能概述

新增一个**轨迹地理信息在线编辑功能**，用户可以在时间轴界面编辑轨迹点的行政区划（省/市/区）、道路编号、道路名称及其英文字段。编辑后的数据用于生成实况覆盖层。

### 核心问题

- 轨迹点可能上万，大多数地理信息重复
- 需要高效的显示与编辑方案
- 支持撤销重做和历史记录

---

## 2. 整体架构与布局

### 页面结构

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Header: [返回] [主页] 轨迹名称          [撤销] [重做] [●未保存] [保存]  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│                      地图区域（占满主体空间）                            │
│                      支持悬停高亮、点击定位                              │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│  ▼ 图表  [海拔] [速度]  刻度: [时间▼时长点索引]            [─ 折叠 +]  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │   14:23:00.000 ──── 14:28:23.456 ──── 14:33:46.912 ──── →      │  │
│  │        /\        /\                   /\                         │  │
│  │       /  \      /  \                 /  \                        │  │
│  │      │    \    /    \               /    \                       │  │
│  │      │     \  /      \             /      \                      │  │
│  │       ──────\/────────\───────────/────────────────             │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│  ▼ 时间轴                                                   [─ 折叠 +]  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ 省级   │ [北京市───────] [河北省─────────────────────] [山东──] │  │
│  │ 地级   │ [朝阳区───────] [石家庄市───────────────────] [济南──] │  │
│  │ 县级   │ [─────] [裕华区──────────────────────────────] [─────] │  │
│  │ 道路编号│ [G4───] [───────────────] [G2────────────────────────] │  │
│  │ 道路名称│ [京港澳─────] [────────────────────────] [京沪───────] │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5条水平轨道

| 轨道 | 字段 | 有英文 | 层级关系 |
|------|------|--------|----------|
| 省级 | province | ✓ | 顶级 |
| 地级 | city | ✓ | 依赖省级 |
| 县级 | district | ✓ | 依赖地级 |
| 道路编号 | road_number | ✗ | 独立 |
| 道路名称 | road_name | ✓ | 独立 |

### 刻度单位

| 单位 | 格式 | 示例 | 说明 |
|------|------|------|------|
| **时间** | `HH:MM:SS.mmm` | `14:23:45.678` | GPS 时间（用户时区），**默认** |
| **时长** | `HH:MM:SS.mmm` | `00:05:23.456` | 从起点开始的累计时长 |
| **点索引** | 数字 | `1234` | 直接显示点的索引值 |

**重要**：不管刻度单位怎么切换，段落宽度始终按时长比例计算。

### 折叠功能

- 图表区域可折叠（节省空间）
- 时间轴区域可折叠（专注地图编辑）
- 默认状态：图表展开，时间轴展开

### 指针（Playhead）

红色竖线，类似视频编辑软件的时间轴指针：

- 用于**查看**当前时刻的属性，不用于修改数据
- 可拖动或点击时间轴任意位置跳转
- 指针旁显示当前时刻的属性值（悬浮卡片）

```typescript
interface PointerState {
  position: number        // 时间位置（0-1 比例或毫秒）
  isDragging: boolean
  showAttributes: boolean // 是否显示属性卡片
}

// 指针旁显示的属性
interface PointerAttributes {
  time: string            // 当前时间（HH:MM:SS.mmm）
  province: string | null
  city: string | null
  district: string | null
  roadNumber: string | null
  roadName: string | null
}
```

属性卡片样式：
- 跟随指针位置
- 半透明背景，不遮挡图表和时间轴
- 仅在指针位置发生变化时更新

### 三向联动

- **悬停时间轴段落** → 地图高亮对应区域 + 图表高亮对应位置
- **悬停图表** → 地图显示 tooltip + 时间轴高亮对应段落
- **点击地图点** → 图表高亮 + 时间轴滚动到对应段落 + 指针跳转
- **移动指针** → 地图标记对应位置 + 图表高亮 + 显示属性卡片
- **共享水平滚动**：图表和时间轴在同一滚动容器，确保对齐

---

## 3. 核心数据结构

### TrackSegment - 轨道段落

```typescript
interface TrackSegment {
  id: string                    // 唯一标识（前端生成）
  startIndex: number            // 起始点索引
  endIndex: number              // 结束点索引（包含）
  pointCount: number            // 点数量

  // 该轨道的值（只存储该轨道对应的字段）
  value: string | null          // 显示文本
  valueEn: string | null        // 英文文本（道路编号无此字段）

  // UI 状态
  isSelected?: boolean
  isHovered?: boolean
  isEdited?: boolean            // 是否被用户编辑过
}
```

### TrackTimeline - 轨道定义

```typescript
type TrackType = 'province' | 'city' | 'district' | 'roadNumber' | 'roadName'

interface TrackTimeline {
  type: TrackType               // 轨道类型
  label: string                 // 显示标签（如"省级"）
  segments: TrackSegment[]      // 该轨道的所有段落
  hasEnglish: boolean           // 是否有英文字段（道路编号为 false）
}

// 行政区划轨道层级关系
const TRACK_HIERARCHY = {
  province: null,               // 顶级
  city: 'province',             // 依赖省级
  district: 'city',             // 依赖地级
  roadNumber: null,             // 独立
  roadName: null                // 独立
}
```

### GeoEditorState - 编辑器状态

```typescript
interface GeoEditorState {
  trackId: number
  points: TrackPoint[]          // 所有轨迹点
  tracks: TrackTimeline[]       // 5条轨道
  totalDuration: number         // 总时长（毫秒）

  // 选择状态
  selectedSegmentId: string | null
  hoveredSegmentId: string | null

  // 刻度显示
  timeScaleUnit: 'time' | 'duration' | 'index'

  // 折叠状态
  isChartExpanded: boolean
  isTimelineExpanded: boolean

  // 历史记录
  history: EditHistory[]
  historyIndex: number

  // 持久化
  hasUnsavedChanges: boolean
  lastSavedAt: number | null
}
```

---

## 4. 编辑交互逻辑

### 波纹剪辑：拖动边界

当用户拖动某轨道的段落边界时：

```typescript
// 行政区划轨道：联动拖动
function handleAdminBoundaryDrag(
  trackType: 'province' | 'city' | 'district',
  segmentId: string,
  newBoundaryIndex: number,
  isStart: boolean  // true=拖动起始边界, false=拖动结束边界
) {
  // 1. 更新当前轨道段落边界
  updateSegmentBoundary(trackType, segmentId, newBoundaryIndex, isStart)

  // 2. 级联更新下级轨道
  const childTracks = getChildTracks(trackType)
  childTracks.forEach(childType => {
    cascadeUpdateBoundaries(childType, segmentId, newBoundaryIndex, isStart)
  })

  // 3. 检查下级段落是否消失（范围变为0），删除并波及前后
  removeEmptySegments(childTracks)

  // 4. 强制对齐：确保下级边界不超过上级边界
  enforceBoundaryAlignment(trackType)
}

// 道路轨道：独立拖动
function handleRoadBoundaryDrag(
  trackType: 'roadNumber' | 'roadName',
  segmentId: string,
  newBoundaryIndex: number,
  isStart: boolean
) {
  // 只更新当前轨道，不影响其他轨道
  updateSegmentBoundary(trackType, segmentId, newBoundaryIndex, isStart)
}
```

### 编辑字段：级联清除

当用户修改上级字段的**中文值**发生变化时，提示是否清除下级字段：

```typescript
function handleFieldEdit(
  trackType: TrackType,
  segmentId: string,
  newValue: string,
  newValueEn: string,
  oldValue: string,
  oldValueEn: string
) {
  // 1. 更新当前段落
  updateSegmentValue(trackType, segmentId, newValue, newValueEn)

  // 2. 如果是行政区划轨道且中文值发生变化，级联清除下级
  if (trackType === 'province' || trackType === 'city') {
    const childTracks = trackType === 'province' ? ['city', 'district'] : ['district']
    const hasChineseChange = oldValue !== newValue

    if (hasChineseChange) {
      // 仅当中文值变化时提示
      ElMessageBox.confirm(
        `修改${getTrackLabel(trackType)}后，下级字段将被清除。是否继续？`,
        '确认清除',
        { confirmButtonText: '继续', cancelButtonText: '取消' }
      ).then(() => {
        childTracks.forEach(childType => {
          clearChildSegments(childType, segmentId)
        })
      }).catch(() => {
        // 用户取消，回滚修改
        revertSegmentValue(trackType, segmentId, oldValue, oldValueEn)
      })
    }
  }

  // 3. 记录历史
  recordHistory('edit', `编辑${getTrackLabel(trackType)}`)
}
```

**关键规则**：
- 仅当**中文值**发生变化时才提示清除
- 英文值变化不触发级联清除
- 用户取消则回滚当前修改
- 确认后清除下级所有字段的中英文值（留空壳）

### 双击编辑对话框

```typescript
function openEditDialog(trackType: TrackType, segment: TrackSegment) {
  const hasEnglish = TRACK_DEFINITIONS[trackType].hasEnglish

  showDialog({
    title: `编辑${getTrackLabel(trackType)}`,
    fields: hasEnglish ? [
      { label: '中文', value: segment.value, key: 'value' },
      { label: '英文', value: segment.valueEn, key: 'valueEn' }
    ] : [
      { label: '编号', value: segment.value, key: 'value' }
    ],
    onSave: (newValues) => handleFieldEdit(trackType, segment.id, newValues.value, newValues.valueEn)
  })
}
```

### 自动分段算法

初始化时自动将连续相同值的点合并为段落：

```typescript
function autoSegmentByTrack(points: TrackPoint[], trackType: TrackType): TrackSegment[] {
  const segments: TrackSegment[] = []
  let currentSegment: Omit<TrackSegment, 'id'> | null = null

  points.forEach((point, index) => {
    const value = getTrackValue(point, trackType)
    const valueEn = getTrackValueEn(point, trackType)

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
        valueEn
      }
    }
  })

  if (currentSegment) {
    segments.push({ ...currentSegment, id: generateId() })
  }

  return segments
}
```

---

## 5. 撤销重做与持久化

### EditHistory - 历史记录

```typescript
interface EditHistory {
  id: string
  timestamp: number
  action: 'edit' | 'resize' | 'split' | 'merge'
  description: string
  before: {
    tracks: TrackTimeline[]    // 操作前的完整轨道状态
    selectedSegmentId: string | null
  }
  after: {
    tracks: TrackTimeline[]    // 操作后的完整轨道状态
    selectedSegmentId: string | null
  }
}
```

### EditHistoryManager - 历史管理器

```typescript
class EditHistoryManager {
  private readonly MAX_HISTORY = 50
  private readonly STORAGE_KEY_PREFIX = 'geo-editor-history-'

  // 记录操作
  recordAction(
    action: EditHistory['action'],
    description: string,
    before: TrackTimeline[],
    after: TrackTimeline[]
  ): void {
    const historyItem: EditHistory = {
      id: generateId(),
      timestamp: Date.now(),
      action,
      description,
      before: { tracks: before, selectedSegmentId: state.selectedSegmentId },
      after: { tracks: after, selectedSegmentId: state.selectedSegmentId }
    }

    // 如果在历史中间进行了新操作，删除当前位置之后的所有记录
    if (state.historyIndex < state.history.length - 1) {
      state.history = state.history.slice(0, state.historyIndex + 1)
    }

    state.history.push(historyItem)
    state.historyIndex = state.history.length - 1

    // 限制历史数量
    if (state.history.length > this.MAX_HISTORY) {
      state.history.shift()
      state.historyIndex--
    }

    // 持久化到 LocalStorage
    this.persist()
  }

  // 撤销
  undo(): boolean {
    if (!this.canUndo()) return false
    state.historyIndex--
    this.restoreState(state.history[state.historyIndex].before)
    return true
  }

  // 重做
  redo(): boolean {
    if (!this.canRedo()) return false
    state.historyIndex++
    this.restoreState(state.history[state.historyIndex].after)
    return true
  }

  // 持久化
  private persist(): void {
    const data = {
      history: state.history,
      historyIndex: state.historyIndex,
      trackId: state.trackId,
      savedAt: Date.now()
    }
    localStorage.setItem(
      this.STORAGE_KEY_PREFIX + state.trackId,
      JSON.stringify(data)
    )
  }

  // 恢复会话
  restoreSession(trackId: number): boolean {
    const key = this.STORAGE_KEY_PREFIX + trackId
    const data = localStorage.getItem(key)
    if (!data) return false

    const parsed = JSON.parse(data)
    state.history = parsed.history
    state.historyIndex = parsed.historyIndex
    return true
  }
}
```

### 本地自动保存 + 离页提示

```typescript
// 每次编辑后自动保存到 LocalStorage
function autoSaveToLocal(): void {
  historyManager.recordAction(...)
  state.hasUnsavedChanges = true
}

// 离页提示
onBeforeRouteLeave((to, from, next) => {
  if (state.hasUnsavedChanges) {
    ElMessageBox.confirm(
      '有未保存的更改，要保存到服务器吗？',
      '提示',
      {
        confirmButtonText: '保存',
        cancelButtonText: '放弃',
        distinguishCancelAndClose: true
      }
    ).then(() => {
      saveToServer().then(() => next())
    }).catch((action) => {
      if (action === 'cancel') next()  // 放弃更改
    })
  } else {
    next()
  }
})
```

---

## 6. 后端 API 设计

### 端点定义

```python
# 获取轨迹编辑数据（包含点列表和初始段落）
GET /api/tracks/{track_id}/geo-editor

# 保存段落更新
PUT /api/tracks/{track_id}/geo-segments
```

### Pydantic Schemas

```python
class GeoSegmentUpdate(BaseModel):
    """单个段落的更新数据"""
    track_type: Literal['province', 'city', 'district', 'road_number', 'road_name']
    start_index: int
    end_index: int
    value: str | None = None
    value_en: str | None = None


class GeoSegmentsUpdateRequest(BaseModel):
    """批量更新请求"""
    segments: list[GeoSegmentUpdate]

    @model_validator(mode='after')
    def validate_segments(self):
        # 验证索引范围有效
        # 验证行政区划的层级约束
        return self


class GeoEditorDataResponse(BaseModel):
    """编辑器初始化数据"""
    track_id: int
    points: list['TrackPointGeoData']
    total_duration: int  # 毫秒


class TrackPointGeoData(BaseModel):
    """轨迹点数据（仅包含编辑所需字段）"""
    point_index: int
    time: datetime
    latitude: float
    longitude: float
    province: str | None
    city: str | None
    district: str | None
    province_en: str | None
    city_en: str | None
    district_en: str | None
    road_number: str | None
    road_name: str | None
    road_name_en: str | None
```

---

## 7. 入口点设计

### 轨迹详情页编辑对话框

在轨迹详情页（`TrackDetail.vue`）的编辑对话框中，坐标系选项下方新增"编辑地理信息"按钮：

```vue
<!-- EditTrackDialog.vue -->
<el-form-item label="坐标系">
  <el-radio-group v-model="editForm.coordSystem">
    <el-radio value="wgs84">WGS84</el-radio>
    <el-radio value="gcj02">GCJ02</el-radio>
    <el-radio value="bd09">BD09</el-radio>
  </el-radio-group>
</el-form-item>

<el-form-item>
  <el-button type="primary" @click="openGeoEditor">
    编辑地理信息
  </el-button>
</el-form-item>
```

点击后打开地理信息编辑器页面（`/track/:id/geo-editor`）。

---

## 8. 文件清单

### 前端新增文件

```
frontend/src/
├── views/
│   └── GeoEditor.vue                 # 主页面
├── components/geo-editor/
│   ├── TimelineTracks.vue             # 时间轴轨道组件
│   ├── TrackTimeline.vue              # 单个轨道组件
│   ├── SegmentBlock.vue               # 段落块组件
│   ├── SegmentEditDialog.vue          # 段落编辑对话框
│   ├── GeoChartPanel.vue              # 图表面板
│   ├── TimePointer.vue                # 指针组件
│   └── PointerAttributes.vue          # 指针旁属性卡片
├── stores/
│   └── geoEditor.ts                   # Pinia Store
├── utils/
│   └── editHistoryManager.ts          # 历史记录管理器
└── api/
    └── geoEditor.ts                   # API 客户端
```

### 前端修改文件

```
frontend/src/
├── views/
│   └── TrackDetail.vue                # 添加"编辑地理信息"按钮
├── router/
│   └── index.ts                       # 添加 /track/:id/geo-editor 路由
└── components/
    └── EditTrackDialog.vue            # 添加入口按钮
```

### 后端新增文件

```
backend/app/
├── api/
│   └── geo_editor.py                  # API 路由
├── schemas/
│   └── geo_editor.py                  # Pydantic schemas
└── services/
    └── geo_editor_service.py          # 业务逻辑
```

---

## 9. 关键设计决策总结

| 决策点 | 选择 |
|--------|------|
| 布局方式 | 水平时间轴，5轨道（省/地/县/道路编号/道路名称） |
| 刻度单位 | 时间（默认）/ 时长 / 点索引 |
| x轴坐标 | 始终按时长比例计算 |
| 编辑粒度 | 双击段落只编辑该轨道字段 |
| 层级约束 | 行政区划联动拖动，道路轨道独立 |
| 修改上级 | 级联清除下级字段 |
| 边界对齐 | 系统强制对齐 |
| 撤销重做 | 每次保存算一次操作，LocalStorage 持久化 |
| 离页保存 | 本地自动保存，离开时提示保存到服务器 |
| 三向联动 | 地图/图表/时间轴双向联动，共享水平滚动 |

---

**设计文档版本**: 1.0
