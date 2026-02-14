# 路径插值功能实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**目标:** 为 GPS 信号丢失区域（如隧道）添加轨迹插值功能，用户可通过钢笔工具绘制路径，系统自动生成插值点。

**架构:** 后端提供插值 API（使用三次 Bézier 曲线算法），前端提供钢笔工具对话框组件，支持独立手柄控制曲线形状。

**技术栈:**
- 后端: FastAPI, SQLAlchemy, Alembic
- 前端: Vue 3, TypeScript, Element Plus, Leaflet
- 算法: 三次 Bézier 曲线 + 弧长参数化

---

## Phase 1: 数据库迁移

### Task 1: 创建插值表迁移脚本

**文件:**
- 创建: `backend/alembic/versions/014_add_interpolations.py`

**Step 1: 创建迁移文件**

创建迁移文件，添加 `track_interpolations` 表和 `track_points` 表的扩展字段。

```python
"""add track_interpolations table and interpolated fields to track_points

Revision ID: 014_add_interpolations
Revises: 013_add_user_configs_and_share
Create Date: 2026-02-08

添加轨迹插值功能相关表结构。
兼容 SQLite / MySQL / PostgreSQL。
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '014_add_interpolations'
down_revision = '013_add_user_configs_and_share'
branch_labels = None
depends_on = None


def upgrade():
    """
    创建插值表并添加插值标记字段
    """
    # 创建 track_interpolations 表
    op.create_table(
        'track_interpolations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('is_valid', sa.Boolean(), nullable=False, server_default='1'),

        sa.Column('track_id', sa.Integer(), nullable=False, comment='关联轨迹ID'),
        sa.Column('start_point_index', sa.Integer(), nullable=False, comment='起点索引'),
        sa.Column('end_point_index', sa.Integer(), nullable=False, comment='终点索引'),
        sa.Column('path_geometry', sa.Text(), nullable=False, comment='控制点数据(JSON格式)'),
        sa.Column('interpolation_interval_seconds', sa.Integer(), nullable=False, server_default='1', comment='插值间隔(秒)'),
        sa.Column('point_count', sa.Integer(), nullable=False, comment='插入的点数'),
        sa.Column('algorithm', sa.String(length=50), nullable=False, server_default='cubic_bezier', comment='插值算法'),

        sa.PrimaryKeyConstraint('id')
    )

    # 创建索引
    op.create_index('ix_track_interpolations_track_id', 'track_interpolations', ['track_id'])
    op.create_index('ix_track_interpolations_is_valid', 'track_interpolations', ['is_valid'])

    # 为 track_points 表添加插值相关字段
    op.add_column('track_points', sa.Column('is_interpolated', sa.Boolean(), nullable=False, server_default='0', comment='是否为插值点'))
    op.add_column('track_points', sa.Column('interpolation_id', sa.Integer(), nullable=True, comment='关联的插值ID'))

    # 创建外键（SQLite 不支持外键，会忽略）
    try:
        op.create_foreign_key('fk_track_interpolations_track_id', 'track_interpolations', 'tracks', ['track_id'], ['id'])
        op.create_foreign_key('fk_track_points_interpolation_id', 'track_points', 'track_interpolations', ['interpolation_id'], ['id'])
    except Exception:
        # SQLite 不支持外键，忽略错误
        pass


def downgrade():
    """
    回滚迁移
    """
    # 删除外键
    try:
        op.drop_constraint('fk_track_points_interpolation_id', 'track_points', type_='foreignkey')
        op.drop_constraint('fk_track_interpolations_track_id', 'track_interpolations', type_='foreignkey')
    except Exception:
        pass

    # 删除字段
    op.drop_column('track_points', 'interpolation_id')
    op.drop_column('track_points', 'is_interpolated')

    # 删除索引
    op.drop_index('ix_track_interpolations_is_valid', 'track_interpolations')
    op.drop_index('ix_track_interpolations_track_id', 'track_interpolations')

    # 删除表
    op.drop_table('track_interpolations')
```

**Step 2: 运行迁移**

```bash
cd backend
alembic upgrade head
```

预期输出: `Running upgrade -> 014_add_interpolations`

**Step 3: 提交**

```bash
git add backend/alembic/versions/014_add_interpolations.py
git commit -m "feat: add track_interpolations table and interpolated fields"
```

---

## Phase 2: 后端数据模型

### Task 2: 创建插值模型

**文件:**
- 创建: `backend/app/models/interpolation.py`

**Step 1: 创建模型文件**

```python
"""
轨迹插值模型
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import AuditMixin


class TrackInterpolation(Base, AuditMixin):
    """轨迹插值配置表"""

    __tablename__ = "track_interpolations"

    id = Column(Integer, primary_key=True, index=True)
    track_id = Column(Integer, ForeignKey("tracks.id"), nullable=False, index=True)
    start_point_index = Column(Integer, nullable=False, comment="起点索引")
    end_point_index = Column(Integer, nullable=False, comment="终点索引")
    path_geometry = Column(Text, nullable=False, comment="控制点数据(JSON格式)")
    interpolation_interval_seconds = Column(Integer, nullable=False, default=1, comment="插值间隔(秒)")
    point_count = Column(Integer, nullable=False, comment="插入的点数")
    algorithm = Column(String(50), nullable=False, default="cubic_bezier", comment="插值算法")

    # 关系
    track = relationship("Track", back_populates="interpolations")
    interpolated_points = relationship(
        "TrackPoint",
        foreign_keys="TrackPoint.interpolation_id",
        back_populates="interpolation_source"
    )

    def __repr__(self):
        return f"<TrackInterpolation(id={self.id}, track_id={self.track_id}, points={self.point_count})>"
```

**Step 2: 更新 Track 模型添加关系**

**文件:** `backend/app/models/track.py`
**位置:** 在 `Track` 类的 `relationship` 部分添加

```python
# 在 Track 类中添加:
interpolations = relationship("TrackInterpolation", back_populates="track", cascade="all, delete-orphan")
```

**Step 3: 更新 TrackPoint 模型添加关系**

**文件:** `backend/app/models/track.py`
**位置:** 在 `TrackPoint` 类的 `relationship` 部分添加

```python
# 在 TrackPoint 类中添加:
interpolation_source = relationship("TrackInterpolation", foreign_keys=[interpolation_id])
```

**Step 4: 更新 models/__init__.py**

**文件:** `backend/app/models/__init__.py`
**位置:** 导入部分添加

```python
from app.models.interpolation import TrackInterpolation
```

**Step 5: 提交**

```bash
git add backend/app/models/
git commit -m "feat: add TrackInterpolation model"
```

---

## Phase 3: 后端 Schema

### Task 3: 创建插值 Schema

**文件:**
- 创建: `backend/app/schemas/interpolation.py`

**Step 1: 创建 Schema 文件**

