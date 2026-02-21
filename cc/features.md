# 功能模块

## 实时记录

### 时间字段规范

| 字段 | 含义 | 用途 |
|------|------|------|
| `last_upload_at` | LiveRecording 上传时间 | 备用 |
| `last_point_time` | GPS 时间 | 对话框"轨迹点时间" |
| `last_point_created_at` | 服务器接收时间 | **"最近更新"统一使用此字段** |

### 核心逻辑

- **乱序处理**: 前端接收新点后按 `time` 排序
- **point_index**: 实时记录期间可能不准，停止时自动修复
- **查询排序**: 始终使用 `.order_by(TrackPoint.time.asc(), TrackPoint.created_at.asc())`

### WebSocket

- 连接: `/api/ws/live-recording/{recording_id}?token={TOKEN}`
- 自动重连: 3 秒间隔
- 地址动态适配: [`origin.ts`](frontend/src/utils/origin.ts) 根据访问地址判断

## 地理编码

### 本地反向编码

- **边界框过滤**: 快速获取候选区域
- **Shapely 精确匹配**: `polygon.contains(point)` 判断
- **无 geometry**: 跳过（不回退到边界框）

### DataV 导入

- **在线数据**: GCJ02 坐标，导入时转 WGS84
- **压缩包**: 假设 WGS84
- **特殊行政区划**:
  - 直辖市 (110000/120000/310000/500000): 区县直属省级
  - 不设区地级市 (东莞/中山/儋州/嘉峪关): 保留市级，无镇级
  - 省辖县级 (仙桃/潜江/天门/济源): 分类为 `area` 级别

## PostGIS

### 架构

- `admin_divisions.geometry`: GeoJSON 多边形（shapely 用）
- `admin_divisions_spatial.geom`: PostGIS 几何（空间查询用）
- **手动同步**: 后台管理提供同步功能

## 地理信息编辑器

### 撤销/重做

- 快捷键: Ctrl+Z 撤销, Ctrl+Y 重做
- 历史结构: `history[i].after` 是撤销后应恢复的状态
- 类型扩展: `'edit' | 'resize' | 'move'`

### 刻度条

- 边界扩展: 基于可视区域点时间扩展
- 点索引定位: `findPointIndexByTime` 确保刻度与点一致
- 级别去重: 主刻度 5%, 次刻度 1%, 三级 0.2%

## 轨迹插值

### 三阶段流程

1. **选择区段**: 表格展示可插值区段（间隔 ≥ 最小间隔）
2. **绘制路径**: 地图点击添加控制点，支持拖拽、撤销/重做
3. **预览结果**: 禁用编辑，确认后保存

### 控制点手柄

- `handlesLocked = true`: 拖拽一个手柄，另一个对称移动
- `handlesLocked = false`: 手柄独立移动

## 覆盖层模板编辑器

### 坐标系统规范

| 数据 | 单位 | 范围 |
|------|------|------|
| `position.x/y` | 画布比例 | -0.5 到 0.5 |
| `layout.width/height` | 画布比例 | 0 到 1 |
| `style.font_size` | 画布比例 | 正数 |

### 转换公式

```javascript
// 画布比例 → 画布像素
offsetX = element.position.x * canvasWidth

// 画布像素 → 预览百分比 (0-100)
leftPct = (elemX * scaleToPreviewX) / previewBaseWidth * 100

// 预览百分比 → 画布比例
deltaCanvasPct = deltaPreviewPct / 100
```

### 容器锚点

- **始终相对于画布计算**，不受 `use_safe_area` 影响
- 公式: `final_x = container_x + offset_x - elem_anchor_x`

### 空格键拖动

- 滚动区域: 容器尺寸 150%
- 拖动时: 禁用滚动条 (`overflow: hidden !important`)
- 初始居中: `(wrapperWidth - containerWidth) / 2`

## 海报生成

### 前端生成

- iframe 加载 [`TrackMapOnly.vue`](frontend/src/views/TrackMapOnly.vue)
- 等待 `window.mapReady === true`
- html2canvas 截取 `.map-only-page`（不截 `.map-wrapper-container`）

### 后端生成

- Playwright 访问 `/tracks/{id}/map-only`
- 等待 `window.mapReady === true`
- 使用 `clip` 参数截取

### 百度地图

- **强制后端生成**: Legacy 版本 DOM 渲染，html2canvas 无法正确捕获

### 缩放等待时间

- 动态: `baseWait + (mapScale - 100) * multiplier`

## 分享嵌入模式

- URL: `/s/{token}?embed=true`
- 只显示地图，隐藏其他元素
- "查看轨迹详情"按钮跳转完整分享页
