# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Vibe Route** 是一个基于 [gpxutil](https://github.com/DingJunyao/gpxutil) 构建的全栈 Web 轨迹管理系统。用户可以上传 GPX 文件，系统会解析轨迹数据，进行坐标转换（WGS84/GCJ02/BD09）、地理编码填充，并在地图上可视化展示。

## Development

对于 Python，我用的是 Anaconda，环境是 vibe_route。所有与 Python 相关的操作都要保证切换到这个环境。

用的是什么数据库，看后端的 .env。

## Development Commands

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
mkdir -p data/uploads data/temp data/exports data/road_signs
uvicorn app.main:app --reload
alembic upgrade head
```

后端运行在 `http://localhost:8000`，API 文档：`http://localhost:8000/docs`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

前端运行在 `http://localhost:5173`

### Testing

用户会在开发过程中对项目多次测试。当用户对项目中存在的问题询问时，除一般的逻辑外，还应当考虑到：

- 数据库里面的数据
- 前端的显示效果

这些都可以使用插件或 MCP 解决。优先考虑 MCP。

### Reviewing

在合适的情况下，或者是用户提出审查项目时，使用 code-review-excellence skill 来审查这个项目。排除 ./ref_gpxutil。

审查结果存入 ./ref/CODE_REVIEW_REPORT.md，如果已存在，则覆盖它。

## Summarize

每次大的更改，当用户提出整理要点，都要把要点记录在本文件中。

## Architecture Overview

### 认证流程（双重加密）

密码在传输和存储过程中经过两次加密：

1. **前端加密** ([`crypto.ts`](frontend/src/utils/crypto.ts))：SHA256 加密
2. **后端存储** ([`security.py`](backend/app/core/security.py))：bcrypt 二次哈希

### 公开配置 vs 管理员配置

- **公开配置** (`GET /api/auth/config`)：任何用户可访问，只返回地图相关配置
- **管理员配置** (`GET /api/admin/config`)：需要管理员权限，返回完整配置

前端 [`config.ts`](frontend/src/stores/config.ts) store 会根据用户权限自动选择合适的 API。

### 多坐标系支持

轨迹点存储三种坐标系：

- **WGS84**: 国际标准坐标系（GPS 原始坐标）
- **GCJ02**: 中国火星坐标系（高德、腾讯地图、天地图）
- **BD09**: 百度坐标系

地图组件根据选择的底图自动使用对应坐标。

### 用户状态字段

- **`is_valid`**: 软删除标记，查询用户时会过滤 `is_valid = False` 的记录
- **`is_active`**: 账户启用状态，控制用户能否登录

用户创建时会复用已删除（`is_valid = False`）用户的记录。

### 数据库模型

核心模型：

- [`User`](backend/app/models/user.py): 用户表，首位注册用户自动成为管理员
- [`Track`](backend/app/models/track.py): 轨迹表
- [`TrackPoint`](backend/app/models/track.py): 轨迹点表
- [`Task`](backend/app/models/task.py): 异步任务
- [`Config`](backend/app/models/config.py): 系统配置
- [`LiveRecording`](backend/app/models/live_recording.py): 实时记录

所有模型继承 [`AuditMixin`](backend/app/models/base.py)，包含 `created_at`, `updated_at`, `created_by`, `updated_by`, `is_valid` 字段。

### 路由守卫

前端路由守卫（[`router/index.ts`](frontend/src/router/index.ts)）：

- `guest`: 未登录用户可访问
- `requiresAuth`: 需要登录
- `requiresAdmin`: 需要管理员权限

### API 请求拦截

[`request.ts`](frontend/src/api/request.ts) 配置：

- 自动添加 `Authorization: Bearer {token}` 头
- 401 响应使用后端返回的具体错误信息
- 不在登录页时，401 会清除 token 并跳转登录页
- 统一错误处理和消息提示

### gpxutil 集成

[`gpxutil_wrapper/`](backend/app/gpxutil_wrapper/) 目录封装了 gpxutil 核心功能：

- [`coord_transform.py`](backend/app/gpxutil_wrapper/coord_transform.py): 坐标系转换
- [`geocoding.py`](backend/app/gpxutil_wrapper/geocoding.py): 地理编码填充
- [`svg_gen.py`](backend/app/gpxutil_wrapper/svg_gen.py): 道路标志生成
- [`overlay.py`](backend/app/gpxutil_wrapper/overlay.py): 信息覆盖层生成

### 响应式设计

- 移动端断点：`screenWidth <= 1366px`
- 桌面端隐藏类：`.desktop-only`
- 移动端使用卡片列表替代表格
- viewport 配置：`maximum-scale=1.0, user-scalable=no`

### 响应式布局要点

使用 `vh` 单位实现基于视口高度的动态布局：

```css
.main { height: calc(100vh - 60px); }
.normal-map-container { height: 40vh; min-height: 300px; }
.chart { height: 22vh; min-height: 180px; }
```

窗口大小监听：

```typescript
const screenWidth = ref(window.innerWidth)
const screenHeight = ref(window.innerHeight)
const isMobile = computed(() => screenWidth.value <= 1366)
const isTallScreen = computed(() => !isMobile.value && screenHeight.value >= 800)
```

**首页布局**：