```python
"""
轨迹插值相关的 Pydantic schemas
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class ControlPointHandle(BaseModel):
    """控制点手柄"""
    dx: float = Field(..., description="X 方向偏移量（经度）")
    dy: float = Field(..., description="Y 方向偏移量（纬度）")


class ControlPoint(BaseModel):
    """贝塞尔曲线控制点"""
    lng: float = Field(..., description="经度", ge=-180, le=180)
    lat: float = Field(..., description="纬度", ge=-90, le=90)
    in_handle: ControlPointHandle = Field(..., description="进入手柄")
    out_handle: ControlPointHandle = Field(..., description="离开手柄")
    handles_locked: bool = Field(default=True, description="手柄是否锁定")


class AvailableSegment(BaseModel):
    """可插值区段"""
    start_index: int
    end_index: int
    interval_seconds: float
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class InterpolatedPoint(BaseModel):
    """插值点数据"""
    point_index: int
    time: datetime
    latitude: float
    longitude: float
    latitude_gcj02: float
    longitude_gcj02: float
    latitude_bd09: float
    longitude_bd09: float
    speed: float
    course: float
    elevation: Optional[float] = None


class InterpolationCreateRequest(BaseModel):
    """创建插值请求"""
    start_point_index: int = Field(..., ge=0, description="起点索引")
    end_point_index: int = Field(..., ge=0, description="终点索引")
    control_points: List[ControlPoint] = Field(default_factory=list, description="控制点列表")
    interpolation_interval_seconds: float = Field(default=1.0, ge=0.1, le=60, description="插值间隔（秒）")
    algorithm: str = Field(default="cubic_bezier", description="插值算法类型")


class InterpolationUpdateRequest(BaseModel):
    """更新插值请求"""
    control_points: List[ControlPoint] = Field(..., description="新的控制点列表")
    interpolation_interval_seconds: Optional[float] = Field(None, ge=0.1, le=60, description="新的插值间隔")


class InterpolationResponse(BaseModel):
    """插值响应"""
    id: int
    track_id: int
    start_point_index: int
    end_point_index: int
    point_count: int
    control_points: List[ControlPoint]
    interpolation_interval_seconds: int
    algorithm: str
    created_at: datetime


class InterpolationPreviewRequest(BaseModel):
    """插值预览请求"""
    track_id: int
    start_point_index: int
    end_point_index: int
    control_points: List[ControlPoint] = Field(default_factory=list)
    interpolation_interval_seconds: float = Field(default=1.0, ge=0.1, le=60)


class InterpolationPreviewResponse(BaseModel):
    """插值预览响应"""
    points: List[InterpolatedPoint]
    total_count: int
    start_time: datetime
    end_time: datetime
```

**Step 2: 提交**

```bash
git add backend/app/schemas/interpolation.py
git commit -m "feat: add interpolation schemas"
```

---

## Phase 4: 后端服务层 - Bézier 曲线引擎

### Task 4: 创建 Bézier 曲线工具模块

**文件:**
- 创建: `backend/app/utils/bezier.py`

**Step 1: 创建 Bézier 曲线工具类**

```python
"""
三次 Bézier 曲线计算工具
用于轨迹插值
"""
import math
from typing import List, Tuple
from dataclasses import dataclass


@dataclass
class Point:
    """坐标点"""
    lng: float  # 经度
    lat: float  # 纬度


@dataclass
class BezierControlPoint(Point):
    """带手柄的贝塞尔控制点"""
    in_handle_dx: float = 0.0
    in_handle_dy: float = 0.0
    out_handle_dx: float = 0.0
    out_handle_dy: float = 0.0
    handles_locked: bool = True


def calculate_distance(p1: Point, p2: Point) -> float:
    """
    计算两点间的球面距离（米）
    使用 Haversine 公式
    """
    R = 6371000  # 地球半径（米）

    phi1 = math.radians(p1.lat)
    phi2 = math.radians(p2.lat)
    delta_phi = math.radians(p2.lat - p1.lat)
    delta_lambda = math.radians(p2.lng - p1.lng)

    a = (math.sin(delta_phi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) *
         math.sin(delta_lambda / 2) ** 2)

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def linear_interpolate(a: float, b: float, t: float) -> float:
    """线性插值"""
    return a + (b - a) * t


def normalize_angle(angle: float) -> float:
    """
    归一化角度到 [0, 360)
    处理角度插值时的跳变问题
    """
    angle = angle % 360
    if angle < 0:
        angle += 360
    return angle


def interpolate_angle(start: float, end: float, t: float) -> float:
    """
    角度线性插值（考虑 359° -> 1° 的情况）
    """
    start = start % 360
    end = end % 360

    diff = end - start
    if diff > 180:
        diff -= 360
    elif diff < -180:
        diff += 360

    result = start + diff * t
    return normalize_angle(result)


class CubicBezierSegment:
    """单段三次贝塞尔曲线"""

    def __init__(
        self,
        p0: Point,
        p1: Point,  # 控制点1 (out handle of p0)
        p2: Point,  # 控制点2 (in handle of p3)
        p3: Point
    ):
        self.p0 = p0
        self.p1 = p1
        self.p2 = p2
        self.p3 = p3

    def evaluate(self, t: float) -> Point:
        """
        计算贝塞尔曲线在参数 t 处的点
        B(t) = (1-t)³P₀ + 3(1-t)²tP₁ + 3(1-t)t²P₂ + t³P₃
        """
        mt = 1 - t
        mt2 = mt * mt
        mt3 = mt2 * mt
        t2 = t * t
        t3 = t2 * t

        lng = (mt3 * self.p0.lng +
               3 * mt2 * t * self.p1.lng +
               3 * mt * t2 * self.p2.lng +
               t3 * self.p3.lng)

        lat = (mt3 * self.p0.lat +
               3 * mt2 * t * self.p1.lat +
               3 * mt * t2 * self.p2.lat +
               t3 * self.p3.lat)

        return Point(lng, lat)

    def calculate_length(self, steps: int = 20) -> float:
        """
        计算曲线长度（数值积分）
        """
        length = 0.0
        prev = self.evaluate(0)

        for i in range(1, steps + 1):
            t = i / steps
            curr = self.evaluate(t)
            length += calculate_distance(prev, curr)
            prev = curr

        return length

    def get_point_at_length(self, target_length: float, steps: int = 100) -> Point:
        """
        根据弧长获取点（弧长参数化）
        """
        total_length = self.calculate_length(steps)

        if target_length <= 0:
            return self.p0
        if target_length >= total_length:
            return self.p3

        # 二分查找或线性搜索
        accumulated = 0.0
        prev = self.evaluate(0)

        for i in range(1, steps + 1):
            t = i / steps
            curr = self.evaluate(t)
            segment_length = calculate_distance(prev, curr)

            if accumulated + segment_length >= target_length:
                # 在这段内，线性插值
                remaining = target_length - accumulated
                local_t = remaining / segment_length if segment_length > 0 else 0
                local_t_param = (i - 1 + local_t) / steps
                return self.evaluate(local_t_param)

            accumulated += segment_length
            prev = curr

        return self.p3


class CubicBezierCurve:
    """多段三次贝塞尔曲线"""

    def __init__(self, points: List[Point]):
        """
        初始化曲线
        points: 包含起止点和中间控制点的列表
        """
        self.points = points
        self.segments: List[CubicBezierSegment] = []
        self.segment_lengths: List[float] = []
        self.total_length = 0.0

        self._build_segments()

    def _build_segments(self):
        """构建曲线段"""
        self.segments = []
        self.segment_lengths = []
        self.total_length = 0.0

        for i in range(len(self.points) - 1):
            # 简化版本：直接连接相邻点作为控制点
            # 实际使用时，需要从 ControlPoint 数据结构中获取手柄位置
            segment = CubicBezierSegment(
                self.points[i],
                self.points[i],  # 这里需要替换为实际的 out handle 位置
                self.points[i + 1],  # 这里需要替换为实际的 in handle 位置
                self.points[i + 1]
            )
            length = segment.calculate_length()
            self.segments.append(segment)
            self.segment_lengths.append(length)
            self.total_length += length

    def get_total_length(self) -> float:
        """获取曲线总长度"""
        return self.total_length

    def get_point_at_length(self, target_length: float) -> Point:
        """
        根据弧长获取点
        """
        if target_length <= 0:
            return self.points[0]
        if target_length >= self.total_length:
            return self.points[-1]

        # 找到所在的段
        accumulated = 0.0
        for i, (segment, seg_length) in enumerate(zip(self.segments, self.segment_lengths)):
            if accumulated + seg_length >= target_length:
                remaining = target_length - accumulated
                return segment.get_point_at_length(remaining)
            accumulated += seg_length

        return self.points[-1]

    def generate_points(self, count: int) -> List[Point]:
        """
        生成均匀分布的点
        """
        if count <= 0:
            return []
        if count == 1:
            return [self.points[0]]

        points = []
        step = self.total_length / (count - 1)

        for i in range(count):
            points.append(self.get_point_at_length(i * step))

        return points
```

