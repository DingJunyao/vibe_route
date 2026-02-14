# 路径插值功能设计文档

**日期**: 2026-02-08
**状态**: 设计阶段
**作者**: AI Assistant

## 1. 概述

### 1.1 功能背景

在 GPS 信号丢失的区域（如隧道），轨迹记录会产生中断，导致"经过区域"显示不完整。本功能允许用户手动选择中断区段，通过类似 Adobe Illustrator 钢笔工具的方式绘制预期路径，系统自动生成插值点填充空白区域。

### 1.2 目标用户

- 需要完善轨迹数据的用户
- 经常经过隧道或信号盲区的骑行/驾驶者

### 1.3 核心特性

- **钢笔工具交互**: 点击添加控制点，拖拽调整曲线形状
- **独立手柄控制**: 每个控制点带有方向手柄，精确控制曲线弯曲
- **实时预览**: 绘制过程中实时显示插值点位置
- **基于速度的插值**: 根据起止点速度线性插值
- **手动地理填充**: 插值后可手动重新填充省市区信息

---

## 2. 数据库设计

### 2.1 新增表: `track_interpolations`

```sql
CREATE TABLE track_interpolations (
    id INTEGER PRIMARY KEY,
    track_id INTEGER NOT NULL,
    start_point_index INTEGER NOT NULL,
    end_point_index INTEGER NOT NULL,
    path_geometry TEXT NOT NULL,
    interpolation_interval_seconds INTEGER NOT NULL DEFAULT 1,
    point_count INTEGER NOT NULL,
    algorithm VARCHAR(50) NOT NULL DEFAULT 'cubic_bezier',
    created_at TIMESTAMP NOT NULL,
    created_by INTEGER NOT NULL,
    is_valid BOOLEAN NOT NULL DEFAULT TRUE,

    FOREIGN KEY (track_id) REFERENCES tracks(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);
```

### 2.2 修改表: `track_points`

```sql
ALTER TABLE track_points ADD COLUMN is_interpolated BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE track_points ADD COLUMN interpolation_id INTEGER REFERENCES track_interpolations(id);
```

### 2.3 约束规则

1. **唯一性约束**: 同一轨迹的同一区段只能有一个插值配置
2. **区段不重叠**: 插值区段不能相互重叠
3. **级联删除**: 删除插值记录时，关联的插值点标记为 `is_interpolated=FALSE`

---

## 3. 后端 API 设计

### 3.1 API 端点

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/interpolation/tracks/{track_id}/available-segments` | 获取可插值区段列表 |
| POST | `/interpolation/preview` | 预览插值结果 |
| POST | `/interpolation/tracks/{track_id}/interpolations` | 创建插值 |
| GET | `/interpolation/tracks/{track_id}/interpolations` | 获取轨迹的插值列表 |
| PUT | `/interpolation/interpolations/{interpolation_id}` | 更新插值配置 |
| DELETE | `/interpolation/interpolations/{interpolation_id}` | 删除插值 |

### 3.2 Schema 定义

```python
class ControlPointHandle(BaseModel):
    dx: float
    dy: float

class ControlPoint(BaseModel):
    lng: float
    lat: float
    in_handle: ControlPointHandle
    out_handle: ControlPointHandle
    handles_locked: bool = True

class InterpolationCreateRequest(BaseModel):
    start_point_index: int
    end_point_index: int
    control_points: List[ControlPoint]
    interpolation_interval_seconds: float = 1.0
    algorithm: str = "cubic_bezier"
```

### 3.3 核心算法

**三次 Bézier 曲线公式:**
```
B(t) = (1-t)³P₀ + 3(1-t)²tP₁ + 3(1-t)t²P₂ + t³P₃
```

**插值点生成流程:**
1. 构建完整控制点序列（起点 + 控制点 + 终点）
2. 生成多段三次 Bézier 曲线
3. 计算曲线总长度（弧长参数化）
4. 按时间间隔均匀分布插值点
5. 线性插值速度和航向角

---

## 4. 前端设计

### 4.1 组件结构

```
InterpolationDialog.vue (主对话框)
├── 选择区段步骤
│   ├── 起点/终点下拉选择
│   └── 最小间隔滑块
├── 绘制路径步骤
│   └── PenToolMap.vue (钢笔工具地图)
│       ├── 地图显示
│       ├── 控制点渲染
│       ├── 手柄渲染与交互
│       └── 实时预览线
└── 预览确认步骤
    └── 预览统计与应用按钮