| 端     | 主容器高度            | 统计卡片              | 地图卡片           |
|--------|-----------------------|-----------------------|--------------------|
| 电脑端 | `calc(100vh - 60px)`  | 固定高度（4 列横向） | `flex: 1` 填充剩余  |
| 移动端 | `calc(100vh - 60px)`  | 70-80px（2x2 网格）   | `flex: 1`，最小 200px |

**轨迹详情页布局**：

- 固定布局（电脑端高度 >= 800px）：左侧固定（地图 + 图表），右侧滚动
- 常规布局（电脑端高度 < 800px）：左右独立滚动，地图 40vh，图表 22vh
- 移动端：单列流式布局，地图 30vh，图表 20vh

### 地图响应式重绘

使用 `ResizeObserver` 监听地图容器大小变化：

```typescript
const mapResizeObserver = new ResizeObserver(() => {
  if (mapRef.value?.resize) mapRef.value.resize()
})
mapResizeObserver.observe(mapWrapperRef.value)
```

所有地图组件都暴露了 `resize()` 方法，通过 [`UniversalMap.vue`](frontend/src/components/map/UniversalMap.vue) 统一调用。

### 地图与图表双向同步

轨迹详情页（[`TrackDetail.vue`](frontend/src/views/TrackDetail.vue)）实现了地图与图表的双向交互：

- **桌面端**：鼠标悬停同步高亮
- **移动端**：点击显示 tooltip

关键技术点：

- 动态触发距离：`Math.pow(2, 12 - zoom) * 0.008`
- 位置信息格式化：`省 市 区 road_number road_name`
- 各地图引擎事件处理：
  - 高德：`mousemove`/`click` + DOM 捕获阶段
  - 百度：`addEventListener('mousemove')`/`addEventListener('click')`
  - Leaflet：直接监听地图实例
- 图表同步：ECharts `dispatchAction` 触发 `showTip`/`highlight`
- 蓝色圆点标记：`#409eff` 背景，`2px solid #fff` 边框

### 百度地图 GL 特殊处理

1. 自定义覆盖物必须继承 `BMapGL.Overlay`
2. 监听 `moveend` 和 `zoomend` 确保标记位置自动更新
3. **InfoWindow 状态冲突**：需要先 `closeInfoWindow()` 再 `setTimeout(() => openInfoWindow(), 0)`
4. 使用标准覆盖物 API：`map.addOverlay(overlay)` / `map.removeOverlay(overlay)`

### 腾讯地图 GL JS API 特殊处理

1. 无坐标转换 API：需手动计算像素坐标
2. 使用 MultiMarker 显示标记：Canvas 绘制蓝色圆点作为 data URL
3. 事件监听在 DOM 容器上：捕获阶段确保事件能被捕获
4. **InfoWindow 参数**：创建时必须指定 `map`、`offset` 和 `enableCustom`

### 自定义 Tooltip（Leaflet/百度）

为避免原生 InfoWindow/Popup 闪烁，使用自定义 HTML 元素：

- 绝对定位的 `div`，`pointer-events: none`
- 监听地图 `move`/`moveend` 事件实时更新位置
- 坐标转换：Leaflet 用 `map.latLngToContainerPoint(latlng)`，百度用 `map.pointToOverlayPixel(point)`

### 轨迹详情页"经过区域"点击高亮

点击"经过区域"树中的项目（省/市/区/道路），地图上对应路径段显示为蓝色高亮。

**后端**：为每个区域节点添加 `start_index` 和 `end_index` 字段，使用 `point.point_index` 作为索引来源。

**前端**：所有地图引擎添加 `highlightSegment` prop，在 `drawTracks` 方法中绘制高亮路径段（蓝色，线宽 7）。

**坐标对象注意事项**：

- 高德：`AMap.LngLat` 对象
- 百度：`BMapGL.Point` 对象
- 腾讯：`TMap.LatLng` 对象
- Leaflet：`[lat, lng]` 数组

**滚动容器**：页面使用 `.track-detail-container` 作为滚动容器，需使用 `containerRef.value?.scrollTo()` 而非 `window.scrollTo()`。

### 首页地图轨迹信息显示模式

地图组件支持两种模式，通过 `mode` prop 控制：

- `home` 模式（首页）：悬停/点击轨迹时显示轨迹信息（名称、时间、里程、历时）
- `detail` 模式（轨迹详情页）：悬停/点击时显示点信息（位置、海拔、时间、速度）

事件处理：

- home 模式：发射 `track-hover` 事件，参数为 `trackId`
- detail 模式：发射 `point-hover` 事件，参数为 `(point, pointIndex)`

**腾讯地图移动端修复**：

1. 移除 mouseout 监听器（仅桌面端添加）
2. 防抖标志防止 `touchend` 和 `click` 重复触发
3. InfoWindow 创建时必须指定 `map`、`offset` 和 `enableCustom` 参数

**Leaflet 地图切换底图修复**：切换底图时需调用 `hideMarker()` 清除提示框。

### 地图居中按钮

地图控制栏提供居中按钮，点击后将所有轨迹居中显示，四周留 5% 空间。

**Padding 计算**：取地图容器宽高中较大值的 5%

**各地图引擎 fitBounds 实现**：

- Leaflet：`map.fitBounds(bounds, { padding: L.point(padding, padding) })`
- 高德：`AMapInstance.setFitView(null, false, [padding, padding, padding, padding])`
- 百度：`BMapInstance.setViewport(bounds)`
- 腾讯：`TMapInstance.fitBounds(boundsObj, { padding })`

### 轨迹详情页"经过区域"道路编号转标牌

