# 轨迹地理信息在线编辑功能实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**目标：** 构建一个在线编辑器，允许用户以段落为单位编辑轨迹点的行政区划（省/市/区）、道路编号和道路名称，支持撤销重做、双向联动，并将修改保存到后端。

**架构：** 前端使用 Vue 3 + Pinia 管理状态，时间轴与地图/图表双向联动，LocalStorage 持久化编辑历史；后端提供批量更新轨迹点地理信息的 API。

**技术栈：** Vue 3 (Composition API), Pinia, Element Plus, ECharts, FastAPI, SQLAlchemy, Pydantic

---

## 目录

1. [后端 API 开发](#task-1-backend-api)
2. [前端类型定义与 API 客户端](#task-2-frontend-types)
3. [Pinia Store](#task-3-pinia-store)
4. [历史记录管理器](#task-4-history-manager)
5. [主页面组件](#task-5-main-page)
6. [时间轴组件](#task-6-timeline)
7. [段落编辑对话框](#task-7-edit-dialog)
8. [路由配置与入口](#task-8-routing)

---

<a name="task-1-backend-api"></a>
## Task 1: 后端 Pydantic Schema

**Files:**
- Create: `backend/app/schemas/geo_editor.py`

**Step 1: 创建 Schema 文件**

创建 `backend/app/schemas/geo_editor.py`：

```python
"""
地理编辑器相关的 Pydantic schemas
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, model_validator


class GeoSegmentUpdate(BaseModel):
    """单个地理信息段落的更新"""
    start_point_index: int = Field(..., ge=0, description="起始点索引")
    end_point_index: int = Field(..., ge=0, description="结束点索引（包含）")

    # 行政区划
    province: Optional[str] = Field(None, max_length=50, description="省份")
    city: Optional[str] = Field(None, max_length=50, description="城市")
    district: Optional[str] = Field(None, max_length=50, description="区县")
    province_en: Optional[str] = Field(None, max_length=100, description="省份英文")
    city_en: Optional[str] = Field(None, max_length=100, description="城市英文")
    district_en: Optional[str] = Field(None, max_length=100, description="区县英文")

    # 道路信息
    road_number: Optional[str] = Field(None, max_length=50, description="道路编号")
    road_name: Optional[str] = Field(None, max_length=200, description="道路名称")
    road_name_en: Optional[str] = Field(None, max_length=200, description="道路名称英文")

    @field_validator('province', 'city', 'district', 'province_en', 'city_en', 'district_en', 'road_number', 'road_name', 'road_name_en')
    @classmethod
    def empty_string_to_none(cls, v: Optional[str]) -> Optional[str]:
        """将空字符串转换为 None"""
        if v is not None and v.strip() == '':
            return None
        return v

    @model_validator(mode='after')
    def validate_indices(self) -> 'GeoSegmentUpdate':
        """验证索引范围"""
        if self.start_point_index > self.end_point_index:
            raise ValueError(f"起始索引 ({self.start_point_index}) 不能大于结束索引 ({self.end_point_index})")
        return self


class GeoSegmentsUpdateRequest(BaseModel):
    """批量更新地理信息段落的请求"""
    segments: List[GeoSegmentUpdate] = Field(..., min_items=1, max_items=1000, description="段落列表")

    @model_validator(mode='after')
    def validate_segments(self) -> 'GeoSegmentsUpdateRequest':
        """验证段落连续且不重叠"""
        if not self.segments:
            return self

        # 按起始索引排序
        sorted_segments = sorted(self.segments, key=lambda s: s.start_point_index)

        for i, seg in enumerate(sorted_segments):
            # 检查索引范围
            if seg.start_point_index > seg.end_point_index:
                raise ValueError(f"段落 {i + 1} 的起始索引大于结束索引")

            # 检查重叠
            if i > 0 and sorted_segments[i - 1].end_point_index >= seg.start_point_index:
                raise ValueError(
                    f"段落 {i + 1} 与前一段落重叠（前一段结束于 {sorted_segments[i - 1].end_point_index}，"
                    f"本段开始于 {seg.start_point_index}）"
                )

        return self


class GeoSegmentsUpdateResponse(BaseModel):
    """批量更新地理信息段落的响应"""
    updated_count: int = Field(..., description="更新的轨迹点数量")
    track_id: int = Field(..., description="轨迹ID")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True
```

**Step 2: 运行测试验证**

运行: `cd backend && python -c "from app.schemas.geo_editor import GeoSegmentUpdate; print('Schema import OK')"`
Expected: `Schema import OK`

**Step 3: 提交**

```bash
git add backend/app/schemas/geo_editor.py
git commit -m "feat(geo-editor): add Pydantic schemas for geo segment updates"
```

---

## Task 2: 后端 Service 层

**Files:**
- Create: `backend/app/services/geo_segment_service.py`

**Step 1: 创建 Service 文件**

创建 `backend/app/services/geo_segment_service.py`：

```python
"""
地理信息段落编辑服务
"""
import logging
from typing import List
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track, TrackPoint
from app.schemas.geo_editor import GeoSegmentUpdate, GeoSegmentsUpdateResponse
from app.models.base import get_utc_now

logger = logging.getLogger(__name__)


class GeoSegmentService:
    """地理信息段落服务"""

    async def update_segments(
        self,
        db: AsyncSession,
        track: Track,
        segments: List[GeoSegmentUpdate],
        user_id: int
    ) -> GeoSegmentsUpdateResponse:
        """
        按段落批量更新轨迹点地理信息

        Args:
            db: 数据库会话
            track: 轨迹对象
            segments: 段落更新列表
            user_id: 当前用户ID

        Returns:
            更新结果
        """
        # 获取轨迹的所有点，按 point_index 索引
        stmt = select(TrackPoint).where(
            TrackPoint.track_id == track.id,
            TrackPoint.is_valid == True
        )
        result = await db.execute(stmt)
        points = result.scalars().all()

        # 创建点索引映射
        point_map = {p.point_index: p for p in points}

        updated_count = 0

        # 遍历每个段落进行更新
        for segment in segments:
            for idx in range(segment.start_point_index, segment.end_point_index + 1):
                if idx not in point_map:
                    continue

                point = point_map[idx]

                # 更新行政区划
                if segment.province is not None:
                    point.province = segment.province
                if segment.city is not None:
                    point.city = segment.city
                if segment.district is not None:
                    point.district = segment.district
                if segment.province_en is not None:
                    point.province_en = segment.province_en
                if segment.city_en is not None:
                    point.city_en = segment.city_en
                if segment.district_en is not None:
                    point.district_en = segment.district_en

                # 更新道路信息
                if segment.road_number is not None:
                    point.road_number = segment.road_number
                if segment.road_name is not None:
                    point.road_name = segment.road_name
                if segment.road_name_en is not None:
                    point.road_name_en = segment.road_name_en

                point.updated_by = user_id
                point.updated_at = get_utc_now()
                updated_count += 1

        # 提交更改
        await db.commit()

        # 更新轨迹的标记字段
        has_area = any(p.province for p in points)
        has_road = any(p.road_number or p.road_name for p in points)

        if track.has_area_info != has_area or track.has_road_info != has_road:
            track.has_area_info = has_area
            track.has_road_info = has_road
            track.updated_by = user_id
            track.updated_at = get_utc_now()
            await db.commit()

        logger.info(
            f"Updated {updated_count} points for track {track.id} "
            f"(has_area: {has_area}, has_road: {has_road})"
        )

        return GeoSegmentsUpdateResponse(
            updated_count=updated_count,
            track_id=track.id,
            updated_at=get_utc_now()
        )


# 单例实例
geo_segment_service = GeoSegmentService()
```

**Step 2: 提交**

```bash
git add backend/app/services/geo_segment_service.py
git commit -m "feat(geo-editor): add GeoSegmentService for batch updates"
```

---

## Task 3: 后端 API 路由

**Files:**
- Create: `backend/app/api/geo_editor.py`
- Modify: `backend/app/main.py:229`

**Step 1: 创建 API 路由文件**

创建 `backend/app/api/geo_editor.py`：

```python
"""
地理编辑器相关 API 路由
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.track import Track
from app.schemas.geo_editor import (
    GeoSegmentsUpdateRequest,
    GeoSegmentsUpdateResponse,
)
from app.services.geo_segment_service import geo_segment_service

router = APIRouter(prefix="/geo-editor", tags=["地理编辑器"])
logger = logging.getLogger(__name__)


@router.put("/tracks/{track_id}/geo-segments", response_model=GeoSegmentsUpdateResponse)
async def update_geo_segments(
    track_id: int,
    request: GeoSegmentsUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    批量更新轨迹的地理信息段落

    - **track_id**: 轨迹ID
    - **segments**: 段落更新列表，每个段落包含起始/结束索引和要更新的字段

    返回更新的点数量和更新时间
    """
    # 查询轨迹并验证权限
    stmt = select(Track).where(
        Track.id == track_id,
        Track.is_valid == True
    )
    result = await db.execute(stmt)
    track = result.scalar_one_or_none()

    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="轨迹不存在"
        )

    if track.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限修改此轨迹"
        )

    # 执行更新
    try:
        response = await geo_segment_service.update_segments(
            db=db,
            track=track,
            segments=request.segments,
            user_id=current_user.id
        )
        return response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating geo segments: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新地理信息失败"
        )
```

**Step 2: 在 main.py 中注册路由**

修改 `backend/app/main.py` 第 229 行后添加：

```python
from app.api import geo_editor  # 添加导入

app.include_router(geo_editor.router, prefix=settings.API_V1_PREFIX)  # 添加路由
```

**Step 3: 测试 API**

运行: `cd backend && python -c "from app.api.geo_editor import router; print(f'Router registered: {router.prefix}')"`
Expected: `Router registered: /geo-editor`

**Step 4: 提交**

```bash
git add backend/app/api/geo_editor.py backend/app/main.py
git commit -m "feat(geo-editor): add API endpoint for geo segment updates"
```

---

## Task 4: 前端类型定义

**Files:**
- Modify: `frontend/src/api/track.ts`

**Step 1: 添加地理编辑器类型**

在 `frontend/src/api/track.ts` 文件末尾添加：

```typescript
// ==================== 地理编辑器类型 ====================

export interface GeoSegment {
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

export interface GeoSegmentUpdate {
  start_point_index: number
  end_point_index: number
  province?: string | null
  city?: string | null
  district?: string | null
  province_en?: string | null
  city_en?: string | null
  district_en?: string | null
  road_number?: string | null
  road_name?: string | null
  road_name_en?: string | null
}

export interface GeoSegmentsUpdateRequest {
  segments: GeoSegmentUpdate[]
}

export interface GeoSegmentsUpdateResponse {
  updated_count: number
  track_id: number
  updated_at: string
}

export interface EditHistory {
  id: string
  timestamp: number
  action: 'edit' | 'split' | 'merge' | 'batch-update' | 'resize'
  description: string
  before: GeoSegment[]
  after: GeoSegment[]
  affectedSegmentIds: string[]
}
```

**Step 2: 提交**

```bash
git add frontend/src/api/track.ts
git commit -m "feat(geo-editor): add TypeScript types for geo editor"
```

---

## Task 5: 前端 API 客户端

**Files:**
- Create: `frontend/src/api/geoEditor.ts`

**Step 1: 创建 API 客户端**

创建 `frontend/src/api/geoEditor.ts`：

```typescript
import { http } from './request'
import type {
  GeoSegmentsUpdateRequest,
  GeoSegmentsUpdateResponse
} from './track'

/**
 * 更新轨迹的地理信息段落
 */
export async function updateGeoSegments(
  trackId: number,
  request: GeoSegmentsUpdateRequest
): Promise<GeoSegmentsUpdateResponse> {
  return http.put(`/geo-editor/tracks/${trackId}/geo-segments`, request)
}
```

**Step 2: 提交**

```bash
git add frontend/src/api/geoEditor.ts
git commit -m "feat(geo-editor): add API client for geo segment updates"
```

---

## Task 6: 历史记录管理器

**Files:**
- Create: `frontend/src/utils/editHistoryManager.ts`

**Step 1: 创建历史记录管理器**

创建 `frontend/src/utils/editHistoryManager.ts`：

```typescript
import type { GeoSegment, EditHistory } from '@/api/track'

const STORAGE_KEY = 'geo-editor-history'
const MAX_HISTORY = 50

/**
 * 编辑历史管理器
 */
export class EditHistoryManager {
  private history: EditHistory[] = []
  private historyIndex: number = -1
  private trackId: number | null = null

  /**
   * 初始化编辑会话
   */
  init(trackId: number): void {
    this.trackId = trackId
    this.loadFromStorage()
  }

  /**
   * 记录操作
   */
  recordAction(
    action: EditHistory['action'],
    description: string,
    before: GeoSegment[],
    after: GeoSegment[],
    affectedSegmentIds: string[]
  ): void {
    const entry: EditHistory = {
      id: this.generateId(),
      timestamp: Date.now(),
      action,
      description,
      before: this.deepClone(before),
      after: this.deepClone(after),
      affectedSegmentIds
    }

    // 如果当前不在历史末尾，删除后续记录
    if (this.historyIndex < this.history.length - 1) {
      this.history = this.history.slice(0, this.historyIndex + 1)
    }

    this.history.push(entry)

    // 限制历史长度
    if (this.history.length > MAX_HISTORY) {
      this.history.shift()
    } else {
      this.historyIndex++
    }

    this.persist()
  }

  /**
   * 撤销
   */
  undo(): GeoSegment[] | null {
    if (!this.canUndo()) return null

    this.historyIndex--
    const state = this.history[this.historyIndex].before
    this.persist()
    return this.deepClone(state)
  }

  /**
   * 重做
   */
  redo(): GeoSegment[] | null {
    if (!this.canRedo()) return null

    this.historyIndex++
    const state = this.history[this.historyIndex].after
    this.persist()
    return this.deepClone(state)
  }

  /**
   * 是否可以撤销
   */
  canUndo(): boolean {
    return this.historyIndex >= 0
  }

  /**
   * 是否可以重做
   */
  canRedo(): boolean {
    return this.historyIndex < this.history.length - 1
  }

  /**
   * 清除历史
   */
  clear(): void {
    this.history = []
    this.historyIndex = -1
    this.persist()
  }

  /**
   * 获取历史记录列表
   */
  getHistory(): EditHistory[] {
    return [...this.history]
  }

  /**
   * 从 LocalStorage 加载
   */
  private loadFromStorage(): void {
    try {
      const data = localStorage.getItem(STORAGE_KEY)
      if (!data) return

      const parsed = JSON.parse(data)
      const trackHistory = parsed[this.trackId ?? '']

      if (trackHistory) {
        this.history = trackHistory.history || []
        this.historyIndex = trackHistory.index || -1
      }
    } catch (e) {
      console.error('Failed to load edit history:', e)
    }
  }

  /**
   * 持久化到 LocalStorage
   */
  private persist(): void {
    try {
      const data = localStorage.getItem(STORAGE_KEY)
      const parsed: Record<string, { history: EditHistory[], index: number }> = data ? JSON.parse(data) : {}

      // 清理超过7天的旧记录
      const weekAgo = Date.now() - 7 * 24 * 60 * 60 * 1000
      for (const key in parsed) {
        const lastTimestamp = parsed[key].history[parsed[key].history.length - 1]?.timestamp || 0
        if (lastTimestamp < weekAgo) {
          delete parsed[key]
        }
      }

      if (this.trackId) {
        parsed[this.trackId] = {
          history: this.history,
          index: this.historyIndex
        }
      }

      localStorage.setItem(STORAGE_KEY, JSON.stringify(parsed))
    } catch (e) {
      console.error('Failed to persist edit history:', e)
    }
  }

  /**
   * 深度克隆
   */
  private deepClone<T>(obj: T): T {
    return JSON.parse(JSON.stringify(obj))
  }

  /**
   * 生成唯一ID
   */
  private generateId(): string {
    return `hist-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
  }
}

// 单例实例
export const editHistoryManager = new EditHistoryManager()
```

**Step 2: 提交**

```bash
git add frontend/src/utils/editHistoryManager.ts
git commit -m "feat(geo-editor): add EditHistoryManager for undo/redo"
```

---

## Task 7: Pinia Store

**Files:**
- Create: `frontend/src/stores/geoEditor.ts`

**Step 1: 创建 Pinia Store**

创建 `frontend/src/stores/geoEditor.ts`：

```typescript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Ref } from 'vue'
import type { GeoSegment, TrackPoint } from '@/api/track'
import { editHistoryManager } from '@/utils/editHistoryManager'

export const useGeoEditorStore = defineStore('geoEditor', () => {
  // State
  const trackId = ref<number | null>(null)
  const points = ref<TrackPoint[]>([])
  const segments = ref<GeoSegment[]>([])
  const selectedSegmentId = ref<string | null>(null)
  const hoveredSegmentId = ref<string | null>(null)
  const isSaving = ref(false)
  const lastSavedAt = ref<number | null>(null)

  // Getters
  const hasUnsavedChanges = computed(() => {
    return segments.value.some(seg => seg.isEdited)
  })

  const canUndo = computed(() => editHistoryManager.canUndo())
  const canRedo = computed(() => editHistoryManager.canRedo())

  // Actions
  function init(trackIdValue: number, pointsValue: TrackPoint[]) {
    trackId.value = trackIdValue
    points.value = pointsValue
    segments.value = autoSegment(pointsValue)
    editHistoryManager.init(trackIdValue)
  }

  function autoSegment(pts: TrackPoint[]): GeoSegment[] {
    const result: GeoSegment[] = []
    let current: Omit<GeoSegment, 'id'> | null = null

    pts.forEach((point, index) => {
      const geoKey = getGeoKey(point)

      if (current && geoKey === current.geoKey) {
        current.endPointIndex = index
        current.pointCount++
      } else {
        if (current) {
          result.push({ ...current, id: generateId() })
        }
        current = createSegmentFromPoint(point, index)
      }
    })

    if (current) {
      result.push({ ...current, id: generateId() })
    }

    return result
  }

  function getGeoKey(point: TrackPoint): string {
    return JSON.stringify({
      p: point.province,
      c: point.city,
      d: point.district,
      rn: point.road_number,
      n: point.road_name
    })
  }

  function createSegmentFromPoint(point: TrackPoint, index: number): Omit<GeoSegment, 'id'> {
    return {
      startPointIndex: index,
      endPointIndex: index,
      pointCount: 1,
      province: point.province,
      city: point.city,
      district: point.district,
      provinceEn: point.province_en,
      cityEn: point.city_en,
      districtEn: point.district_en,
      roadNumber: point.road_number,
      roadName: point.road_name,
      roadNameEn: point.road_name_en,
      isValid: !!(point.province || point.road_number || point.road_name),
      isExpanded: false,
      isEdited: false
    }
  }

  function updateSegment(segmentId: string, updates: Partial<GeoSegment>) {
    const index = segments.value.findIndex(s => s.id === segmentId)
    if (index === -1) return

    const before = [...segments.value]

    segments.value[index] = {
      ...segments.value[index],
      ...updates,
      isEdited: true
    }

    const after = [...segments.value]
    editHistoryManager.recordAction(
      'edit',
      `编辑段落 ${index + 1}`,
      before,
      after,
      [segmentId]
    )
  }

  function undo() {
    const state = editHistoryManager.undo()
    if (state) {
      segments.value = state
    }
  }

  function redo() {
    const state = editHistoryManager.redo()
    if (state) {
      segments.value = state
    }
  }

  function setSelectedSegment(id: string | null) {
    selectedSegmentId.value = id
  }

  function setHoveredSegment(id: string | null) {
    hoveredSegmentId.value = id
  }

  function clearEditedFlags() {
    segments.value = segments.value.map(s => ({ ...s, isEdited: false }))
    lastSavedAt.value = Date.now()
  }

  function reset() {
    trackId.value = null
    points.value = []
    segments.value = []
    selectedSegmentId.value = null
    hoveredSegmentId.value = null
    isSaving.value = false
    lastSavedAt.value = null
    editHistoryManager.clear()
  }

  function generateId(): string {
    return `seg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
  }

  return {
    // State
    trackId,
    points,
    segments,
    selectedSegmentId,
    hoveredSegmentId,
    isSaving,
    lastSavedAt,

    // Getters
    hasUnsavedChanges,
    canUndo,
    canRedo,

    // Actions
    init,
    updateSegment,
    undo,
    redo,
    setSelectedSegment,
    setHoveredSegment,
    clearEditedFlags,
    reset
  }
})
```

**Step 2: 提交**

```bash
git add frontend/src/stores/geoEditor.ts
git commit -m "feat(geo-editor): add Pinia store for geo editor state"
```

---

## Task 8: 主页面组件 - 基础结构

**Files:**
- Create: `frontend/src/views/GeoEditor.vue`

**Step 1: 创建主页面组件**

创建 `frontend/src/views/GeoEditor.vue`：

```vue
<template>
  <div class="geo-editor-container">
    <el-header>
      <div class="header-left">
        <el-button @click="$router.back()" :icon="ArrowLeft" class="nav-btn" />
        <el-button @click="$router.push('/home')" :icon="HomeFilled" class="nav-btn home-nav-btn" />
        <h1>{{ track?.name || '地理信息编辑' }}</h1>
      </div>
      <div class="header-right">
        <el-button
          @click="handleUndo"
          :disabled="!canUndo"
          :icon="RefreshLeft"
        >
          撤销
        </el-button>
        <el-button
          @click="handleRedo"
          :disabled="!canRedo"
          :icon="RefreshRight"
        >
          重做
        </el-button>
        <el-button
          type="primary"
          @click="handleSave"
          :loading="isSaving"
          :disabled="!hasUnsavedChanges"
          :icon="Check"
        >
          保存
        </el-button>
      </div>
    </el-header>

    <el-main class="main">
      <div v-if="loading" class="loading-container">
        <el-skeleton :rows="5" animated />
      </div>

      <div v-else-if="error" class="error-container">
        <el-alert type="error" :title="error" :closable="false" />
      </div>

      <div v-else class="editor-content">
        <!-- 左侧：时间轴 -->
        <div class="timeline-panel">
          <GeoTimeline
            :segments="segments"
            :selected-segment-id="selectedSegmentId"
            :hovered-segment-id="hoveredSegmentId"
            @select="setSelectedSegment"
            @hover="setHoveredSegment"
            @edit="handleEditSegment"
          />
        </div>

        <!-- 右侧：地图和图表 -->
        <div class="map-chart-panel">
          <SharedMapPanel
            :points="points"
            :segments="segments"
            :selected-segment-id="selectedSegmentId"
            :hovered-segment-id="hoveredSegmentId"
            @point-click="handlePointClick"
          />
        </div>
      </div>
    </el-main>

    <!-- 段落编辑对话框 -->
    <SegmentEditDialog
      v-model="editDialogVisible"
      :segment="editingSegment"
      @save="handleDialogSave"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, HomeFilled, RefreshLeft, RefreshRight, Check } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useGeoEditorStore } from '@/stores/geoEditor'
import { geoApi } from '@/api/track'
import { updateGeoSegments } from '@/api/geoEditor'
import type { GeoSegment } from '@/api/track'
import GeoTimeline from '@/components/geo-editor/GeoTimeline.vue'
import SharedMapPanel from '@/components/geo-editor/SharedMapPanel.vue'
import SegmentEditDialog from '@/components/geo-editor/SegmentEditDialog.vue'

const route = useRoute()
const router = useRouter()
const geoEditorStore = useGeoEditorStore()

const trackId = computed(() => parseInt(route.params.id as string))
const loading = ref(true)
const error = ref<string | null>(null)
const track = ref<any>(null)

// 对话框状态
const editDialogVisible = ref(false)
const editingSegment = ref<GeoSegment | null>(null)

// Store 映射
const points = computed(() => geoEditorStore.points)
const segments = computed(() => geoEditorStore.segments)
const selectedSegmentId = computed(() => geoEditorStore.selectedSegmentId)
const hoveredSegmentId = computed(() => geoEditorStore.hoveredSegmentId)
const isSaving = computed(() => geoEditorStore.isSaving)
const canUndo = computed(() => geoEditorStore.canUndo)
const canRedo = computed(() => geoEditorStore.canRedo)
const hasUnsavedChanges = computed(() => geoEditorStore.hasUnsavedChanges)

// 加载轨迹数据
async function loadTrack() {
  loading.value = true
  error.value = null

  try {
    track.value = await geoApi.getTrack(trackId.value)
    const trackPoints = await geoApi.getTrackPoints(trackId.value)

    geoEditorStore.init(trackId.value, trackPoints)
  } catch (e: any) {
    error.value = e.message || '加载轨迹失败'
  } finally {
    loading.value = false
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

// 保存
async function handleSave() {
  if (!hasUnsavedChanges.value) return

  isSaving.value = true

  try {
    const updateData = segments.value
      .filter(s => s.isEdited)
      .map(s => ({
        start_point_index: s.startPointIndex,
        end_point_index: s.endPointIndex,
        province: s.province,
        city: s.city,
        district: s.district,
        province_en: s.provinceEn,
        city_en: s.cityEn,
        district_en: s.districtEn,
        road_number: s.roadNumber,
        road_name: s.roadName,
        road_name_en: s.roadNameEn
      }))

    await updateGeoSegments(trackId.value, { segments: updateData })

    geoEditorStore.clearEditedFlags()
    ElMessage.success('保存成功')
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    isSaving.value = false
  }
}

// 选择段落
function setSelectedSegment(id: string | null) {
  geoEditorStore.setSelectedSegment(id)
}

// 悬停段落
function setHoveredSegment(id: string | null) {
  geoEditorStore.setHoveredSegment(id)
}

// 编辑段落
function handleEditSegment(segment: GeoSegment) {
  editingSegment.value = { ...segment }
  editDialogVisible.value = true
}

// 对话框保存
function handleDialogSave(updatedSegment: GeoSegment) {
  geoEditorStore.updateSegment(updatedSegment.id, updatedSegment)
  editDialogVisible.value = false
}

// 地图点点击
function handlePointClick(pointIndex: number) {
  const segment = segments.value.find(
    s => pointIndex >= s.startPointIndex && pointIndex <= s.endPointIndex
  )
  if (segment) {
    setSelectedSegment(segment.id)
  }
}

// 离开前确认
async function handleBeforeLeave() {
  if (hasUnsavedChanges.value) {
    try {
      await ElMessageBox.confirm(
        '您有未保存的更改，确定要离开吗？',
        '确认',
        { type: 'warning' }
      )
    } catch {
      return false
    }
  }
  geoEditorStore.reset()
  return true
}

onMounted(() => {
  loadTrack()
})

onUnmounted(() => {
  geoEditorStore.reset()
})
</script>

<style scoped>
.geo-editor-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-left h1 {
  font-size: 18px;
  margin: 0;
}

.header-right {
  display: flex;
  gap: 8px;
}

.main {
  flex: 1;
  overflow: hidden;
  padding: 20px;
}

.loading-container,
.error-container {
  padding: 40px;
}

.editor-content {
  display: flex;
  gap: 20px;
  height: 100%;
}

.timeline-panel {
  flex: 0 0 500px;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--el-border-color);
  padding-right: 20px;
}

.map-chart-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

@media (max-width: 1366px) {
  .editor-content {
    flex-direction: column;
  }

  .timeline-panel {
    flex: none;
    height: 40vh;
    border-right: none;
    border-bottom: 1px solid var(--el-border-color);
    padding-right: 0;
    padding-bottom: 20px;
  }
}
</style>
```

**Step 2: 提交**

```bash
git add frontend/src/views/GeoEditor.vue
git commit -m "feat(geo-editor): add main GeoEditor page component"
```

---

## Task 9: 时间轴组件

**Files:**
- Create: `frontend/src/components/geo-editor/GeoTimeline.vue`
- Create: `frontend/src/components/geo-editor/TimelineTable.vue`

**Step 1: 创建时间轴容器组件**

创建 `frontend/src/components/geo-editor/GeoTimeline.vue`：

```vue
<template>
  <div class="geo-timeline">
    <div class="timeline-header">
      <h3>地理信息段落</h3>
      <el-tag type="info">{{ segments.length }} 个段落</el-tag>
    </div>

    <el-scrollbar class="timeline-scroll">
      <TimelineTable
        :segments="segments"
        :selected-segment-id="selectedSegmentId"
        :hovered-segment-id="hoveredSegmentId"
        @select="$emit('select', $event)"
        @hover="$emit('hover', $event)"
        @edit="$emit('edit', $event)"
      />
    </el-scrollbar>
  </div>
</template>

<script setup lang="ts">
import type { GeoSegment } from '@/api/track'
import TimelineTable from './TimelineTable.vue'

defineProps<{
  segments: GeoSegment[]
  selectedSegmentId: string | null
  hoveredSegmentId: string | null
}>()

defineEmits<{
  select: [id: string | null]
  hover: [id: string | null]
  edit: [segment: GeoSegment]
}>()
</script>

<style scoped>
.geo-timeline {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid var(--el-border-color);
  margin-bottom: 12px;
}

.timeline-header h3 {
  margin: 0;
  font-size: 16px;
}

.timeline-scroll {
  flex: 1;
}
</style>
```

**Step 2: 创建表格组件**

创建 `frontend/src/components/geo-editor/TimelineTable.vue`：

```vue
<template>
  <el-table
    :data="segments"
    :row-class-name="getRowClassName"
    @row-click="handleRowClick"
    @row-mouseenter="handleRowMouseEnter"
    @row-mouseleave="handleRowMouseLeave"
    class="timeline-table"
  >
    <el-table-column type="index" label="#" width="50" />

    <el-table-column label="行政区划" min-width="150">
      <template #default="{ row }">
        <div class="division-cell" @dblclick="handleEdit(row)">
          <div v-if="row.province">{{ row.province }}</div>
          <div v-if="row.city">{{ row.city }}</div>
          <div v-if="row.district">{{ row.district }}</div>
          <div v-if="!row.province && !row.city && !row.district" class="empty-text">—</div>
        </div>
      </template>
    </el-table-column>

    <el-table-column label="道路编号" min-width="100">
      <template #default="{ row }">
        <div class="editable-cell" @dblclick="handleEdit(row)">
          {{ row.roadNumber || '—' }}
        </div>
      </template>
    </el-table-column>

    <el-table-column label="道路名称" min-width="150">
      <template #default="{ row }">
        <div class="editable-cell" @dblclick="handleEdit(row)">
          {{ row.roadName || '—' }}
        </div>
      </template>
    </el-table-column>

    <el-table-column label="点数" width="80" align="center">
      <template #default="{ row }">
        {{ row.pointCount }}
      </template>
    </el-table-column>

    <el-table-column label="范围" width="120">
      <template #default="{ row }">
        {{ row.startPointIndex }} - {{ row.endPointIndex }}
      </template>
    </el-table-column>

    <el-table-column width="40">
      <template #default="{ row }">
        <span v-if="row.isEdited" class="edited-indicator" />
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import type { GeoSegment } from '@/api/track'

const props = defineProps<{
  segments: GeoSegment[]
  selectedSegmentId: string | null
  hoveredSegmentId: string | null
}>()

const emit = defineEmits<{
  select: [id: string | null]
  hover: [id: string | null]
  edit: [segment: GeoSegment]
}>()

function getRowClassName({ row }: { row: GeoSegment }) {
  const classes: string[] = []

  if (row.id === props.selectedSegmentId) {
    classes.push('selected-row')
  }

  if (row.id === props.hoveredSegmentId) {
    classes.push('hovered-row')
  }

  if (!row.isValid) {
    classes.push('invalid-row')
  }

  return classes.join(' ')
}

function handleRowClick(row: GeoSegment) {
  emit('select', row.id === props.selectedSegmentId ? null : row.id)
}

function handleRowMouseEnter(row: GeoSegment) {
  emit('hover', row.id)
}

function handleRowMouseLeave() {
  emit('hover', null)
}

function handleEdit(row: GeoSegment) {
  emit('edit', row)
}
</script>

<style scoped>
.timeline-table {
  border: none;
}

.timeline-table :deep(.el-table__body-wrapper) {
  scrollbar-width: thin;
}

.timeline-table :deep(.el-table__row) {
  cursor: pointer;
}

.timeline-table :deep(.selected-row) {
  background-color: var(--el-color-primary-light-9) !important;
}

.timeline-table :deep(.hovered-row) {
  background-color: var(--el-fill-color-light) !important;
}

.timeline-table :deep(.invalid-row) {
  border-left: 3px solid var(--el-color-danger);
}

.division-cell,
.editable-cell {
  padding: 4px 0;
  line-height: 1.5;
}

.empty-text {
  color: var(--el-text-color-placeholder);
}

.edited-indicator {
  display: inline-block;
  width: 8px;
  height: 8px;
  background-color: var(--el-color-warning);
  border-radius: 50%;
}
</style>
```

**Step 3: 提交**

```bash
git add frontend/src/components/geo-editor/GeoTimeline.vue frontend/src/components/geo-editor/TimelineTable.vue
git commit -m "feat(geo-editor): add timeline components"
```

---

## Task 10: 共享地图面板组件

**Files:**
- Create: `frontend/src/components/geo-editor/SharedMapPanel.vue`

**Step 1: 创建共享地图面板组件**

创建 `frontend/src/components/geo-editor/SharedMapPanel.vue`：

```vue
<template>
  <div class="shared-map-panel">
    <div ref="mapContainerRef" class="map-container">
      <UniversalMap
        ref="mapRef"
        :points="points"
        :mode="'editor'"
        :highlight-segment="currentSegment"
        @point-click="handlePointClick"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import UniversalMap from '@/components/map/UniversalMap.vue'
import type { TrackPoint, GeoSegment } from '@/api/track'

const props = defineProps<{
  points: TrackPoint[]
  segments: GeoSegment[]
  selectedSegmentId: string | null
  hoveredSegmentId: string | null
}>()

const emit = defineEmits<{
  pointClick: [pointIndex: number]
}>()

const mapRef = ref<InstanceType<typeof UniversalMap> | null>(null)
const mapContainerRef = ref<HTMLElement | null>(null)

const currentSegment = computed(() => {
  const id = props.selectedSegmentId || props.hoveredSegmentId
  return props.segments.find(s => s.id === id) || null
})

function handlePointClick(point: TrackPoint, index: number) {
  emit('pointClick', index)
}
</script>

<style scoped>
.shared-map-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.map-container {
  flex: 1;
  min-height: 300px;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--el-border-color);
}
</style>
```

**Step 2: 提交**

```bash
git add frontend/src/components/geo-editor/SharedMapPanel.vue
git commit -m "feat(geo-editor): add SharedMapPanel component"
```

---

## Task 11: 段落编辑对话框

**Files:**
- Create: `frontend/src/components/geo-editor/SegmentEditDialog.vue`

**Step 1: 创建段落编辑对话框**

创建 `frontend/src/components/geo-editor/SegmentEditDialog.vue`：

```vue
<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    title="编辑段落地理信息"
    :width="isMobile ? '95%' : '500px'"
    :close-on-click-modal="false"
  >
    <el-form :model="form" label-width="100px" class="edit-form">
      <!-- 行政区划 -->
      <el-divider content-position="left">行政区划</el-divider>

      <el-form-item label="省份">
        <el-input v-model="form.province" placeholder="如：北京市" />
      </el-form-item>

      <el-form-item label="城市">
        <el-input v-model="form.city" placeholder="如：朝阳区" />
      </el-form-item>

      <el-form-item label="区县">
        <el-input v-model="form.district" placeholder="如：建国路" />
      </el-form-item>

      <!-- 道路信息 -->
      <el-divider content-position="left">道路信息</el-divider>

      <el-form-item label="道路编号">
        <el-input v-model="form.roadNumber" placeholder="如：G2" />
      </el-form-item>

      <el-form-item label="道路名称">
        <el-input v-model="form.roadName" placeholder="如：京沪高速" />
      </el-form-item>

      <!-- 英文字段 -->
      <div class="expand-section">
        <el-button
          text
          :icon="showEnglish ? ArrowUp : ArrowDown"
          @click="showEnglish = !showEnglish"
        >
          {{ showEnglish ? '收起' : '展开' }}英文字段
        </el-button>
      </div>

      <template v-if="showEnglish">
        <el-form-item label="省份 EN">
          <el-input v-model="form.provinceEn" placeholder="Province" />
        </el-form-item>

        <el-form-item label="城市 EN">
          <el-input v-model="form.cityEn" placeholder="City" />
        </el-form-item>

        <el-form-item label="区县 EN">
          <el-input v-model="form.districtEn" placeholder="District" />
        </el-form-item>

        <el-form-item label="道路 EN">
          <el-input v-model="form.roadNameEn" placeholder="Road Name" />
        </el-form-item>
      </template>
    </el-form>

    <template #footer>
      <el-button @click="handleCancel">取消</el-button>
      <el-button type="primary" @click="handleSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { ArrowDown, ArrowUp } from '@element-plus/icons-vue'
import type { GeoSegment } from '@/api/track'

const props = defineProps<{
  modelValue: boolean
  segment: GeoSegment | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  save: [segment: GeoSegment]
}>()

const showEnglish = ref(false)
const isMobile = computed(() => window.innerWidth <= 1366)

const form = ref<{
  province: string | null
  city: string | null
  district: string | null
  provinceEn: string | null
  cityEn: string | null
  districtEn: string | null
  roadNumber: string | null
  roadName: string | null
  roadNameEn: string | null
}>({
  province: null,
  city: null,
  district: null,
  provinceEn: null,
  cityEn: null,
  districtEn: null,
  roadNumber: null,
  roadName: null,
  roadNameEn: null
})

watch(() => props.segment, (seg) => {
  if (seg) {
    form.value = {
      province: seg.province,
      city: seg.city,
      district: seg.district,
      provinceEn: seg.provinceEn,
      cityEn: seg.cityEn,
      districtEn: seg.districtEn,
      roadNumber: seg.roadNumber,
      roadName: seg.roadName,
      roadNameEn: seg.roadNameEn
    }
  }
}, { immediate: true })

function handleCancel() {
  emit('update:modelValue', false)
}

function handleSave() {
  if (!props.segment) return

  const updated: GeoSegment = {
    ...props.segment,
    province: form.value.province?.trim() || null,
    city: form.value.city?.trim() || null,
    district: form.value.district?.trim() || null,
    provinceEn: form.value.provinceEn?.trim() || null,
    cityEn: form.value.cityEn?.trim() || null,
    districtEn: form.value.districtEn?.trim() || null,
    roadNumber: form.value.roadNumber?.trim() || null,
    roadName: form.value.roadName?.trim() || null,
    roadNameEn: form.value.roadNameEn?.trim() || null,
    isValid: !!(form.value.province || form.value.roadNumber || form.value.roadName),
    isEdited: true
  }

  emit('save', updated)
}
</script>

<style scoped>
.edit-form {
  padding: 10px 0;
}

.expand-section {
  text-align: center;
  margin: 10px 0;
}
</style>
```

**Step 2: 提交**

```bash
git add frontend/src/components/geo-editor/SegmentEditDialog.vue
git commit -m "feat(geo-editor): add SegmentEditDialog component"
```

---

## Task 12: 路由配置

**Files:**
- Modify: `frontend/src/router/index.ts:80`

**Step 1: 添加路由**

在 `frontend/src/router/index.ts` 的 routes 数组中，第 80 行后添加：

```typescript
{
  path: '/tracks/:id/geo-editor',
  name: 'GeoEditor',
  component: () => import('@/views/GeoEditor.vue'),
  meta: { requiresAuth: true },
},
```

**Step 2: 提交**

```bash
git add frontend/src/router/index.ts
git commit -m "feat(geo-editor): add route for geo editor page"
```

---

## Task 13: 轨迹详情页入口按钮

**Files:**
- Modify: `frontend/src/views/TrackDetail.vue:673`

**Step 1: 添加入口按钮**

在 `TrackDetail.vue` 的编辑对话框 footer 中（第 673-691 行），在"填充地理信息"按钮后添加：

```vue
<el-button
  type="success"
  @click="goToGeoEditor"
>
  <el-icon><MapLocation /></el-icon>
  编辑地理信息
</el-button>
```

同时在 script setup 部分添加导入和方法：

```typescript
import { MapLocation } from '@element-plus/icons-vue'  // 添加到导入

// 添加方法
function goToGeoEditor() {
  if (track.value) {
    router.push(`/tracks/${track.value.id}/geo-editor`)
  }
}
```

**Step 2: 提交**

```bash
git add frontend/src/views/TrackDetail.vue
git commit -m "feat(geo-editor): add entry button in TrackDetail page"
```

---

## Task 14: 地图组件编辑器模式支持

**Files:**
- Modify: `frontend/src/components/map/UniversalMap.vue`

**Step 1: 添加编辑器模式和高亮段落支持**

在 `UniversalMap.vue` 中添加 `mode` prop 和 `highlightSegment` prop：

```typescript
// 添加 props 定义
const props = defineProps<{
  // ... 现有 props
  mode?: 'home' | 'detail' | 'editor'  // 添加编辑器模式
  highlightSegment?: { startPointIndex: number; endPointIndex: number } | null  // 添加段落高亮
}>()
```

在地图渲染逻辑中处理段落高亮（具体实现参考现有 highlightSegment 逻辑）。

**Step 2: 提交**

```bash
git add frontend/src/components/map/UniversalMap.vue
git commit -m "feat(geo-editor): add editor mode to UniversalMap"
```

---

## 验证测试清单

完成所有任务后，按以下步骤验证功能：

### 后端验证

1. 启动后端服务：`cd backend && uvicorn app.main:app --reload`
2. 访问 API 文档：`http://localhost:8000/docs`
3. 确认 `PUT /api/geo-editor/tracks/{track_id}/geo-segments` 端点存在
4. 使用测试数据调用 API 验证功能

### 前端验证

1. 启动前端服务：`cd frontend && npm run dev`
2. 登录后进入任意轨迹详情页
3. 点击"编辑地理信息"按钮
4. 验证时间轴显示正确
5. 验证地图显示正确
6. 双击段落行，弹出编辑对话框
7. 修改地理信息，保存
8. 验证撤销/重做功能
9. 验证未保存离开提示

### 集成验证

1. 编辑地理信息后保存
2. 返回轨迹详情页
3. 验证地理信息已更新
4. 重新进入编辑器，验证数据正确加载

---

**计划版本**: 1.0
**创建日期**: 2025-02-02
**预计工作量**: 14 个任务，约 2-3 小时完成