```

### 4.2 交互流程

```
1. 用户在轨迹详情页点击"编辑轨迹" → "路径插值"
   ↓
2. 对话框打开，加载可插值区段
   ↓
3. 用户选择起点和终点（间隔 ≥ 3 秒）
   ↓
4. 进入绘制模式，地图显示 A-B 直线
   ↓
5. 用户点击地图添加控制点，拖拽调整位置
   ↓
6. 点击控制点显示手柄，拖拽手柄调整曲线
   ↓
7. 实时显示插值点预览（虚线圆点）
   ↓
8. 点击"预览"生成完整插值数据
   ↓
9. 确认后点击"应用"保存到服务器
   ↓
10. 关闭对话框，轨迹详情页刷新
```

### 4.3 钢笔工具交互

| 操作 | 效果 |
|------|------|
| 点击空白处 | 添加新控制点 |
| 拖拽控制点 | 移动位置 |
| 点击控制点 | 显示手柄 |
| 拖拽手柄 | 调整曲线形状 |
| 右键/双击控制点 | 删除该点 |
| Alt + 拖拽手柄 | 解锁手柄独立移动 |

### 4.4 文件结构

```
frontend/src/
├── api/
│   └── interpolation.ts
├── components/
│   └── interpolation/
│       ├── InterpolationDialog.vue
│       └── PenToolMap.vue
├── utils/
│   └── bezierCurve.ts
└── views/
    └── TrackDetail.vue (添加入口)
```

---

## 5. 工具类: Bézier 曲线引擎

### 5.1 核心类

```typescript
class CubicBezierCurve {
  constructor(points: Array<Point | BezierControlPoint>)
  getTotalLength(): number
  getPointAtLength(targetLength: number): Point
  generatePoints(count: number): Point[]
}
```

### 5.2 关键方法

**弧长参数化**: 确保插值点在曲线上均匀分布，而不是在参数 t 上均匀分布。

**手柄计算**: 新添加的控制点自动计算合理的默认手柄位置（基于前后点方向）。

---

## 6. 入口集成

### 6.1 轨迹详情页

在 `TrackDetail.vue` 添加"编辑轨迹"下拉菜单：

```
编辑轨迹 ▼
├── 编辑地理信息 → 跳转 GeoEditor
├── 路径插值 → 打开 InterpolationDialog
├── 拆分轨迹 → (未来功能)
└── 合并轨迹 → (未来功能)
```

### 6.2 图标使用

使用 Element Plus 内置图标:
- `Link` - 路径插值
- `Edit` - 编辑地理信息
- `Lock` / `Unlock` - 手柄锁定
- `Delete` - 删除控制点
- `View` - 预览
- `Check` - 应用
- `RefreshLeft` / `RefreshRight` - 撤销/重做

---

## 7. 约束与规则

### 7.1 区段要求

- 间隔 ≥ 3 秒（用户可调）
- A、B 之间无其他轨迹点
- A、B 之间无现有插值配置

### 7.2 限制

- 一条轨迹不允许多个插值段（简化设计）
- 控制点数量建议 ≤ 20 个（性能考虑）
- 插值点数 = 时间差（秒），每秒一个点

### 7.3 数据持久化

- 插值点标记为 `is_interpolated=true`
- 保存插值元数据（算法、时间、控制点）
- 选择区段时忽略插值点索引

---

## 8. 未来扩展

1. **批量插值**: 一次处理多个空白区段
2. **自动检测**: 识别隧道区域（速度+GPS信号丢失模式）
3. **插值模板**: 保存常用配置供复用
4. **导出选项**: 导出时选择是否包含插值点
5. **插值历史**: 查看和恢复历史操作

---

## 9. 实施计划

1. **Phase 1**: 数据库表结构和后端 API
2. **Phase 2**: Bézier 曲线引擎（前端 + 后端）
3. **Phase 3**: 钢笔工具地图组件
4. **Phase 4**: 对话框和交互流程
5. **Phase 5**: 集成测试和优化
