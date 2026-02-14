# 轨迹地理信息在线编辑功能设计文档

**创建日期**: 2025-02-02
**分支**: feature/geo-editor
**状态**: 设计中

---

## 1. 功能概述

新增一个**轨迹地理信息在线编辑功能**，用户可以在时间轴界面编辑轨迹点的行政区划（省/市/区）、道路编号、道路名称及其英文字段。编辑后的数据用于生成实况覆盖层。

### 核心问题

- 轨迹点可能上万，大多数地理信息重复
- 需要高效的显示与编辑方案
- 支持撤销重做和历史记录

---

## 2. 整体架构

### 系统架构

```
前端组件结构：
GeoEditor.vue (主页面)
├── GeoTimeline.vue (时间轴容器)
│   ├── TimelineTable.vue (表格时间轴)
│   └── TimelineRow.vue (行组件)
├── SharedMapPanel.vue (地图与图表面板)
├── SegmentEditDialog.vue (段落编辑对话框)
└── EditHistoryManager.ts (历史记录管理器)
```

### 核心数据流

```
用户操作 → EditHistoryManager 记录 → LocalStorage 持久化
                ↓
         GeoEditor 状态更新
                ↓
    时间轴/地图/图表 同步渲染
                ↓
         用户点击"保存"
                ↓
    PUT /api/tracks/:id/geo-segments
```

### 关键设计原则

1. **单向数据流**：所有状态通过 Pinia store 管理
2. **段落抽象**：将连续相同地理信息的点抽象为 `Segment`
3. **懒加载**：超长轨迹分批加载
4. **响应式同步**：时间轴与地图图表流畅同步

---

## 3. 核心数据结构

### GeoSegment - 地理信息段落

```typescript
interface GeoSegment {
  id: string                    // 唯一标识（前端生成）
  startPointIndex: number       // 起始点索引
  endPointIndex: number         // 结束点索引（包含）
  pointCount: number            // 点数量

  // 行政区划
  province: string | null
  city: string | null
  district: string | null
  provinceEn: string | null
  cityEn: string | null
  districtEn: string | null

  // 道路信息
  roadNumber: string | null
  roadName: string | null
  roadNameEn: string | null

  // UI 状态
  isExpanded?: boolean          // 是否展开
  isValid?: boolean             // 是否已填写完整信息
  isEdited?: boolean            // 是否被编辑过
}
```

### EditHistory - 编辑历史记录

```typescript
interface EditHistory {
  id: string
  timestamp: number
  action: 'edit' | 'split' | 'merge' | 'batch-update' | 'resize'
  description: string
  before: GeoSegment[]          // 操作前的状态快照
  after: GeoSegment[]           // 操作后的状态快照
  affectedSegmentIds: string[]  // 涉及的段落 ID
}
```

### GeoEditorState - 编辑器状态

```typescript
interface GeoEditorState {
  trackId: number
  points: TrackPoint[]
  segments: GeoSegment[]
  selectedSegmentId: string | null
  hoveredSegmentId: string | null

  // 历史记录
  history: EditHistory[]
  historyIndex: number          // 当前历史位置

  // UI 状态
  isSaving: boolean
  hasUnsavedChanges: boolean
  lastSavedAt: number | null
}
```

### 自动分段算法

初始化时自动将连续相同地理信息的点合并为段落：

```typescript
function autoSegment(points: TrackPoint[]): GeoSegment[] {
  const segments: GeoSegment[] = []
  let currentSegment: Omit<GeoSegment, 'id'> | null = null

  points.forEach((point, index) => {
    const geoKey = getGeoKey(point)

    if (currentSegment && geoKey === currentSegment.geoKey) {
      currentSegment.endPointIndex = index
      currentSegment.pointCount++
    } else {
      if (currentSegment) {
        segments.push({ ...currentSegment, id: generateId() })
      }
      currentSegment = createSegmentFromPoint(point, index)
    }
  })

  if (currentSegment) {
    segments.push({ ...currentSegment, id: generateId() })
  }

  return segments
}

function getGeoKey(point: TrackPoint): string {
  return JSON.stringify({
    p: point.province,
    c: point.city,
    d: point.district,
    rn: point.roadNumber,
    n: point.roadName
  })
}
```