将道路编号（如 G221、豫S88）转换为对应的道路标志 SVG。

**道路编号解析规则**：

| 数据库格式 | 类型      | sign_type | code  | province |
|-----------|-----------|-----------|-------|----------|
| G221      | 国道      | way       | G221  | -        |
| 豫S221     | 省道      | way       | S221  | 豫        |
| G5        | 国家高速  | expwy     | G5    | -        |
| 豫S88      | 省级高速  | expwy     | S88   | 豫        |
| 川SA       | 四川高速  | expwy     | SA    | 川        |

**判断顺序**：普通道路（G/S/X + 三位数字）→ 国家高速（G + 1-4位数字）→ 四川省级高速（S + 字母 + 可选数字，仅限四川）→ 省级高速（S + 1-4位纯数字，需省份前缀）

**关键技术点**：

1. 使用正则 `/[^\x00-\x7F]/` 匹配中文省份
2. 省级高速缓存键需包含省份，避免冲突
3. 使用 `loadingSigns` Set 防止重复加载
4. SVG 加载完成后通过 `treeForceUpdateKey` 强制树组件重新渲染
5. 全局样式：`.road-sign-inline svg { height: 1.2em; width: auto; }`

### 道路标志生成功能

首页提供道路标志 SVG 生成功能。

**功能说明**：

- 普通道路（`way`）：G/S/X + 三位数字
- 高速公路（`expwy`）：
  - 国家高速：G + 1-4 位数字
  - 省级高速：S + 纯数字或 S + 字母 + 可选数字（**仅限四川省**）

**前后端双重验证**：

- 前端验证提供即时反馈
- 后端使用 Pydantic `model_validator` 进行跨字段验证
- `field_validator` 先执行（如 `normalize_code` 转大写）
- `model_validator(mode='after')` 后执行（使用处理后的值进行跨字段验证）

**单选按钮说明文字模式**：

```vue
<el-form-item label="匹配方式">
  <el-radio-group v-model="importMatchMode">
    <el-radio value="index">索引</el-radio>
    <el-radio value="time">时间</el-radio>
  </el-radio-group>
  <div class="radio-hint">
    <template v-if="importMatchMode === 'index'">
      匹配 index 列的值
    </template>
    <template v-else>
      匹配 time_date/time_time 或 time 列的值
    </template>
  </div>
</el-form-item>
```

**表单变更自动清除预览**：任何表单字段变更都会清除 SVG 预览。

### 后台管理页面

**功能特性**：

1. 用户管理：分页列表、搜索、排序、筛选、设置管理员、禁用/启用、重置密码、删除
2. 系统配置：注册开关、邀请码要求、地图提供商、地图层配置
3. 邀请码管理：创建、查看列表、删除

**用户保护规则**：

1. 不能操作自己：不能修改自己的管理员状态、禁用自己、删除自己、重置自己的密码
2. 保护首位用户：不能取消首位用户管理员状态、禁用、删除、重置密码
3. 保留至少一位管理员

**Axios 数组参数序列化**：

在 [`request.ts`](frontend/src/api/request.ts) 中配置 `paramsSerializer: { indexes: null }`，使数组序列化为 `roles=a&roles=b` 而非 `roles[0]=a&roles[1]=b`。

**筛选按钮视觉反馈**：

```typescript
const hasActiveFilters = computed(() => {
  const roleFilterActive = userRoleFilters.value.length !== 2  // 默认全选
  const statusFilterActive = userStatusFilters.value.length !== 1 || userStatusFilters.value[0] !== 'active'
  return roleFilterActive || statusFilterActive
})
```

**移动端响应式布局**：

- 搜索框全宽，排序和筛选按钮各占半宽
- 排序按钮防止换行：`flex-wrap: nowrap`，缩小字体和内边距
- 地图层列表：桌面端拖拽手柄，移动端上下箭头按钮

**系统配置未保存更改保护**：

使用 `onBeforeRouteLeave` 守卫和 `beforeunload` 事件，配合深拷贝的 `originalConfig` 检测未保存更改。

### 远程日志调试

- 手机端 URL 添加 `?remote-log` 参数启用（开发环境默认启用）
- 电脑端访问 `/log-viewer` 查看实时日志
- 后端通过 WebSocket 推送日志
- 日志自动解析标签（如 `[AMap]`）

### 地图 Tooltip 定位调试（重要）

**问题现象**：高德地图在轨迹上悬停时，tooltip 显示不稳定，某些区域完全不显示。

**根本原因**：AMap 的 polyline 或其他内部元素会阻止事件冒泡，导致容器级别的 mousemove 监听器无法接收事件。

**解决方案**：在 `document` 级别监听鼠标移动，手动检查鼠标是否在地图容器内。

**实现要点**（[`AMap.vue`](frontend/src/components/map/AMap.vue)）：