**Step 2: 提交**

```bash
git add backend/app/utils/bezier.py
git commit -m "feat: add cubic bezier curve utility"
```

---

## Phase 5: 后端服务层 - 插值服务

### Task 5: 创建插值服务

**文件:**
- 创建: `backend/app/services/interpolation_service.py`

**Step 1: 创建插值服务文件**

```python
"""
轨迹插值服务
"""
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track, TrackPoint
from app.models.interpolation import TrackInterpolation
from app.schemas.interpolation import (
    InterpolationCreateRequest,
    InterpolationUpdateRequest,
    InterpolationResponse,
    AvailableSegment,
    InterpolatedPoint,
    InterpolationPreviewRequest,
    InterpolationPreviewResponse
)
from app.utils.bezier import (
    Point, CubicBezierCurve,
    calculate_distance, linear_interpolate, interpolate_angle
)
from app.services.coord_transform import CoordTransform


class InterpolationService:
    """插值服务"""

    def __init__(self):
        self.coord_transform = CoordTransform()

    async def get_available_segments(
        self,
        db: AsyncSession,
        track_id: int,
        min_interval_seconds: float,
        ignore_interpolated: bool = True
    ) -> List[AvailableSegment]:
        """
        获取可用于插值的区段

        Args:
            db: 数据库会话
            track_id: 轨迹ID
            min_interval_seconds: 最小间隔（秒）
            ignore_interpolated: 是否忽略已有插值的区段

        Returns:
            可用区段列表
        """
        # 获取轨迹的所有点（按索引排序）
        result = await db.execute(
            select(TrackPoint)
            .where(
                and_(
                    TrackPoint.track_id == track_id,
                    TrackPoint.is_valid == True,
                    TrackPoint.is_interpolated == False if ignore_interpolated else True
                )
            )
            .order_by(TrackPoint.point_index)
        )
        points = result.scalars().all()

        segments = []
        for i in range(len(points) - 1):
            curr, next_p = points[i], points[i + 1]

            # 计算时间差
            if curr.time and next_p.time:
                interval = (next_p.time - curr.time).total_seconds()
                if interval >= min_interval_seconds:
                    segments.append(AvailableSegment(
                        start_index=curr.point_index,
                        end_index=next_p.point_index,
                        interval_seconds=interval,
                        start_time=curr.time,
                        end_time=next_p.time
                    ))

        return segments

    async def preview_interpolation(
        self,
        db: AsyncSession,
        request: InterpolationPreviewRequest
    ) -> InterpolationPreviewResponse:
        """
        生成插值预览
        """
        # 获取起点和终点
        start_point_result = await db.execute(
            select(TrackPoint).where(
                and_(
                    TrackPoint.track_id == request.track_id,
                    TrackPoint.point_index == request.start_point_index
                )
            )
        )
        start_point = start_point_result.scalar_one_or_none()

        end_point_result = await db.execute(
            select(TrackPoint).where(
                and_(
                    TrackPoint.track_id == request.track_id,
                    TrackPoint.point_index == request.end_point_index
                )
            )
        )
        end_point = end_point_result.scalar_one_or_none()

        if not start_point or not end_point:
            raise ValueError("起点或终点不存在")

        # 生成插值点
        interpolated_points = self._generate_interpolated_points(
            start_point=start_point,
            end_point=end_point,
            control_points=request.control_points,
            interval_seconds=request.interpolation_interval_seconds
        )

        return InterpolationPreviewResponse(
            points=interpolated_points,
            total_count=len(interpolated_points),
            start_time=start_point.time,
            end_time=end_point.time
        )

    def _generate_interpolated_points(
        self,
        start_point: TrackPoint,
        end_point: TrackPoint,
        control_points: List,
        interval_seconds: float
    ) -> List[InterpolatedPoint]:
        """
        生成插值点
        """
        # 构建曲线点序列
        curve_points = [
            Point(start_point.longitude_wgs84, start_point.latitude_wgs84)
        ]

        # 添加控制点（带手柄）
        for cp in control_points:
            # 这里需要处理手柄偏移，暂时简化
            curve_points.append(Point(cp.lng, cp.lat))

        curve_points.append(Point(end_point.longitude_wgs84, end_point.latitude_wgs84))

        # 创建贝塞尔曲线
        curve = CubicBezierCurve(curve_points)

        # 计算时间差和点数
        time_diff = (end_point.time - start_point.time).total_seconds()
        point_count = int(time_diff / interval_seconds)

        # 生成曲线上的点
        curve_points_result = curve.generate_points(max(2, point_count + 2))

        # 生成插值点数据
        interpolated = []
        start_speed = start_point.speed or 0
        end_speed = end_point.speed or 0
        start_course = start_point.bearing or 0
        end_course = end_point.bearing or 0

        for i, point in enumerate(curve_points_result[1:-1], start=1):
            t = i / point_count if point_count > 0 else 0

            # 计算时间
            point_time = start_point.time + timedelta(seconds=i * interval_seconds)

            # 线性插值速度和航向
            speed = linear_interpolate(start_speed, end_speed, t)
            course = interpolate_angle(start_course, end_course, t)

            # 坐标转换
            lat_wgs, lng_wgs = point.lat, point.lng
            lat_gcj, lng_gcj = self.coord_transform.wgs2gcj(lat_wgs, lng_wgs)
            lat_bd, lng_bd = self.coord_transform.gcj2bd(lat_gcj, lng_gcj)

            interpolated.append(InterpolatedPoint(
                point_index=0,  # 稍后分配
                time=point_time,
                latitude=lat_wgs,
                longitude=lng_wgs,
                latitude_gcj02=lat_gcj,
                longitude_gcj02=lng_gcj,
                latitude_bd09=lat_bd,
                longitude_bd09=lng_bd,
                speed=speed,
                course=course,
                elevation=None  # 可以添加高程插值
            ))

        return interpolated

    async def create_interpolation(
        self,
        db: AsyncSession,
        track_id: int,
        request: InterpolationCreateRequest,
        user_id: int
    ) -> InterpolationResponse:
        """
        创建插值
        """
        # 1. 验证区段
        segments = await self.get_available_segments(
            db, track_id, min_interval_seconds=3.0
        )
        valid_segment = None
        for seg in segments:
            if seg.start_index == request.start_point_index and seg.end_index == request.end_point_index:
                valid_segment = seg
                break

        if not valid_segment:
            raise ValueError("所选区段不可用于插值")

        # 2. 生成插值预览
        preview_request = InterpolationPreviewRequest(
            track_id=track_id,
            start_point_index=request.start_point_index,
            end_point_index=request.end_point_index,
            control_points=request.control_points,
            interpolation_interval_seconds=request.interpolation_interval_seconds
        )
        preview = await self.preview_interpolation(db, preview_request)

        # 3. 创建插值记录
        import json
        interpolation = TrackInterpolation(
            track_id=track_id,
            start_point_index=request.start_point_index,
            end_point_index=request.end_point_index,
            path_geometry=json.dumps([cp.dict() for cp in request.control_points]),
            interpolation_interval_seconds=int(request.interpolation_interval_seconds),
            point_count=len(preview.points),
            algorithm=request.algorithm,
            created_by=user_id
        )
        db.add(interpolation)
        await db.flush()

        # 4. 插入插值点
        await self._insert_interpolated_points(
            db,
            track_id,
            interpolation.id,
            request.start_point_index,
            preview.points
        )

        await db.commit()
        await db.refresh(interpolation)

        return InterpolationResponse(
            id=interpolation.id,
            track_id=interpolation.track_id,
            start_point_index=interpolation.start_point_index,
            end_point_index=interpolation.end_point_index,
            point_count=interpolation.point_count,
            control_points=request.control_points,
            interpolation_interval_seconds=interpolation.interpolation_interval_seconds,
            algorithm=interpolation.algorithm,
            created_at=interpolation.created_at
        )

    async def _insert_interpolated_points(
        self,
        db: AsyncSession,
        track_id: int,
        interpolation_id: int,
        start_point_index: int,
        points: List[InterpolatedPoint]
    ):
        """
        插入插值点到数据库
        """
        # 更新后续点的索引
        await db.execute(
            select(TrackPoint)
            .where(
                and_(
                    TrackPoint.track_id == track_id,
                    TrackPoint.point_index > start_point_index
                )
            )
        )

        # 批量插入插值点
        new_index_start = start_point_index + 1
        for i, point_data in enumerate(points):
            track_point = TrackPoint(
                track_id=track_id,
                point_index=new_index_start + i,
                time=point_data.time,
                latitude_wgs84=point_data.latitude,
                longitude_wgs84=point_data.longitude,
                latitude_gcj02=point_data.latitude_gcj02,
                longitude_gcj02=point_data.longitude_gcj02,
                latitude_bd09=point_data.latitude_bd09,
                longitude_bd09=point_data.longitude_bd09,
                speed=point_data.speed,
                bearing=point_data.course,
                elevation=point_data.elevation,
                is_interpolated=True,
                interpolation_id=interpolation_id,
                # 其他字段设为 NULL
                province=None,
                city=None,
                district=None,
                road_name=None,
                road_number=None
            )
            db.add(track_point)

        await db.flush()
```