---

## 4. UI 设计

### 桌面端布局

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Header: [返回] [主页] 轨迹名称          [撤销] [重做] [保存]                  │
├────────────────────────────┬──────────────────────────────────────────────────┤
│                            │  ┌────────────────────────────────────────────┐  │
│  ┌──────────────────────┐  │  │  时间轴 (滚动)                             │  │
│  │                      │  │  ├─────┬──────────┬──────────┬────────────┤  │
│  │                      │  │  │ #   │ 行政区划 │ 道路编号 │   道路名称  │  │
│  │        地图          │  │  ├─────┼──────────┼──────────┼────────────┤  │
│  │                      │  │  │ 1   │ — — —    │    —     │     —      │  │
│  │                      │  │  ├─────┼──────────┼──────────┼────────────┤  │
│  ├──────────────────────┤  │  │ 2   │ 河 郑 金  │   G4     │   京港澳   │  │
│  │        图表          │  │  │     │ 南 州 水  │          │            │  │
│  │                      │  │  │     │ 省 市 区  │          │   高速公路  │  │
│  │                      │  │  ├─────┼──────────┼──────────┼────────────┤  │
│  │                      │  │  │ 3   │ 北 北 朝  │   —     │   北四环   │  │
│  └──────────────────────┘  │  │     │ 京 京 阳  │          │            │  │
│                            │  └─────┴──────────┴──────────┴────────────┘  │
└────────────────────────────┴─────────────────────────────────────────────────┘
```

### 移动端布局

```
┌────────────────────────┐
│  Header + 工具栏        │
├────────────────────────┤
│  ┌──────────────────┐  │
│  │      地图        │  │
│  └──────────────────┘  │
├────────────────────────┤
│  ┌──────────────────┐  │
│  │      图表        │  │
│  └──────────────────┘  │
├────────────────────────┤
│  ┌────────────────────────────────────────┐
│  │  ▼ 行政区划 ▼  ▼ 道路编号 ▼  ▼ 道路名称 ▼  │  ← 可折叠标题
│  ├────────────────────────────────────────┤
│  │  [北京市] [朝阳区] [海淀区] [...]  →    │  ← 横向滚动
│  └────────────────────────────────────────┘
└────────────────────────┘
```

### 表格列定义

| 列 | 内容 | 编辑方式 |
|-----|------|---------|
| `#` | 段落序号 | 不可编辑 |
| `行政区划` | 省/市/区（三行显示） | 双击编辑对话框 |
| `道路编号` | 道路编号（如 G4） | 双击内联编辑 |
| `道路名称` | 道路名称（如京港澳高速） | 双击内联编辑 |

### 行状态样式

| 状态 | 样式 |
|------|------|
| 默认 | 正常显示 |
| 悬停 | 整行高亮，地图实时预览 |
| 选中 | 蓝色背景，地图锁定高亮 |
| 已编辑 | 左侧橙色圆点标记 |
| 无效数据 | 红色虚线边框 |

### 编辑交互

- **双击行政区划列** → 弹出完整编辑对话框
- **双击道路编号/名称** → 内联编辑
- **拖动行边界** → 调整段落点数范围
- **右键行** → 菜单（拆分/合并/应用到后续）

### 段落编辑对话框