```typescript
// 存储 document 监听器引用以便清理
let documentMouseMoveHandler: ((e: MouseEvent) => void) | null = null

// 在 document 级别监听（不会被内部元素阻挡）
documentMouseMoveHandler = (e: MouseEvent) => {
  if (!AMapInstance || !mapContainer.value) return

  // 检查鼠标是否在地图容器内
  const rect = mapContainer.value.getBoundingClientRect()
  const x = e.clientX - rect.left
  const y = e.clientY - rect.top

  // 如果鼠标在容器外，隐藏标记
  if (x < 0 || x > rect.width || y < 0 || y > rect.height) {
    hideMarker()
    return
  }

  // 将容器坐标转换为地图坐标
  const lngLat = AMapInstance.containerToLngLat(new AMap.Pixel(x, y))
  if (!lngLat) return
  const mouseLngLat: [number, number] = [lngLat.lng, lngLat.lat]
  handleMouseMove(mouseLngLat)
}

document.addEventListener('mousemove', documentMouseMoveHandler, true)

// 在 onUnmounted 时清理
if (documentMouseMoveHandler) {
  document.removeEventListener('mousemove', documentMouseMoveHandler, true)
  documentMouseMoveHandler = null
}
```

**其他技术要点**：

1. **使用 anchor 而非大偏移**：当上方空间不足时，使用 `top-center` 锚点（tooltip 顶部附着在点上，向下延伸），而非使用大正数偏移

2. **anchor 值**：
   - `bottom-center`（默认）：tooltip 在点上方
   - `top-center`：tooltip 在点下方

3. **计算逻辑**（[`calculateSmartOffset`](frontend/src/components/map/AMap.vue:224)）：
   ```typescript
   if (spaceAbove < tooltipHeight + 20 && spaceBelow > tooltipHeight + 20) {
     anchor = 'top-center'
     offsetY = 10
   } else {
     anchor = 'bottom-center'
     offsetY = -10
   }
   ```

4. **调用顺序**：
   ```typescript
   tooltip.setAnchor(smartOffset.anchor)  // 先设置锚点
   tooltip.setOffset(new AMap.Pixel(smartOffset.x, smartOffset.y))
   tooltip.setContent(content)
   tooltip.setPosition(new AMap.LngLat(lng, lat))
   tooltip.open(AMapInstance)
   ```

5. **content 固定宽度**：所有 tooltip 内容 div 都设置 `width: 200px`，防止 tooltip 变窄变高

### 图表与地图 Tooltip 同步修复（重要）

**问题背景**：在轨迹详情页，当鼠标在海拔/速度图表上划过时，地图上没有显示出对应的提示框。但如果直接在地图上移动鼠标，tooltip 显示正常。

**问题历史**：
- **提交 c99f0025**：图表悬停可以触发地图 tooltip，但鼠标在地图上移动时轨迹会"跑"，影响交互体验
- **提交 94a2f3c**：修复了轨迹跑动问题（通过 document 级别事件监听），但同时破坏了图表到地图的 tooltip 同步

**根本原因**：

document 级别的 `mousemove` 事件监听器会捕获**所有**鼠标移动事件，包括图表上的鼠标移动。当用户在图表上滑动时：

1. 图表触发 `showTip` 事件，调用 `mapRef.value.highlightPoint(index)` 显示 tooltip
2. 几乎同时，document 的 `mousemove` 事件被触发
3. document 事件处理函数检测到鼠标位置（此时在图表上），尝试在地图上对应位置显示 tooltip
4. 由于鼠标不在轨迹上附近，tooltip 被隐藏或位置错误

**解决方案**：在 document 级别事件监听器中，检查鼠标事件的目标元素是否来自图表容器。如果是，则跳过地图的 mousemove 处理。

**实现代码**（[`AMap.vue`](frontend/src/components/map/AMap.vue)）：

```typescript
// 在 document 级别监听鼠标移动，避免被 AMap 内部元素阻挡
documentMouseMoveHandler = (e: MouseEvent) => {
  if (!AMapInstance || !mapContainer.value) return

  // 检查鼠标事件是否来自图表容器，如果是则跳过处理
  const chartContainer = document.querySelector('.chart')
  if (chartContainer && chartContainer.contains(e.target as Node)) {
    return  // 鼠标在图表上，让图表的 tooltip 优先显示
  }

  // 检查鼠标是否在地图容器内
  const rect = mapContainer.value.getBoundingClientRect()
  const x = e.clientX - rect.left
  const y = e.clientY - rect.top

  // 如果鼠标在容器外，隐藏标记
  if (x < 0 || x > rect.width || y < 0 || y > rect.height) {
    hideMarker()
    return
  }

  // 将容器坐标转换为地图坐标
  const lngLat = AMapInstance.containerToLngLat(new AMap.Pixel(x, y))
  if (!lngLat) return
  const mouseLngLat: [number, number] = [lngLat.lng, lngLat.lat]
  handleMouseMove(mouseLngLat)
}

document.addEventListener('mousemove', documentMouseMoveHandler, true)
```

**关键技术点**：

1. **`chartContainer.contains(e.target)`**：这是 DOM API 方法，检查 `e.target`（事件源元素）是否是图表容器的后代节点
2. **事件冒泡**：当鼠标在图表上移动时，`e.target` 是图表内的某个元素（如 SVG 元素），`contains()` 返回 `true`
3. **提前返回**：一旦检测到鼠标在图表上，立即 `return`，不执行后续的地图坐标转换和 tooltip 更新
4. **选择器** `.chart`：图表容器的 class 名称，在 TrackDetail.vue 中定义为 `<div ref="chartRef" class="chart">`

**为什么不用时间戳冷却方案**：

早期尝试使用时间戳冷却（如 200ms 内忽略 document 事件）无法解决问题，因为：
- 冷却时间难以精确控制：太短仍然会冲突，太长会影响地图交互的响应速度
- 无法区分鼠标是在图表还是地图上移动
- 直接检测事件源更可靠、更精确