**Step 2: 创建服务实例**

**文件:** `backend/app/services/interpolation_service.py` (末尾添加)

```python
# 单例服务实例
interpolation_service = InterpolationService()
```

**Step 3: 提交**

```bash
git add backend/app/services/interpolation_service.py
git commit -m "feat: add interpolation service"
```

---

## Phase 6: 后端 API 路由

### Task 6: 创建插值 API 路由

**文件:**
- 创建: `backend/app/api/interpolation.py`

**Step 1: 创建 API 路由文件**

```python
"""
轨迹插值 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.schemas.interpolation import (
    InterpolationCreateRequest,
    InterpolationUpdateRequest,
    InterpolationResponse,
    InterpolationPreviewRequest,
    InterpolationPreviewResponse,
    AvailableSegment
)
from app.services.interpolation_service import interpolation_service

router = APIRouter(prefix="/interpolation", tags=["interpolation"])


@router.get("/tracks/{track_id}/available-segments")
async def get_available_segments(
    track_id: int,
    min_interval: float = 3.0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> list[AvailableSegment]:
    """
    获取轨迹的可插值区段列表

    Args:
        track_id: 轨迹ID
        min_interval: 最小间隔（秒）

    Returns:
        可用区段列表
    """
    segments = await interpolation_service.get_available_segments(
        db, track_id, min_interval
    )
    return segments


@router.post("/preview")
async def preview_interpolation(
    request: InterpolationPreviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> InterpolationPreviewResponse:
    """
    预览插值结果（不保存）
    """
    try:
        return await interpolation_service.preview_interpolation(db, request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tracks/{track_id}/interpolations")
async def create_interpolation(
    track_id: int,
    request: InterpolationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> InterpolationResponse:
    """
    创建插值配置并插入插值点
    """
    try:
        return await interpolation_service.create_interpolation(
            db, track_id, request, current_user.id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tracks/{track_id}/interpolations")
async def get_track_interpolations(
    track_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> list[InterpolationResponse]:
    """
    获取轨迹的所有插值配置
    """
    from app.models.interpolation import TrackInterpolation
    from sqlalchemy import select

    result = await db.execute(
        select(TrackInterpolation)
        .where(
            TrackInterpolation.track_id == track_id,
            TrackInterpolation.is_valid == True
        )
        .order_by(TrackInterpolation.created_at)
    )
    interpolations = result.scalars().all()

    import json
    responses = []
    for interp in interpolations:
        control_points = [
            eval(cp) for cp in json.loads(interp.path_geometry)
        ]
        responses.append(InterpolationResponse(
            id=interp.id,
            track_id=interp.track_id,
            start_point_index=interp.start_point_index,
            end_point_index=interp.end_point_index,
            point_count=interp.point_count,
            control_points=control_points,
            interpolation_interval_seconds=interp.interpolation_interval_seconds,
            algorithm=interp.algorithm,
            created_at=interp.created_at
        ))

    return responses


@router.delete("/interpolations/{interpolation_id}")
async def delete_interpolation(
    interpolation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除插值配置及关联的插值点
    """
    from app.models.interpolation import TrackInterpolation
    from sqlalchemy import select, update

    # 获取插值记录
    result = await db.execute(
        select(TrackInterpolation).where(
            TrackInterpolation.id == interpolation_id
        )
    )
    interpolation = result.scalar_one_or_none()

    if not interpolation:
        raise HTTPException(status_code=404, detail="插值记录不存在")

    # 软删除插值记录
    interpolation.is_valid = False

    # 清除关联插值点的标记
    await db.execute(
        update(TrackPoint)
        .where(TrackPoint.interpolation_id == interpolation_id)
        .values(is_interpolated=False, interpolation_id=None)
    )

    await db.commit()

    return {"message": "插值已删除"}
```

**Step 2: 注册路由**

**文件:** `backend/app/main.py`
**位置:** 导入部分添加

```python
from app.api import interpolation
```

**位置:** 路由注册部分添加

```python
app.include_router(interpolation.router, prefix=settings.API_V1_PREFIX)
```

**Step 3: 提交**

```bash
git add backend/app/api/interpolation.py backend/app/main.py
git commit -m "feat: add interpolation API routes"
```

---

## Phase 7: 前端 API 客户端

### Task 7: 创建前端插值 API

**文件:**
- 创建: `frontend/src/api/interpolation.ts`

**Step 1: 创建 API 客户端文件**