```
┌─────────────────────────────┐
│  编辑段落地理信息            │
├─────────────────────────────┤
│  省级: [北京市_________]     │
│  地级: [___空___]            │
│  县级: [朝阳区_______]       │
├─────────────────────────────┤
│  道路编号: [G221_______]     │
│  道路名称: [京承高速__]      │
├─────────────────────────────┤
│  □ 显示英文字段              │
│  (展开后)                    │
│  Province EN: [Beijing____]  │
│  City EN: [____________]     │
│  ...                         │
├─────────────────────────────┤
│  [应用到后续相同段落]         │
│  [查找并替换]                │
├─────────────────────────────┤
│      [取消]        [保存]    │
└─────────────────────────────┘
```

---

## 5. 历史记录与撤销重做

### EditHistoryManager

```typescript
class EditHistoryManager {
  private state: GeoEditorState
  private readonly MAX_HISTORY = 50
  private readonly STORAGE_KEY = 'geo-editor-history'

  recordAction(
    action: EditAction,
    description: string,
    before: GeoSegment[],
    after: GeoSegment[]
  ): void { /* ... */ }

  undo(): boolean { /* ... */ }
  redo(): boolean { /* ... */ }
  canUndo(): boolean { /* ... */ }
  canRedo(): boolean { /* ... */ }

  private persist(): void { /* ... */ }
  restore(trackId: number): boolean { /* ... */ }
}
```

### 操作类型

| 操作 | Action | 描述示例 |
|------|--------|----------|
| 编辑段落 | `edit` | "编辑段落 #2：北京市 → 上海市" |
| 拆分段落 | `split` | "拆分段落 #3（点 100-150）" |
| 合并段落 | `merge` | "合并段落 #4 和 #5" |
| 调整边界 | `resize` | "调整段落 #1 边界（50→80点）" |
| 批量更新 | `batch` | "批量更新 3 个段落道路名称" |

### LocalStorage 清理策略

- 打开编辑器时清理超过 7 天的历史记录
- 保存到服务器后可清除本地历史
- 同一轨迹只保留最新一次编辑会话

---

## 6. 双向联动

### 联动事件流

```
时间轴              地图              图表
────────────────── ──────────────── ──────────────
hover:segment  ────→ highlight:segment ──→ highlight:range
click:segment   ────→ lock:segment

                                       hover:point  ────→ scroll:to
                  ←──────── highlight:segment  ←──────────
                  ←──────── highlight:range

                                       click:point   ────→ select:segment
```

### 核心联动逻辑

```typescript
// 时间轴悬停段落
function handleSegmentHover(segment: GeoSegment) {
  hoveredSegment.value = segment
  mapRef.value?.highlightSegment(
    segment.startPointIndex,
    segment.endPointIndex
  )
  chartRef.value?.highlightRange(
    segment.startPointIndex,
    segment.endPointIndex
  )
}

// 地图点击轨迹点
function handleMapPointClick(point: TrackPoint, index: number) {
  const segment = findSegmentByPointIndex(index)
  if (segment) {
    selectedSegment.value = segment
    timelineRef.value?.scrollToSegment(segment.id)
  }
}

// 图表悬停
function handleChartHover(dataIndex: number) {
  const point = points.value[dataIndex]
  if (point) {
    mapRef.value?.showPointTooltip(point)
    const segment = findSegmentByPointIndex(dataIndex)
    if (segment) {
      timelineRef.value?.highlightRow(segment.id)
    }
  }
}
```

---

## 7. 后端 API 设计

### 端点定义

```python
PUT /api/tracks/{track_id}/geo-segments
```

### Pydantic Schema