**涉及文件**：
- [`AMap.vue`](frontend/src/components/map/AMap.vue) - `documentMouseMoveHandler` 修改
- [`TrackDetail.vue`](frontend/src/views/TrackDetail.vue) - 图表事件监听（无需修改）

### 实时轨迹记录功能

系统支持通过 GPS Logger 等应用实时记录轨迹点，无需登录即可上传。

**GPS Logger URL 格式**：

```text
https://route.a4ding.com/api/live-recordings/log/{TOKEN}?lat=%LAT&lon=%LON&time=%TIME&alt=%ALT&spd=%SPD
```

**参数兼容性处理**：`longitude` → `lon`，`s` → `spd`

**时区处理**：数据库存储的时间不带时区，需 `point_time.replace(tzinfo=None)` 转换。WebSocket 推送时添加 `+00:00` 后缀表示 UTC 时间。

**轨迹点复用**：使用 `current_track_id` 确保所有点添加到同一 Track。

**SQLAlchemy 陷阱**：`commit()` 前调用 `refresh()` 会撤销未提交更改。

**WebSocket 实时推送**：后端通过 [`websocket.py`](backend/app/api/websocket.py) 推送新点添加事件，前端使用 [`LiveTrackWebSocket`](frontend/src/utils/liveTrackWebSocket.ts) 类接收：

- 连接端点：`/api/ws/live-recording/{recording_id}?token={TOKEN}`
- 事件类型：`connected`（连接成功）、`point_added`（新点添加）、`stats_updated`（统计更新）
- 自动重连：连接断开后 3 秒自动重连

**WebSocket 地址动态适配**：[`origin.ts`](frontend/src/utils/origin.ts) 根据用户访问地址自动判断 WebSocket 服务器地址：

| 访问地址                    | WebSocket 地址                            |
| --------------------------- | ----------------------------------------- |
| `http://localhost:5173`     | `ws://localhost:8000`                     |
| `http://192.168.x.x:5173`   | `ws://192.168.x.x:8000`                   |
| `https://route.a4ding.com` | `wss://route.a4ding.com`（不加端口）       |

判断逻辑：localhost/127.0.0.1 → 本地开发；局域网 IP（10.x、172.16-31.x、192.168.x）→ 局域网访问；其他 → 生产域名。

**轨迹详情页实时更新**：[`TrackDetail.vue`](frontend/src/views/TrackDetail.vue) 实现实时更新逻辑：

- 组件挂载时检测 `track.is_live_recording` 和 `track.live_recording_status === 'active'` 自动启动 WebSocket
- `handleNewPointAdded` 处理新点：添加到 points 数组、更新统计信息、更新结束时间
- 经过区域更新使用节流（10 秒间隔），停止时立即获取完整数据
- 组件卸载时自动断开连接并清理定时器

**实时更新状态指示器**：轨迹详情页标题前显示状态圆点：

- 🔴 **红色闪动** - 实时轨迹记录中
- 🟡 **黄色** - 连接断开/有故障

**反向代理配置**：使用 Nginx Proxy Manager 时，需为 `/api/` 路径启用 WebSocket 支持，并正确转发到后端服务。

### 实时上传状态显示功能

在轨迹列表和轨迹详情页直接显示实时上传状态，无需打开对话框即可查看最近更新时间。

**功能位置**：

1. **轨迹列表页**（[`TrackList.vue`](frontend/src/views/TrackList.vue)）：
   - 在名称列显示状态标签
   - 格式：`实时记录中 · 3 秒前更新`（合并显示）
   - 支持定时刷新（每 2 秒）

2. **轨迹详情页**（[`TrackDetail.vue`](frontend/src/views/TrackDetail.vue)）：
   - 地图右上角显示绿色状态按钮
   - 格式：`3 秒前更新`
   - 支持定时刷新（每 1 秒）

3. **实时记录对话框**：
   - 显示最近上传时间和轨迹点时间
   - 支持定时刷新（每 1 秒）

**实现要点**：

1. **相对时间格式化**（[`relativeTime.ts`](frontend/src/utils/relativeTime.ts)）：
   - `formatRelativeTime()`: "2025-01-01 11:12:13（12 分钟前）"
   - `formatTimeShort()`: "刚刚"、"10 秒前更新"、"5 分钟前更新"
   - 使用 `refreshKey` ref 强制计算属性重新计算，实现自动刷新

2. **自动刷新机制**：
   - 使用 `setInterval` 定时更新
   - 列表页标签：每 2 秒刷新时间显示
   - 列表数据：每 5 秒刷新距离、时长、爬升数据
   - 详情页状态按钮：每 1 秒刷新
   - 对话框时间：每 1 秒刷新
   - 在组件卸载时清理定时器

3. **数据获取**：
   - 后端 API 返回 `last_upload_at` 和 `last_point_time` 字段
   - 统一轨迹列表 API（`/api/tracks/unified`）包含实时记录数据
   - 单个记录状态 API（`/api/live-recordings/{id}/status`）

4. **状态标签合并**：
   - 原方案：两个独立标签（"实时轨迹记录中" + "3 秒前更新"）
   - 优化后：单个标签（"实时记录中 · 3 秒前更新"）
   - 无时间数据时：显示"实时轨迹记录中"

**后端支持**：

