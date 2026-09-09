# 功能模块

## 合并轨迹

### 流程（两步式，独立页面 `/merge`）

1. **选择轨迹**: 多选列表（含已结束实时记录的轨迹；进行中的与无轨迹虚拟项不可选），按时间排序展示已选顺序，前端粗略重叠预警
2. **预览合并**: 地图各段彩色线区分（`customOverlays`，多坐标系）+ 起终点标记 + 图例；统计信息、段列表、重叠去重明细；输入名称/描述后确认

### 后端（tracks.py + track_service.py）

- `POST /api/tracks/merge/preview`: 返回合并方案（不落库）
- `POST /api/tracks/merge`: 创建新轨迹，原轨迹零修改
- 预览与执行共用 `_build_merge_plan`（所见即所得）
- 无表结构变更；新轨迹 `original_filename` 记录源 ID（如 `merge:1+5+9`）

### 去重规则（后段优先）

- 排序键 = `time`（空回退 `created_at`）；段按 `start_time` 升序
- 每段截断于下一段首点排序键（`>=` 边界归后段），重叠区间保留时间靠后的段
- 复制点保留全部字段，`interpolation_id` 置空（避免悬空外键），`point_index` 重编号
- 统计口径同 `create_from_gpx`（3D Haversine 距离、相邻高差爬升/下降、首末点时长）

### 空缺补全（不插值，仅预览提示）

- 判定: 相邻段「前段末点时间 → 后段首点时间」间隔 > 300 秒（`MERGE_GAP_THRESHOLD_SECONDS`）；任一端时间缺失则不判空缺
- 预览响应 `gaps[]`: `from_segment/to_segment/time_gap`（秒，缺失 null）/`distance`（水平 Haversine）/`is_gap`
- 渲染: 相邻段末点→首点画衔接线（不生成插值点），空缺=橙色 `#e6a23c` 虚线（`dashArray '12 8'`），正常=灰色 `#909399` 实线；图例 + el-alert 警告 + 空缺明细
- 各引擎 dashArray: 高德 `strokeStyle:'dashed'`+`strokeDasharray` 字符串；百度 GL/Legacy 仅 `strokeStyle`；腾讯/Leaflet 数组（解析 `'12 8'`→`[12,8]`）；Google 用 Symbol repeat 方案（无 `strokeDasharray` 支持）

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

### Google 反向地理编码

- **端点**: `{api_base_url}/maps/api/geocode/json`（默认 `https://maps.googleapis.com`，大陆部署可配置反向代理）
- **坐标系**: WGS84 输入（无需转换）
- **配置项**: `api_key`、`freq`（默认 10 次/秒）、`get_en_result`（额外请求英文结果）、`api_base_url`
- **字段映射**: `administrative_area_level_1/2` → 省/市（直辖市 level_2 与省级相同则置空），`locality`/`sublocality` → 区，`sublocality_level_1/2`/`neighborhood` → 街道；道路名遍历所有 results 的 `route` 组件

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