```typescript
import { http } from './request'

// 控制点手柄
export interface ControlPointHandle {
  dx: number
  dy: number
}

// 控制点
export interface ControlPoint {
  lng: number
  lat: number
  inHandle: ControlPointHandle
  outHandle: ControlPointHandle
  handlesLocked: boolean
}

// 可插值区段
export interface AvailableSegment {
  start_index: number
  end_index: number
  interval_seconds: number
  start_time: string | null
  end_time: string | null
}

// 插值点数据
export interface InterpolatedPoint {
  point_index: number
  time: string
  latitude: number
  longitude: number
  latitude_gcj02: number
  longitude_gcj02: number
  latitude_bd09: number
  longitude_bd09: number
  speed: number
  course: number
  elevation: number | null
}

// 创建请求
export interface InterpolationCreateRequest {
  start_point_index: number
  end_point_index: number
  control_points: ControlPoint[]
  interpolation_interval_seconds: number
  algorithm: string
}

// 预览请求
export interface InterpolationPreviewRequest {
  track_id: number
  start_point_index: number
  end_point_index: number
  control_points: ControlPoint[]
  interpolation_interval_seconds: number
}

// 插值响应
export interface InterpolationResponse {
  id: number
  track_id: number
  start_point_index: number
  end_point_index: number
  point_count: number
  control_points: ControlPoint[]
  interpolation_interval_seconds: number
  algorithm: string
  created_at: string
}

// API 方法
export const interpolationApi = {
  // 获取可插值区段
  getAvailableSegments(trackId: number, minInterval: number = 3.0): Promise<AvailableSegment[]> {
    return http.get(`/interpolation/tracks/${trackId}/available-segments`, {
      params: { min_interval: minInterval }
    })
  },

  // 预览插值
  preview(request: InterpolationPreviewRequest): Promise<{
    points: InterpolatedPoint[]
    total_count: number
    start_time: string
    end_time: string
  }> {
    return http.post('/interpolation/preview', request)
  },

  // 创建插值
  create(trackId: number, request: InterpolationCreateRequest): Promise<InterpolationResponse> {
    return http.post(`/interpolation/tracks/${trackId}/interpolations`, request)
  },

  // 获取轨迹的插值列表
  getTrackInterpolations(trackId: number): Promise<InterpolationResponse[]> {
    return http.get(`/interpolation/tracks/${trackId}/interpolations`)
  },

  // 删除插值
  delete(interpolationId: number): Promise<void> {
    return http.delete(`/interpolation/interpolations/${interpolationId}`)
  }
}
```

**Step 2: 提交**

```bash
git add frontend/src/api/interpolation.ts
git commit -m "feat: add interpolation API client"
```

---

## Phase 8: 前端 Bézier 曲线引擎

### Task 8: 创建前端 Bézier 曲线工具类

**文件:**
- 创建: `frontend/src/utils/bezierCurve.ts`

**Step 1: 创建 Bézier 曲线工具类**

```typescript
/**
 * 三次贝塞尔曲线工具类
 * 用于前端轨迹插值预览
 */

export interface Point {
  lng: number
  lat: number
}

export interface BezierControlPoint extends Point {
  inHandle: Point
  outHandle: Point
  handlesLocked: boolean
}

/**
 * 计算两点间的球面距离（米）
 */
function calculateDistance(p1: Point, p2: Point): number {
  const R = 6371000
  const φ1 = (p1.lat * Math.PI) / 180
  const φ2 = (p2.lat * Math.PI) / 180
  const Δφ = ((p2.lat - p1.lat) * Math.PI) / 180
  const Δλ = ((p2.lng - p1.lng) * Math.PI) / 180

  const a = Math.sin(Δφ / 2) ** 2 +
            Math.cos(φ1) * Math.cos(φ2) *
            Math.sin(Δλ / 2) ** 2

  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))

  return R * c
}

/**
 * 线性插值
 */
function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t
}

/**
 * 单段三次贝塞尔曲线
 */
class CubicBezierSegment {
  constructor(
    private p0: Point,
    private p1: Point,
    private p2: Point,
    private p3: Point
  ) {}

  /**
   * 计算贝塞尔曲线在参数 t 处的点
   */
  evaluate(t: number): Point {
    const mt = 1 - t
    const mt2 = mt * mt
    const mt3 = mt2 * mt
    const t2 = t * t
    const t3 = t2 * t

    return {
      lng: mt3 * this.p0.lng + 3 * mt2 * t * this.p1.lng + 3 * mt * t2 * this.p2.lng + t3 * this.p3.lng,
      lat: mt3 * this.p0.lat + 3 * mt2 * t * this.p1.lat + 3 * mt * t2 * this.p2.lat + t3 * this.p3.lat
    }
  }

  /**
   * 计算曲线长度（数值积分）
   */
  calculateLength(steps: number = 20): number {
    let length = 0
    let prev = this.evaluate(0)

    for (let i = 1; i <= steps; i++) {
      const curr = this.evaluate(i / steps)
      length += calculateDistance(prev, curr)
      prev = curr
    }

    return length
  }

  /**
   * 根据弧长获取点
   */
  getPointAtLength(targetLength: number, steps: number = 100): Point {
    const totalLength = this.calculateLength(steps)

    if (targetLength <= 0) return this.p0
    if (targetLength >= totalLength) return this.p3

    let accumulated = 0
    let prev = this.evaluate(0)

    for (let i = 1; i <= steps; i++) {
      const t = i / steps
      const curr = this.evaluate(t)
      const segmentLength = calculateDistance(prev, curr)

      if (accumulated + segmentLength >= targetLength) {
        const remaining = targetLength - accumulated
        const localT = segmentLength > 0 ? remaining / segmentLength : 0
        const localTParam = (i - 1 + localT) / steps
        return this.evaluate(localTParam)
      }

      accumulated += segmentLength
      prev = curr
    }

    return this.p3
  }
}

/**
 * 多段三次贝塞尔曲线
 */
export class CubicBezierCurve {
  private segments: CubicBezierSegment[] = []
  private segmentLengths: number[] = []
  private totalLength = 0

  constructor(points: Array<Point | BezierControlPoint>) {
    this._buildSegments(points)
  }

  /**
   * 构建曲线段
   */
  private _buildSegments(points: Array<Point | BezierControlPoint>) {
    this.segments = []
    this.segmentLengths = []
    this.totalLength = 0

    for (let i = 0; i < points.length - 1; i++) {
      const p0 = points[i]
      const p3 = points[i + 1]

      // 获取控制点手柄
      let p1: Point, p2: Point

      if ('outHandle' in p0) {
        const cp = p0 as BezierControlPoint
        p1 = {
          lng: p0.lng + cp.outHandle.lng,
          lat: p0.lat + cp.outHandle.lat
        }
      } else {
        // 端点没有手柄，使用自身位置
        p1 = { lng: p0.lng, lat: p0.lat }
      }

      if ('inHandle' in p3) {
        const cp = p3 as BezierControlPoint
        p2 = {
          lng: p3.lng + cp.inHandle.lng,
          lat: p3.lat + cp.inHandle.lat
        }
      } else {
        p2 = { lng: p3.lng, lat: p3.lat }
      }

      const segment = new CubicBezierSegment(
        { lng: p0.lng, lat: p0.lat },
        p1,
        p2,
        { lng: p3.lng, lat: p3.lat }
      )

      const length = segment.calculateLength()
      this.segments.push(segment)
      this.segmentLengths.push(length)
      this.totalLength += length
    }
  }

  /**
   * 获取曲线总长度
   */
  getTotalLength(): number {
    return this.totalLength
  }

  /**
   * 根据弧长获取点
   */
  getPointAtLength(targetLength: number): Point {
    if (targetLength <= 0) {
      return this.segments[0]?.evaluate(0) || { lng: 0, lat: 0 }
    }
    if (targetLength >= this.totalLength) {
      const lastSegment = this.segments[this.segments.length - 1]
      return lastSegment ? lastSegment.evaluate(1) : { lng: 0, lat: 0 }
    }

    let accumulated = 0
    for (let i = 0; i < this.segments.length; i++) {
      const segLength = this.segmentLengths[i]
      if (accumulated + segLength >= targetLength) {
        return this.segments[i].getPointAtLength(targetLength - accumulated)
      }
      accumulated += segLength
    }

    return { lng: 0, lat: 0 }
  }

  /**
   * 生成均匀分布的点
   */
  generatePoints(count: number): Point[] {
    if (count <= 0) return []
    if (count === 1) return [this.getPointAtLength(0)]

    const points: Point[] = []
    const step = this.totalLength / (count - 1)

    for (let i = 0; i < count; i++) {
      points.push(this.getPointAtLength(i * step))
    }

    return points
  }
}
```