- [`UnifiedTrackResponse`](backend/app/schemas/track.py) 添加 `last_upload_at` 和 `last_point_time` 字段
- [`track_service.py`](backend/app/services/track_service.py) 的 `get_unified_list()` 方法填充这些字段
- [`live_recording_service.py`](backend/app/services/live_recording_service.py) 提供 `get_last_point_time()` 方法

## File Structure

```text
backend/
├── app/
│   ├── api/              # API 路由
│   ├── core/             # 配置、依赖注入、安全
│   ├── models/           # SQLAlchemy 模型
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # 业务逻辑层
│   └── gpxutil_wrapper/  # gpxutil 集成

frontend/
├── src/
│   ├── api/              # API 客户端
│   ├── components/
│   │   ├── map/          # 地图组件
│   │   └── charts/       # 图表组件
│   ├── stores/           # Pinia stores
│   ├── utils/            # 工具函数
│   └── views/            # 页面组件
```

## Common Patterns

### 添加新的 API 端点

1. 在 [`backend/app/api/`](backend/app/api/) 创建路由文件
2. 使用依赖注入：`current_user: User = Depends(get_current_user)`
3. 管理员端点：`current_user: User = Depends(get_current_admin_user)`
4. 在 [`main.py`](backend/app/main.py) 注册路由

### 添加新的前端页面

1. 在 [`frontend/src/views/`](frontend/src/views/) 创建 Vue 组件
2. 在 [`router/index.ts`](frontend/src/router/index.ts) 添加路由配置
3. 根据需要添加 `meta: { requiresAuth: true }` 或 `meta: { requiresAdmin: true }`

### Pinia Store 模式

参考 [`stores/auth.ts`](frontend/src/stores/auth.ts)：

- 使用 Composition API 风格
- State 用 `ref()`，Getters 用 `computed()`
- token 同步到 localStorage
- 初始化时自动恢复状态

## UI 规范

### Header 样式统一

所有页面的 `el-header` 使用 Element Plus 默认设置：

- **默认高度**：`60px`（不显式定义）
- **默认内边距**：`0 20px`（不显式定义）
- 不在媒体查询中覆盖这些值

**导航按钮样式**：

```css
.nav-btn {
  padding: 8px;
}

.home-nav-btn {
  margin-left: 0;
  margin-right: 12px;
}
```

### 图标统一

- **上传轨迹**：使用 `Plus` 图标（所有页面统一）
- **后退按钮**：`ArrowLeft`
- **主页按钮**：`HomeFilled`

### 用户下拉菜单顺序

**主页**（移动端）：

1. 轨迹列表
2. 上传轨迹
3. 记录实时轨迹
4. 道路标志（如配置）
5. ───────────（分割线）
6. 后台管理（管理员）
7. 退出登录

**轨迹列表**（移动端）：

1. 上传轨迹
2. 记录实时轨迹
3. ───────────（分割线）
4. 后台管理（管理员）
5. 退出登录

**轨迹详情**（移动端）：

1. 记录配置（如有）
2. 编辑
3. 导入数据
4. 导出数据
5. ───────────（分割线）
6. 后台管理（管理员）
7. 退出登录

**轨迹详情**（桌面端按钮顺序）：

1. 记录配置（如有）
2. 编辑
3. 导入数据
4. 导出数据

**后台管理**：不包含"主页"选项

**上传轨迹**：后台管理（管理员）、退出登录

### 下拉菜单分割线实现

Element Plus 没有原生的分割线组件，使用禁用的 `el-dropdown-item` 模拟：

```vue
<el-dropdown-item class="dropdown-divider" :disabled="true" />
```

```css
.dropdown-divider {
  margin: 4px 0;
  height: 1px;
  padding: 0;
  overflow: hidden;
  line-height: 0;
  background-color: var(--el-border-color-lighter);
}
```

### 经过区域树形图样式

**道路层级**：不显示图标（省、市、区仍保留 LocationFilled 图标）

**横向滚动**：当宽度不足时自动显示横向滚动条

```css
.region-tree-container :deep(.el-tree) {
  display: inline-block;
  min-width: 100%;
}
```

**节点布局**：道路名称和距离之间最小间距 24px

```css
.region-tree-node {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 24px;
  width: 100%;
  min-width: max-content;
}
```

## Important Notes

1. **密码处理**: 前端使用 `hashPassword()` 加密，后端使用 bcrypt
2. **用户复用**: 用户创建时复用已删除用户的用户名/邮箱
3. **配置 API**: 普通用户使用 `/auth/config`，管理员使用 `/admin/config`
4. **CORS**: 开发环境允许所有来源
5. **网络访问**: Vite 配置使用 `host: '0.0.0.0'` 支持局域网访问
6. **首用户管理员**: `FIRST_USER_IS_ADMIN = True`
7. **移动端 viewport**: `maximum-scale=1.0, user-scalable=no`

## Git 技巧

### 临时修改文件但不上传到 Git

```bash
# 标记文件为跳过工作树
git update-index --skip-worktree <文件路径>

# 查看被跳过的文件
git ls-files -v | grep "^S"

# 恢复文件
git update-index --no-skip-worktree <文件路径>
```

## 最新更改 (2026-01)

### DateTime 时区处理

**问题**：PostgreSQL 使用 `TIMESTAMP WITHOUT TIME ZONE`，但代码中使用了 timezone-aware datetime，导致 `can't subtract offset-naive and offset-aware datetimes` 错误。

**解决方案**：统一使用 timezone-naive 的 UTC 时间。