```python
class GeoSegmentUpdate(BaseModel):
    start_point_index: int
    end_point_index: int

    # 行政区划
    province: str | None = None
    city: str | None = None
    district: str | None = None
    province_en: str | None = None
    city_en: str | None = None
    district_en: str | None = None

    # 道路信息
    road_number: str | None = None
    road_name: str | None = None
    road_name_en: str | None = None

    @field_validator('province', 'city', 'district', 'road_number', 'road_name')
    @classmethod
    def empty_string_to_none(cls, v):
        return v if v else None


class GeoSegmentsUpdateRequest(BaseModel):
    segments: list[GeoSegmentUpdate]

    @model_validator(mode='after')
    def validate_segments(self):
        # 验证段落连续且不重叠
        sorted_segments = sorted(self.segments, key=lambda s: s.start_point_index)
        for i, seg in enumerate(sorted_segments):
            if seg.start_point_index > seg.end_point_index:
                raise ValueError(f"段落 {i} 起始索引大于结束索引")
            if i > 0 and sorted_segments[i-1].end_point_index >= seg.start_point_index:
                raise ValueError(f"段落 {i} 与前一段重叠")
        return self.segments


class GeoSegmentsUpdateResponse(BaseModel):
    updated_count: int
    track_id: int
    updated_at: datetime
```

### Service 层

```python
class GeoSegmentService:

    async def update_segments(
        self,
        db: Session,
        track: Track,
        segments: list[GeoSegmentUpdate],
        user_id: int
    ) -> GeoSegmentsUpdateResponse:
        """按段落批量更新轨迹点地理信息"""
        points = await self._get_points_by_track(db, track.id)
        point_map = {p.point_index: p for p in points}

        updated_count = 0

        for segment in segments:
            for idx in range(segment.start_point_index, segment.end_point_index + 1):
                if idx not in point_map:
                    continue

                point = point_map[idx]

                # 更新字段...
                point.updated_by = user_id
                point.updated_at = get_utc_now()
                updated_count += 1

        db.commit()

        # 更新轨迹统计标记
        track.has_area_info = any(p.province for p in points)
        track.has_road_info = any(p.road_number or p.road_name for p in points)
        track.updated_by = user_id
        track.updated_at = get_utc_now()
        db.commit()

        return GeoSegmentsUpdateResponse(
            updated_count=updated_count,
            track_id=track.id,
            updated_at=get_utc_now()
        )
```

---

## 8. 路由与入口

### 路由配置

```typescript
{
  path: '/track/:id/geo-editor',
  name: 'GeoEditor',
  component: () => import('@/views/GeoEditor.vue'),
  meta: { requiresAuth: true }
}
```

### 入口按钮

在 `TrackDetail.vue` 的编辑对话框中添加：

```vue
<el-button @click="goToGeoEditor" type="primary">
  <el-icon><Edit /></el-icon>
  编辑地理信息
</el-button>
```

---

## 9. 英文字段处理

### 行政区划

- 中文修改后自动使用系统转写功能转换英文
- 用户可以手动覆盖

### 道路信息

- 完全由用户手动填写
- 系统不提供自动转写

---

## 10. 关键设计决策总结

| 决策点 | 选择 |
|--------|------|
| 编辑粒度 | 段落级别，自动分段+手动调整 |
| 保存策略 | 本地暂存+批量保存 |
| 英文处理 | 行政区划自动转写，道路手动填写 |
| 页面入口 | /track/:id/geo-editor 独立路由 |
| 联动交互 | 完整双向联动 |
| 历史存储 | LocalStorage，操作级别粒度 |
| 后端 API | 按段落更新 |

---

## 11. 文件清单

### 前端新增文件

```
frontend/src/
├── views/
│   └── GeoEditor.vue                 # 主页面
├── components/geo-editor/
│   ├── GeoTimeline.vue               # 时间轴容器
│   ├── TimelineTable.vue             # 表格时间轴
│   ├── TimelineRow.vue               # 行组件
│   └── SegmentEditDialog.vue         # 段落编辑对话框
├── stores/
│   └── geoEditor.ts                  # Pinia Store
├── utils/
│   └── editHistoryManager.ts         # 历史记录管理器
└── api/
    └── geoEditor.ts                  # API 客户端
```

### 后端新增文件

```
backend/app/
├── api/
│   └── geo_editor.py                 # API 路由
├── schemas/
│   └── geo_editor.py                 # Pydantic schemas
└── services/
    └── geo_segment_service.py        # 业务逻辑
```

---

**设计文档版本**: 1.0