**Step 2: 提交**

```bash
git add frontend/src/utils/bezierCurve.ts
git commit -m "feat: add frontend bezier curve utility"
```

---

## Phase 9: 前端钢笔工具地图组件

### Task 9: 创建钢笔工具地图组件

**文件:**
- 创建: `frontend/src/components/interpolation/PenToolMap.vue`

**Step 1: 创建组件文件**

```vue
<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import UniversalMap from '@/components/map/UniversalMap.vue'
import { CubicBezierCurve, type BezierControlPoint } from '@/utils/bezierCurve'
import { Lock, Unlock, Delete } from '@element-plus/icons-vue'

interface Props {
  trackId: number
  startPoint: { lng: number; lat: number; index: number; time: string }
  endPoint: { lng: number; lat: number; index: number; time: string }
  controlPoints: Array<{
    lng: number
    lat: number
    inHandle: { dx: number; dy: number }
    outHandle: { dx: number; dy: number }
    handlesLocked: boolean
  }>
  modelValue: boolean
}

interface Emits {
  (e: 'update:controlPoints', points: Props['controlPoints']): void
  (e: 'update:modelValue', value: boolean): void
  (e: 'preview', points: any[]): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// 状态
const mapRef = ref()
const selectedPointIndex = ref<number | null>(null)
const dragTarget = ref<'point' | 'handle' | null>(null)
const dragStartPosition = ref<{ lng: number; lat: number } | null>(null)
const handlesLocked = ref(true)

// 曲线实例
const curve = computed(() => {
  const points: Array<{ lng: number; lat: number }> = [
    { lng: props.startPoint.lng, lat: props.startPoint.lat },
    ...props.controlPoints.map(cp => ({ lng: cp.lng, lat: cp.lat })),
    { lng: props.endPoint.lng, lat: props.endPoint.lat }
  ]
  return new CubicBezierCurve(points)
})

// 预览点（用于显示）
const previewPoints = computed(() => {
  if (props.controlPoints.length === 0) {
    // 直线连接
    return [
      { lng: props.startPoint.lng, lat: props.startPoint.lat },
      { lng: props.endPoint.lng, lat: props.endPoint.lat }
    ]
  }
  return curve.value.generatePoints(50)
})

// 地图覆盖层
const mapOverlays = computed(() => {
  const overlays = []

  // 起点标记
  overlays.push({
    type: 'marker',
    position: [props.startPoint.lat, props.startPoint.lng],
    icon: {
      type: 'circle',
      radius: 6,
      fillColor: '#409eff',
      fillOpacity: 1,
      strokeColor: '#fff',
      strokeWeight: 2
    },
    label: 'A'
  })

  // 终点标记
  overlays.push({
    type: 'marker',
    position: [props.endPoint.lat, props.endPoint.lng],
    icon: {
      type: 'circle',
      radius: 6,
      fillColor: '#67c23a',
      fillOpacity: 1,
      strokeColor: '#fff',
      strokeWeight: 2
    },
    label: 'B'
  })

  // 控制点标记
  props.controlPoints.forEach((cp, index) => {
    const isSelected = index === selectedPointIndex.value
    overlays.push({
      type: 'marker',
      position: [cp.lat, cp.lng],
      icon: {
        type: 'circle',
        radius: isSelected ? 8 : 5,
        fillColor: isSelected ? '#e6a23c' : '#f56c6c',
        fillOpacity: 0.9,
        strokeColor: '#fff',
        strokeWeight: 2
      },
      label: String(index + 1)
    })
  })

  // 曲线路径
  if (previewPoints.value.length > 1) {
    overlays.push({
      type: 'polyline',
      positions: previewPoints.value.map(p => [p.lat, p.lng]),
      color: '#409eff',
      weight: 3,
      opacity: 0.7,
      dashArray: '5, 5'
    })
  }

  return overlays
})

// 添加控制点
function addControlPoint(lng: number, lat: number) {
  const newPoint = {
    lng,
    lat,
    inHandle: { dx: -0.001, dy: 0 },
    outHandle: { dx: 0.001, dy: 0 },
    handlesLocked: true
  }
  emit('update:controlPoints', [...props.controlPoints, newPoint])
  selectedPointIndex.value = props.controlPoints.length
}

// 更新控制点位置
function updateControlPoint(index: number, lng: number, lat: number) {
  const updated = [...props.controlPoints]
  updated[index] = { ...updated[index], lng, lat }
  emit('update:controlPoints', updated)
}

// 删除控制点
function deleteControlPoint(index: number) {
  const updated = props.controlPoints.filter((_, i) => i !== index)
  emit('update:controlPoints', updated)
  if (selectedPointIndex.value === index) {
    selectedPointIndex.value = null
  }
}

// 处理地图点击
function handleMapClick(event: any) {
  if (!props.modelValue) return

  const { lng, lat } = event

  // 检查是否点击了现有控制点
  const clickedIndex = findClickedPoint(lng, lat)
  if (clickedIndex !== null) {
    selectedPointIndex.value = clickedIndex
    return
  }

  // 添加新控制点
  addControlPoint(lng, lat)
}

// 查找点击的控制点
function findClickedPoint(lng: number, lat: number): number | null {
  const threshold = 0.0001
  for (let i = 0; i < props.controlPoints.length; i++) {
    const cp = props.controlPoints[i]
    const dist = Math.hypot(cp.lng - lng, cp.lat - lat)
    if (dist < threshold) return i
  }
  return null
}

// 切换手柄锁定
function toggleHandlesLocked() {
  handlesLocked.value = !handlesLocked.value
}

// 图标
const lockIcon = Lock
const unlockIcon = Unlock
const deleteIcon = Delete
</script>

<template>
  <div class="pen-tool-map">
    <UniversalMap
      ref="mapRef"
      :tracks="[]"
      :custom-overlays="mapOverlays"
      mode="detail"
      @map-click="handleMapClick"
    />

    <!-- 工具栏 -->
    <div class="pen-toolbar">
      <el-button-group>
        <el-button
          :type="handlesLocked ? 'primary' : ''"
          size="small"
          @click="toggleHandlesLocked"
        >
          <el-icon><component :is="handlesLocked ? lockIcon : unlockIcon" /></el-icon>
          <span class="btn-text">手柄锁定</span>
        </el-button>
        <el-button
          size="small"
          :disabled="selectedPointIndex === null"
          @click="selectedPointIndex !== null && deleteControlPoint(selectedPointIndex)"
        >
          <el-icon><Delete /></el-icon>
          <span class="btn-text">删除点</span>
        </el-button>
      </el-button-group>
    </div>

    <!-- 提示信息 -->
    <div class="pen-hint">
      点击地图添加控制点，拖拽调整位置
    </div>
  </div>
</template>

<style scoped>
.pen-tool-map {
  position: relative;
  width: 100%;
  height: 100%;
}

.pen-toolbar {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 1000;
  background: white;
  padding: 8px;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
}

.btn-text {
  margin-left: 4px;
}

.pen-hint {
  position: absolute;
  bottom: 12px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 1000;
  background: rgba(0, 0, 0, 0.7);
  color: white;
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 14px;
  pointer-events: none;
}
</style>
```