```python
from datetime import datetime, timezone

# 正确：获取不带时区的 UTC 时间
now = datetime.now(timezone.utc).replace(tzinfo=None)

# 错误：datetime.utcnow() 已在 Python 3.12+ 废弃
```

**涉及文件**：

- [`base.py`](backend/app/models/base.py) - `get_utc_now()` 函数
- [`config.py`](backend/app/models/config.py) - Column 默认值
- [`user_service.py`](backend/app/services/user_service.py) - 所有 `created_at`/`updated_at` 赋值
- [`track_service.py`](backend/app/services/track_service.py) - GPX 解析、填充、更新
- [`live_recording_service.py`](backend/app/services/live_recording_service.py) - 所有 datetime 操作
- [`config_service.py`](backend/app/services/config_service.py) - `expires_at` 赋值
- [`query_helper.py`](backend/app/core/query_helper.py) - 所有 `updated_at` 赋值
- [`overlay.py`](backend/app/gpxutil_wrapper/overlay.py) - 文件命名

### 地理编码失败跟踪

**功能**：填充地理信息时，跟踪失败点数量并显示给用户。

**实现要点**：

- 检查地理编码是否返回有效数据（至少有一个非空字段）
- 只有获取到有效数据时才增加进度计数
- 没有数据时增加失败计数
- 进度显示格式：`12 + 34 失败 / 90 点（0%）`，失败数量为红色

**涉及文件**：

- [`track_service.py`](backend/app/services/track_service.py) - 填充逻辑
- [`TrackDetail.vue`](frontend/src/views/TrackDetail.vue) - 进度显示
- [`track.ts`](frontend/src/api/track.ts) - 类型定义

### PostGIS 空间计算支持

**功能**：PostgreSQL + PostGIS 环境可使用高性能空间计算。

**数据库架构**：
- 使用独立扩展表 `track_points_spatial`，不影响主表
- 支持 SQLite / MySQL / PostgreSQL 全兼容
- 可为已有数据启用 PostGIS

**迁移脚本**：
- SQLite: `009_add_is_live_recording_flag.sql.sqlite`
- MySQL: `009_add_is_live_recording_flag.sql.mysql`
- PostgreSQL: `009_add_is_live_recording_flag.sql.postgresql`

**后台管理**：
- 仅 PostgreSQL 显示空间计算设置
- 未启用 PostGIS 时显示提示信息
- 支持 auto / python / postgis 三种模式

**涉及文件**：
- [`postgis_spatial.py`](backend/app/services/spatial/postgis_spatial.py)
- [`admin.py`](backend/app/api/admin.py) - `/admin/database-info` 端点
- [`Admin.vue`](frontend/src/views/Admin.vue) - 条件显示和提示
- [`config.py`](backend/app/schemas/config.py) - `spatial_backend` 字段

### 实时记录架构改进

**问题**：并发请求导致创建多条轨迹。

**解决方案**：创建 LiveRecording 时同时创建关联的 Track，建立一对一关系。

**实现要点**：
- `Track` 添加 `is_live_recording` 字段标记实时记录轨迹
- 轨迹列表过滤掉实时记录轨迹（`is_live_recording = False`）
- 简化 `add_point_to_recording` 逻辑，无需竞态条件处理

**涉及文件**：
- [`track.py`](backend/app/models/track.py) - `is_live_recording` 字段
- [`live_recording_service.py`](backend/app/services/live_recording_service.py) - `create()` 改进
- [`track_service.py`](backend/app/services/track_service.py) - `get_list()` 过滤

### 地理编码服务配置缓存

**问题**：修改配置后需要重启服务才能生效。

**解决方案**：使用配置哈希检测变化，自动重建服务实例。

```python
# 计算配置哈希
config_hash = hash(json.dumps(provider_config, sort_keys=True))

# 检查是否需要重建
needs_recreate = (
    self._geocoding_service is None or
    self._geocoding_provider != provider or
    self._geocoding_config_hash != config_hash
)
```

**涉及文件**：
- [`track_service.py`](backend/app/services/track_service.py) - `_get_geocoding_service()` 方法

### 实时轨迹点乱序处理

**问题**：WebSocket 推送点按服务器接收顺序，与实际时间顺序不一致，导致轨迹跳线。

**解决方案**：前端接收新点后按时间戳排序。

```typescript
points.value.push(newPoint)
// 按时间戳排序
points.value.sort((a, b) => {
  const timeA = a.time ? new Date(a.time).getTime() : 0
  const timeB = b.time ? new Date(b.time).getTime() : 0
  return timeA - timeB
})
```

**涉及文件**：
- [`TrackDetail.vue`](frontend/src/views/TrackDetail.vue) - `handleNewPointAdded()` 方法

### UI 修复

**地图卡片滚动条**：等待记录时隐藏地图卡片的滚动条。

```css
.map-card :deep(.el-card__body) {
  overflow: hidden !important;
}
```

### 实时记录时间字段统一

**问题**：系统中存在多套时间获取方式，导致在网络中断场景下显示不一致。

**时间字段定义**：

| 字段 | 含义 | 数据来源 | 用途 |
|------|------|---------|------|
| `last_upload_at` | LiveRecording 记录的上传时间 | `LiveRecording.last_upload_at` | 备用 |
| `last_point_time` | 最近轨迹点的 GPS 时间 | `TrackPoint.time` | 对话框"轨迹点时间" |
| `last_point_created_at` | 最近轨迹点的服务器接收时间 | `TrackPoint.created_at` | 列表卡片、对话框"最近更新"、地图"最后更新" |

**核心原则**：统一使用 `created_at`（服务器接收时间）作为"最近更新"的显示依据。

**后端修改**：

1. [`live_recording_service.py`](backend/app/services/live_recording_service.py)：
   - `get_last_point_time()`: 按 `created_at.desc()` 获取最新点，返回 `point.time`
   - `get_last_point_created_at()`: 按 `created_at.desc()` 获取最新点，返回 `point.created_at`

2. [`schemas/track.py`](backend/app/schemas/track.py)：
   - `TrackResponse` 添加 `last_upload_at`、`last_point_time`、`last_point_created_at` 字段
   - `UnifiedTrackResponse` 同样添加这三个字段

3. [`schemas/live_recording.py`](backend/app/schemas/live_recording.py)：
   - `LiveRecordingResponse` 添加 `last_point_created_at` 字段
   - `RecordingStatusResponse` 添加 `last_point_created_at` 字段

4. [`api/tracks.py`](backend/app/api/tracks.py)：
   - `/tracks/{track_id}` API 返回 `last_point_created_at`

5. [`api/live_recordings.py`](backend/app/api/live_recordings.py)：
   - 所有返回 `LiveRecordingResponse` 的 API 都返回 `last_point_created_at`
   - `get_recording_status` 返回 `last_point_created_at`

**前端修改**：

1. [`api/track.ts`](frontend/src/api/track.ts)：
   - `Track` 接口添加 `last_point_created_at` 字段
   - `UnifiedTrack` 接口添加 `last_point_created_at` 字段

2. [`api/liveRecording.ts`](frontend/src/api/liveRecording.ts)：
   - `LiveRecording` 接口添加 `last_point_created_at` 字段
   - `RecordingStatus` 接口添加 `last_point_created_at` 字段

3. [`views/TrackList.vue`](frontend/src/views/TrackList.vue)：
   - 列表卡片使用 `last_point_created_at` 显示更新时间
   - 对话框传递 `last_point_created_at` prop

4. [`views/TrackDetail.vue`](frontend/src/views/TrackDetail.vue)：
   - 地图使用 `last_point_created_at` 显示"最后更新"
   - WebSocket 更新时分别更新 `last_point_time`（GPS 时间）和 `last_point_created_at`（服务器时间）
   - 对话框传递 `last_point_created_at` prop

5. [`components/LiveRecordingDialog.vue`](frontend/src/components/LiveRecordingDialog.vue)：
   - 添加 `lastPointCreatedAt` prop
   - 对话框显示"最近更新"（使用 `lastPointCreatedAt`）和"轨迹点时间"（使用 `lastPointTime`）
   - 停止确认对话框同样使用这两个字段

**显示位置对应关系**：

| 位置 | 显示内容 | 使用字段 |
|------|---------|---------|
| 轨迹列表卡片更新时间 | "3 秒前更新" | `last_point_created_at` |
| 轨迹详情地图右上角 | "3 秒前更新" | `last_point_created_at` |
| 配置对话框"最近更新" | "2025-01-01 11:12:13（12 分钟前）" | `last_point_created_at` |
| 配置对话框"轨迹点时间" | GPS 时间 | `last_point_time` |
| 停止确认对话框 | 同配置对话框 | 同配置对话框 |

### 实时记录 point_index 处理策略

**问题背景**：

实时记录场景下，轨迹点通过网络上传，由于网络延迟等原因，点可能乱序到达服务器。而 `point_index` 字段原本设计用于表示点在轨迹中的顺序位置，这导致了根本性的架构冲突：

- **乱序到达**：点按 GPS 时间顺序生成，但按网络延迟顺序到达
- **索引冲突**：并发请求可能获取相同的 `MAX(point_index)` 值
- **距离错误**：错误的索引导致距离计算出现巨大偏差

**解决方案**：

统一使用**按时间排序**作为点的顺序依据，`point_index` 字段仅作为数据库存储字段保留：

1. **查询排序**：所有查询都使用 `.order_by(TrackPoint.time.asc(), TrackPoint.created_at.asc())`
2. **显示导出**：前端显示和 CSV/XLSX 导出使用枚举索引 `enumerate(points)` 而非 `point_index`
3. **修复脚本**：轨迹结束时运行 `fix_point_index.py` 重排索引

**涉及文件**：

- [`overlay.py`](backend/app/gpxutil_wrapper/overlay.py) - 生成信息覆盖层时按时间排序
- [`track_service.py`](backend/app/services/track_service.py) - 导出、高程同步等使用时间排序
- [`TrackDetail.vue`](frontend/src/views/TrackDetail.vue) - 显示使用数组索引
- [`track.ts`](frontend/src/api/track.ts) - 接口添加注释说明

**自动修复**：

实时记录停止时，系统会自动调用 [`LiveRecordingService.fix_point_index()`](backend/app/services/live_recording_service.py) 修复 `point_index`：

1. 按 GPS 时间顺序重新分配索引（0, 1, 2, ...）
2. 重新计算轨迹距离、时长、爬升/下降统计
3. 记录修复日志

**注意事项**：

- `point_index` 字段仍保留在数据库中，用于 GPX 导入等场景
- 实时记录期间的 `point_index` 可能不准确，但停止时会自动修复
- 所有新代码查询轨迹点时，必须按时间排序而非 `point_index`