**Step 2: 提交**

```bash
git add frontend/src/components/interpolation/PenToolMap.vue
git commit -m "feat: add pen tool map component"
```

---

## Phase 10: 前端插值对话框组件

### Task 10: 创建插值对话框组件

**文件:**
- 创建: `frontend/src/components/interpolation/InterpolationDialog.vue`

**Step 1: 创建对话框组件**

```vue
<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Close, Check, RefreshLeft, Link, Timer,
  InfoFilled, View, Delete, Edit
} from '@element-plus/icons-vue'
import PenToolMap from './PenToolMap.vue'
import { interpolationApi, type ControlPoint, type AvailableSegment } from '@/api/interpolation'

interface Props {
  visible: boolean
  trackId: number
  points: Array<{
    point_index: number
    time: string
    latitude: number
    longitude: number
    speed: number | null
    bearing: number | null
  }>
}

interface Emits {
  (e: 'update:visible', value: boolean): void
  (e: 'applied'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// 状态
const step = ref<'select' | 'draw' | 'preview'>('select')
const minInterval = ref(3)
const startPointIndex = ref<number | null>(null)
const endPointIndex = ref<number | null>(null)
const controlPoints = ref<ControlPoint[]>([])
const isPreviewing = ref(false)
const isApplying = ref(false)

// 可用区段
const availableSegments = ref<AvailableSegment[]>([])

// 选中的区段信息
const selectedSegment = computed(() => {
  if (startPointIndex.value === null || endPointIndex.value === null) return null
  return availableSegments.value.find(s =>
    s.start_index === startPointIndex.value &&
    s.end_index === endPointIndex.value
  )
})

// 起点和终点数据
const startPointData = computed(() => {
  if (startPointIndex.value === null) return null
  return props.points.find(p => p.point_index === startPointIndex.value)
})

const endPointData = computed(() => {
  if (endPointIndex.value === null) return null
  return props.points.find(p => p.point_index === endPointIndex.value)
})

// 预计插入的点数
const estimatedPointCount = computed(() => {
  if (!selectedSegment.value) return 0
  return Math.floor(selectedSegment.value.interval_seconds)
})

// 加载可用区段
async function loadAvailableSegments() {
  try {
    availableSegments.value = await interpolationApi.getAvailableSegments(
      props.trackId,
      minInterval.value
    )
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '加载区段失败')
  }
}

// 选择起点
function handleStartPointChange(index: number) {
  startPointIndex.value = index
  if (endPointIndex.value !== null && endPointIndex.value <= index) {
    endPointIndex.value = null
  }
}

// 选择终点
function handleEndPointChange(index: number) {
  if (startPointIndex.value === null) {
    ElMessage.warning('请先选择起点')
    return
  }
  if (index <= startPointIndex.value) {
    ElMessage.warning('终点必须在起点之后')
    return
  }
  endPointIndex.value = index
}

// 进入绘制模式
function enterDrawMode() {
  if (!selectedSegment.value) {
    ElMessage.warning('请先选择有效的区段')
    return
  }
  step.value = 'draw'
}

// 预览插值
async function handlePreview() {
  if (!startPointData.value || !endPointData.value) return

  isPreviewing.value = true
  try {
    const result = await interpolationApi.preview({
      track_id: props.trackId,
      start_point_index: startPointIndex.value!,
      end_point_index: endPointIndex.value!,
      control_points: controlPoints.value,
      interpolation_interval_seconds: 1
    })
    step.value = 'preview'
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '预览失败')
  } finally {
    isPreviewing.value = false
  }
}

// 应用插值
async function handleApply() {
  if (!startPointData.value || !endPointData.value) return

  isApplying.value = true
  try {
    await interpolationApi.create(props.trackId, {
      start_point_index: startPointIndex.value!,
      end_point_index: endPointIndex.value!,
      control_points: controlPoints.value,
      interpolation_interval_seconds: 1,
      algorithm: 'cubic_bezier'
    })
    ElMessage.success('插值已应用')
    emit('applied')
    handleClose()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '应用失败')
  } finally {
    isApplying.value = false
  }
}

// 清除路径
function handleClearPath() {
  controlPoints.value = []
  step.value = 'draw'
}

// 重置
function handleReset() {
  step.value = 'select'
  startPointIndex.value = null
  endPointIndex.value = null
  controlPoints.value = []
}

// 关闭对话框
function handleClose() {
  handleReset()
  emit('update:visible', false)
}

// 监听对话框打开
watch(() => props.visible, (visible) => {
  if (visible) {
    handleReset()
    loadAvailableSegments()
  }
})

// 监听最小间隔变化
watch(minInterval, () => {
  loadAvailableSegments()
  startPointIndex.value = null
  endPointIndex.value = null
})

// 图标
const linkIcon = Link
const timerIcon = Timer
const infoIcon = InfoFilled
const viewIcon = View
const refreshIcon = RefreshLeft
const deleteIcon = Delete
const checkIcon = Check
const closeIcon = Close
</script>

<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="emit('update:visible', $event)"
    title="路径插值"
    width="800px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <!-- 选择区段步骤 -->
    <div v-if="step === 'select'" class="interpolation-step">
      <h3 class="step-title">
        <el-icon><component :is="linkIcon" /></el-icon>
        选择区段
      </h3>

      <div class="segment-selector">
        <div class="selector-row">
          <label>起点：</label>
          <el-select
            v-model="startPointIndex"
            placeholder="选择起点"
            @change="handleStartPointChange"
            style="width: 280px"
          >
            <el-option
              v-for="seg in availableSegments"
              :key="seg.start_index"
              :label="`点 #${seg.start_index} - ${seg.start_time}`"
              :value="seg.start_index"
            />
          </el-select>
        </div>

        <div class="selector-row">
          <label>终点：</label>
          <el-select
            v-model="endPointIndex"
            placeholder="选择终点"
            @change="handleEndPointChange"
            :disabled="!startPointIndex"
            style="width: 280px"
          >
            <el-option
              v-for="seg in availableSegments.filter(s => s.start_index >= (startPointIndex || 0))"
              :key="seg.end_index"
              :label="`点 #${seg.end_index} - ${seg.end_time}`"
              :value="seg.end_index"
            />
          </el-select>
        </div>

        <div class="selector-row">
          <label>最小间隔：</label>
          <el-slider
            v-model="minInterval"
            :min="1"
            :max="60"
            :step="1"
            style="width: 200px"
          />
          <span class="interval-value">{{ minInterval }} 秒</span>
        </div>
      </div>

      <!-- 区段信息 -->
      <div v-if="selectedSegment" class="segment-info">
        <el-alert type="info" :closable="false">
          <template #title>
            <div class="info-content">
              <span>
                <el-icon><component :is="timerIcon" /></el-icon>
                间隔：{{ selectedSegment.interval_seconds }} 秒
              </span>
              <span>
                <el-icon><component :is="infoIcon" /></el-icon>
                预计插入：约 {{ estimatedPointCount }} 个点
              </span>
            </div>
          </template>
        </el-alert>
      </div>

      <div class="step-actions">
        <el-button @click="handleClose">
          <el-icon><component :is="closeIcon" /></el-icon>
          取消
        </el-button>
        <el-button
          type="primary"
          :disabled="!selectedSegment"
          @click="enterDrawMode"
        >
          下一步：绘制路径
        </el-button>
      </div>
    </div>

    <!-- 绘制路径步骤 -->
    <div v-else-if="step === 'draw'" class="interpolation-step">
      <div class="step-header">
        <h3 class="step-title">
          <el-icon><component :is="linkIcon" /></el-icon>
          绘制路径
        </h3>
        <el-button size="small" text @click="step = 'select'">
          <el-icon><component :is="refreshIcon" /></el-icon>
          返回
        </el-button>
      </div>

      <div class="map-container">
        <PenToolMap
          v-if="startPointData && endPointData"
          :track-id="trackId"
          :start-point="{
            lng: startPointData.longitude,
            lat: startPointData.latitude,
            index: startPointData.point_index,
            time: startPointData.time
          }"
          :end-point="{
            lng: endPointData.longitude,
            lat: endPointData.latitude,
            index: endPointData.point_index,
            time: endPointData.time
          }"
          :control-points="controlPoints"
          v-model:control-points="controlPoints"
          :model-value="true"
        />
      </div>

      <div class="step-actions">
        <el-button @click="handleClearPath">
          <el-icon><component :is="deleteIcon" /></el-icon>
          清除路径
        </el-button>
        <el-button @click="handleReset">
          <el-icon><component :is="refreshIcon" /></el-icon>
          重置
        </el-button>
        <el-button type="primary" @click="handlePreview">
          <el-icon><component :is="viewIcon" /></el-icon>
          预览
        </el-button>
      </div>
    </div>

    <!-- 预览步骤 -->
    <div v-else-if="step === 'preview'" class="interpolation-step">
      <div class="step-header">
        <h3 class="step-title">
          <el-icon><component :is="viewIcon" /></el-icon>
          预览结果
        </h3>
        <el-button size="small" text @click="step = 'draw'">
          <el-icon><component :is="refreshIcon" /></el-icon>
          返回修改
        </el-button>
      </div>

      <div class="preview-info">
        <el-alert type="success" :closable="false">
          <template #title>
            区段 #{{ startPointIndex }} → #{{ endPointIndex }} 已准备就绪
          </template>
        </el-alert>
      </div>

      <div class="step-actions">
        <el-button @click="handleReset">
          <el-icon><component :is="refreshIcon" /></el-icon>
          重置
        </el-button>
        <el-button
          type="primary"
          :loading="isApplying"
          @click="handleApply"
        >
          <el-icon><component :is="checkIcon" /></el-icon>
          应用
        </el-button>
      </div>
    </div>
  </el-dialog>
</template>

<style scoped>
.interpolation-step {
  padding: 0;
}

.step-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 20px 0;
  font-size: 16px;
  font-weight: 500;
}

.step-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.segment-selector {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 20px;
}

.selector-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.selector-row label {
  width: 80px;
  font-weight: 500;
}

.interval-value {
  margin-left: 12px;
  font-weight: 500;
  min-width: 60px;
}

.segment-info {
  margin-bottom: 20px;
}

.info-content {
  display: flex;
  gap: 24px;
}

.info-content span {
  display: flex;
  align-items: center;
  gap: 4px;
}

.map-container {
  height: 400px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 20px;
}

.preview-info {
  margin-bottom: 20px;
}

.step-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
```

**Step 2: 提交**

```bash
git add frontend/src/components/interpolation/InterpolationDialog.vue
git commit -m "feat: add interpolation dialog component"
```

---

## Phase 11: 集成到轨迹详情页

### Task 11: 在轨迹详情页添加入口

**文件:**
- 修改: `frontend/src/views/TrackDetail.vue`

**Step 1: 添加导入和状态**

在 `<script setup>` 部分添加：

```typescript
import InterpolationDialog from '@/components/interpolation/InterpolationDialog.vue'
import { Link } from '@element-plus/icons-vue'

// 插值对话框状态
const showInterpolationDialog = ref(false)
```

**Step 2: 添加处理函数**

```typescript
// 打开插值对话框
function handleOpenInterpolation() {
  showInterpolationDialog.value = true
}

// 插值应用后刷新
function handleInterpolationApplied() {
  loadTrackDetail()
}
```

**Step 3: 在模板中添加按钮和对话框**

在"记录配置"按钮附近添加下拉菜单：

```vue
<!-- 编辑轨迹下拉菜单 -->
<el-dropdown @command="handleEditCommand" trigger="click">
  <el-button>
    编辑轨迹
    <el-icon class="el-icon--right"><ArrowDown /></el-icon>
  </el-button>
  <template #dropdown>
    <el-dropdown-menu>
      <el-dropdown-item command="geo-editor">
        <el-icon><Edit /></el-icon>
        编辑地理信息
      </el-dropdown-item>
      <el-dropdown-item command="interpolation">
        <el-icon><component :is="Link" /></el-icon>
        路径插值
      </el-dropdown-item>
    </el-dropdown-menu>
  </template>
</el-dropdown>

<!-- 添加命令处理函数 -->
<script setup>
// ... 现有代码

function handleEditCommand(command: string) {
  switch (command) {
    case 'geo-editor':
      router.push(`/geo-editor/${trackId.value}`)
      break
    case 'interpolation':
      handleOpenInterpolation()
      break
  }
}
</script>
```

在模板末尾添加对话框组件：

```vue
<!-- 插值对话框 -->
<InterpolationDialog
  v-model:visible="showInterpolationDialog"
  :track-id="trackId"
  :points="trackPoints"
  @applied="handleInterpolationApplied"
/>
```

**Step 4: 提交**

```bash
git add frontend/src/views/TrackDetail.vue
git commit -m "feat: add interpolation dialog entry in track detail page"
```

---

## Phase 12: 测试与验证

### Task 12: 测试完整流程

**Step 1: 启动后端服务**

```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate
source venv/bin/activate  # 或 Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Step 2: 启动前端服务**

```bash
cd frontend
npm install
npm run dev
```

**Step 3: 测试流程**

1. 登录系统
2. 进入任意轨迹详情页
3. 点击"编辑轨迹" → "路径插值"
4. 选择起点和终点（间隔 ≥ 3 秒）
5. 点击"下一步：绘制路径"
6. 在地图上点击添加控制点
7. 点击"预览"查看插值结果
8. 点击"应用"保存插值

**Step 4: 验证数据库**

```bash
cd backend
python -c "
from app.core.database import SessionLocal
from app.models.interpolation import TrackInterpolation
db = SessionLocal()
result = db.query(TrackInterpolation).all()
print(f'Interpolations: {len(result)}')
for interp in result:
    print(f'  - Track {interp.track_id}: {interp.start_point_index} -> {interp.end_point_index}, {interp.point_count} points')
db.close()
"
```

**Step 5: 验证插值点**

```bash
python -c "
from app.core.database import SessionLocal
from app.models.track import TrackPoint
db = SessionLocal()
result = db.query(TrackPoint).filter(TrackPoint.is_interpolated == True).all()
print(f'Interpolated points: {len(result)}')
db.close()
"
```

**Step 6: 提交测试修正（如有必要）**

```bash
git commit -am "fix: address testing issues"
```

---

## 验收标准

- [ ] 用户可以选择间隔 ≥ 3 秒的区段
- [ ] 用户可以在地图上添加/删除/拖拽控制点
- [ ] 实时预览显示插值路径
- [ ] 预览功能正确显示插值点数量和位置
- [ ] 应用功能成功创建插值记录和插入轨迹点
- [ ] 插值点正确标记 `is_interpolated=true`
- [ ] 插值点包含正确的坐标转换（WGS84/GCJ02/BD09）
- [ ] 插值点速度和航向正确线性插值
- [ ] 删除插值功能正确清除标记

---

**文档结束**
