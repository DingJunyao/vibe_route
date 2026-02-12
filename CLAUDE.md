# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Vibe Route** 是一个基于 [gpxutil](https://github.com/DingJunyao/gpxutil) 构建的全栈 Web 轨迹管理系统。用户可以上传 GPX 文件，系统会解析轨迹数据，进行坐标转换（WGS84/GCJ02/BD09）、地理编码填充，并在地图上可视化展示。

## Development

对于 Python，我用的是 Anaconda，环境是 vibe_route。所有与 Python 相关的操作都要保证切换到这个环境。

用的是什么数据库，看后端的 .env。

在调试的时候，会打开开发人员工具。可以使用 Chrome devtools MCP 获取其中的报错、网络分析、性能分析、DOM 结构等信息。

开发者使用的是 Edge。如果找不到，要求开发者运行以下命令以启用带远程调试功能的 Edge：

```powershell
Stop-Process -Name msedge -Force; Start-Sleep -Milliseconds 500; Start-Process "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" -ArgumentList "--remote-debugging-port=9222"
```

你可以通过添加调试日志、使用 Chrome 开发者工具 MCP 等方式辅助处理问题。

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

### 海报生成功能

支持将轨迹导出为海报图片，提供前端和后端两种生成方式。

**功能特性**：

- **两种生成方式**：
  - 前端生成：浏览器本地生成，使用 iframe + html2canvas 截图
  - 后端生成：服务器使用 Playwright 截图，适合复杂场景
- **预览功能**：前端生成支持预览，确认无误后再导出
- **多模板支持**：极简、简洁、丰富、地理四种模板
- **尺寸预设**：竖版/横版 1080P/4K
- **地图缩放**：100%-200% 可调，放大地图要素适应高分辨率

**实现架构**：

**前端生成**（[`frontendPosterGenerator.ts`](frontend/src/utils/frontendPosterGenerator.ts)）：
1. 创建隐藏 iframe 加载 [`TrackMapOnly.vue`](frontend/src/views/TrackMapOnly.vue)
2. 等待 `window.mapReady === true` 信号
3. html2canvas 截取 `.map-only-page`
4. Canvas 合成海报（背景 + 地图 + 信息覆盖层 + 水印）
5. toBlob() → 下载

**后端生成**（[`poster_service.py`](backend/app/services/poster_service.py)）：
1. Playwright 访问 `/tracks/{id}/map-only` 页面
2. 等待 `window.mapReady === true` 信号
3. 使用 clip 参数截取指定区域
4. PIL 合成海报

**关键实现要点**：

1. **TrackMapOnly.vue 显式尺寸支持**：
   - 通过 URL 参数 `width`/`height` 传递目标尺寸
   - 避免隐藏 iframe 中 `vw/vh` 计算不正确的问题

2. **地图缩放等待时间**：
   - 动态计算：`baseWait + (mapScale - 100) * multiplier`
   - TrackMapOnly.vue: 2000 + scale*30 + 1000
   - Frontend generator: 1000 + scale*50
   - Backend: 2000 + scale*50

3. **截图元素选择**：
   - 截取 `.map-only-page`（整个页面）
   - 不截取 `.map-wrapper-container`（有 transform，html2canvas 处理不正确）

4. **Leaflet Canvas 渲染模式**：
   - 海报生成模式下设置 `window.__posterMode = true`
   - Leaflet 检测到该标志时启用 `preferCanvas: true`
   - html2canvas 无法正确处理 Leaflet SVG 轨迹，Canvas 模式无偏移问题

5. **百度地图 CORS 问题**：
   - 在 TrackMapOnly.vue 中隐藏百度地图 logo（`.BMap_cpyCtrl`, `.anchorBL`）
   - 避免 html2canvas 尝试加载无 CORS 头的图片

6. **后端 Playwright 截图策略**：
   - 使用原始 viewport 大小（如 1080x1920）
   - 使用 `clip` 参数截取缩放后的完整区域
   - `device_scale_factor: 1` 避免与 CSS scale 叠加

7. **预览状态管理**：
   - `canPreview` 计算属性：仅前端模式且未生成时启用
   - 配置变更时清除预览（`onConfigChange` → `clearPreview`）
   - 生成方式切换时也清除预览

**涉及文件**：
- [`frontendPosterGenerator.ts`](frontend/src/utils/frontendPosterGenerator.ts) - 前端海报生成器
- [`PosterExportDialog.vue`](frontend/src/components/PosterExportDialog.vue) - 海报导出对话框
- [`TrackMapOnly.vue`](frontend/src/views/TrackMapOnly.vue) - 专用地图页面
- [`poster_service.py`](backend/app/services/poster_service.py) - 后端海报服务
- [`LeafletMap.vue`](frontend/src/components/map/LeafletMap.vue) - Canvas 渲染模式支持

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

### DataV GeoJSON 行政区划导入

**功能**：从阿里 DataV GeoAtlas API 获取行政区划数据，支持在线更新和压缩包上传。

**数据源**：
- API 地址：`https://geo.datav.aliyun.com/areas_v3/bound`
- 数据格式：GeoJSON，包含省/市/区县三级行政区划

**坐标系处理**：
- **DataV 在线数据**：使用 GCJ02 坐标系（火星坐标），导入时自动转换为 WGS84
- **压缩包数据**：假设为 WGS84 坐标系（用户需确认），不进行转换
- 边界框和中心点坐标都会进行相应的坐标转换

**导入模式**：
- **全量更新**：获取全国所有行政区划数据
- **仅更新边界**：只更新边界框数据，不修改基础信息
- **按省份更新**：选择性更新指定省份

**数据库字段扩展**：
- `center_lon`/`center_lat`：行政区划中心点坐标（浮点数，WGS84）
- `children_num`：子级行政区划数量

**特殊行政区划处理**：
- **直辖市**（110000、120000、310000、500000）：区县直接归属省级
- **不设区地级市**（441900 东莞、442000 中山、460400 儋州、620200 嘉峪关）：保留市级，不获取镇级
- **省辖县级单位**（如济源市）：`childrenNum=0` 的 city 级存为 area

**本地反向地理编码修复**：
- 正确处理只查询到 city 级别的不设区地级市情况
- 按中心距离选择最近的区域（当有多个匹配时）

**后端服务**：
- [`DataVGeoService`](backend/app/services/datav_geo_service.py)：从 DataV API 获取数据
- [`AdminDivisionImportService.import_from_datav_online()`](backend/app/services/admin_division_import_service.py)：在线导入
- [`AdminDivisionImportService.import_from_geojson_archive()`](backend/app/services/admin_division_import_service.py)：压缩包导入

**API 端点**：
- `GET /admin/admin-divisions/status`：获取行政区划数据状态
- `POST /admin/admin-divisions/import/online`：在线导入（后台任务）
- `POST /admin/admin-divisions/import/upload`：上传压缩包导入
- `GET /admin/admin-divisions/import/progress/{task_id}`：获取导入进度
- `GET /admin/admin-divisions/provinces`：获取省份列表

**前端 UI**（[`Admin.vue`](frontend/src/views/Admin.vue)）：
- 导入模式选择（全量/边界/按省份）
- 省份多选（按省份模式）
- 强制覆盖选项
- 在线更新/上传压缩包按钮
- 进度条显示
- 当前数据状态显示

**废弃方法**：
- `import_from_sqlite()`：已标记为 DEPRECATED，建议使用新的 DataV 导入方法

## 最新更改 (2026-02)

### 多边形几何字段与 Shapely 精确地理匹配

**问题背景**：不使用 PostGIS 时，地理信息填充使用矩形边界框（min_lat, max_lat, min_lon, max_lon）进行查询，导致边界附近的点匹配不准确。

**解决方案**：添加 `geometry` 字段存储完整的 GeoJSON 多边形数据，使用 shapely 进行精确的多边形包含判断。

**数据库变更**：
- `AdminDivision` 模型添加 `geometry TEXT` 字段存储 GeoJSON 多边形
- 迁移脚本：`012_add_geometry_to_admin_divisions.*`（支持 SQLite/MySQL/PostgreSQL）

**DataV 导入**：
- 在线导入：自动保存完整 geometry（含 GCJ02→WGS84 坐标转换）
- 压缩包导入：保存原始 geometry（假设为 WGS84）

**本地反向地理编码**（[`local_geocoding.py`](backend/app/gpxutil_wrapper/local_geocoding.py)）：
- 先用边界框快速过滤候选区域
- 再用 shapely `polygon.contains(point)` 精确匹配
- 无 geometry 的区域跳过（不回退到边界框判断）

**批量查询优化**：
- `get_batch_candidates()`: 一次查询获取所有候选区域
- `find_division_for_point()`: 内存中进行 shapely 判断
- 减少数据库访问次数

**涉及文件**：
- [`admin_division.py`](backend/app/models/admin_division.py) - `geometry` 字段
- [`admin_division_import_service.py`](backend/app/services/admin_division_import_service.py) - 导入时保存 geometry
- [`local_geocoding.py`](backend/app/gpxutil_wrapper/local_geocoding.py) - shapely 判断逻辑

### 省辖县级行政单位分类修复

**问题**：仙桃、潜江、天门、济源等省直辖县级行政单位被错误分类为 `city` 级别，导致层级结构混乱。

**解决方案**：

**不设区地级市**（仅 4 个硬编码）：
- 东莞（441900）、中山（442000）
- 儋州（460400）、嘉峪关（620200）
- 保留为 `city` 级别，`children_num = 0`

**省辖县级行政单位**：
- 仙桃、潜江、天门、济源等（`level=3` 且 `childrenNum=0`）
- 分类为 `area` 级别（等同于 district）
- `city_code` 为空（无上级市）
- 正常区县（`level=4`）保留 `city_code`

**处理逻辑**（[`_import_legacy_feature`](backend/app/services/admin_division_import_service.py)）：
```python
is_province_administered = (
    level == 3 and
    adcode not in NON_DISTRICT_CITIES and
    children.get("num", 0) == 0
)

if is_province_administered:
    level_type = "area"
    city_code = None
else:
    # 正常分类逻辑...
```

**涉及文件**：
- [`admin_division_import_service.py`](backend/app/services/admin_division_import_service.py) - `NON_DISTRICT_CITIES` 常量

### 省份名称后缀映射

**问题**：压缩包中的省份名称不带后缀（如"北京"而非"北京市"），与数据库格式不一致。

**解决方案**：解析压缩包内的 `地图数据目录.txt`，建立省份代码到完整名称的映射。

**文件格式**（`backend/data/area_data/map/地图数据目录.txt`）：
```
--- 110000 北京市 ---
--- 120000 天津市 ---
...
```

**解析逻辑**（[`_parse_province_name_mapping`](backend/app/services/admin_division_import_service.py)）：
- 使用 `temp_dir.rglob("*.txt")` 递归搜索文件
- 正则提取代码和名称：`(\d+)\s+(.+)`
- 仅对 `level=2`（省级）应用映射

**处理顺序**（[`import_from_geojson_archive`](backend/app/services/admin_division_import_service.py)）：
1. 解压压缩包
2. 递归解析省份名称映射
3. 导入 GeoJSON 特性（应用映射）

**涉及文件**：
- [`admin_division_import_service.py`](backend/app/services/admin_division_import_service.py) - `_parse_province_name_mapping()` 方法

### 层级构建修复

**问题**：当只匹配到省级记录时（如省直辖县级行政单位），`_build_hierarchy` 返回空的 city/area，导致地理信息缺失。

**解决方案**（[`_build_hierarchy`](backend/app/gpxutil_wrapper/local_geocoding.py)）：
```python
# 只有 province 时，直接填充 province
if province and not city and not area:
    return {
        "province": province,
        "province_code": province_code,
        "city": None,
        "city_code": None,
        "area": None,
        "area_code": None
    }
```

### PostGIS 几何数据同步

**背景**：
- `admin_divisions.geometry` 字段存储 GeoJSON 多边形（用于 shapely 判断）
- `admin_divisions_spatial.geom` 字段存储 PostGIS 几何（用于 PostGIS 空间查询）
- 两套数据独立存储，需要手动同步

**问题**：当用户在后台管理中切换 `spatial_backend` 为 `postgis` 时，不会自动同步 PostGIS 几何数据。

**解决方案**：提供手动同步功能，从 `geometry` 字段同步到 PostGIS 空间表。

**后端 API**：
- `GET /admin/admin-divisions/postgis-status`：获取同步状态（几何数据数、PostGIS 数、需同步数）
- `POST /admin/admin-divisions/sync-postgis`：触发同步任务（后台执行）

**实现逻辑**（[`AdminDivisionImportService.sync_postgis_from_geometry`](backend/app/services/admin_division_import_service.py)）：
1. 检查 PostgreSQL + PostGIS 环境是否可用
2. 确保 `admin_divisions_spatial` 表存在
3. 遍历所有有 `geometry` 的记录
4. 使用 `ST_GeomFromGeoJSON` 将 GeoJSON 转换为 PostGIS 几何
5. 使用 `ON CONFLICT ... DO UPDATE` 处理重复记录

**前端功能**（[`Admin.vue`](frontend/src/views/Admin.vue)）：
- 在"空间计算设置"区域显示同步状态
- "同步到 PostGIS"按钮（当需同步数 > 0 时启用）
- 进度条显示同步进度
- 自动轮询任务状态，完成后刷新同步状态

**涉及文件**：
- [`admin_division_import_service.py`](backend/app/services/admin_division_import_service.py) - `sync_postgis_from_geometry()` 方法
- [`admin.py`](backend/app/api/admin.py) - API 端点
- [`admin.ts`](frontend/src/api/admin.ts) - API 客户端
- [`Admin.vue`](frontend/src/views/Admin.vue) - UI 和交互

## 最新更改 (2026-02 地理信息编辑器)

### 地理信息编辑器刻度条改进

**问题背景**：地理信息编辑页面的时间刻度条存在多个问题：
1. 缺少放大倍数显示
2. 左侧边缘刻度缺失（放大时更明显）
3. 刻度时间与实际点时间不匹配
4. 主刻度标签重叠（1x 缩放时）
5. 主刻度之间次刻度和三级刻度数量不正确

**解决方案**：

**1. 放大倍数显示** ([`GeoEditor.vue`](frontend/src/views/GeoEditor.vue))

添加缩放倍数显示，位于缩放按钮左侧：

```typescript
const zoomLevelText = computed(() => {
  const range = geoEditorStore.zoomEnd - geoEditorStore.zoomStart
  const level = Math.round(1 / range)
  if (level >= 1000) {
    return `${(level / 1000).toFixed(1)}kx`
  }
  return `${level}x`
})
```

**2. 刻度生成逻辑重构** ([`TimelineScale.vue`](frontend/src/components/geo-editor/TimelineScale.vue))

- **边界扩展**：基于可视区域点的实际时间扩展边界，确保左侧有刻度
- **点索引定位**：使用 `findPointIndexByTime` 函数进行基于点索引的定位，保证刻度时间与点时间一致
- **级别去重**：实现基于级别的去重机制，不同级别使用不同最小间距
  - 主刻度：5%
  - 次刻度：1%
  - 三级刻度：0.2%

**3. 次刻度和三级刻度数量修复**

改为按点索引生成刻度位置，而非按时间：

```typescript
// 计算对应的点索引间隔
const pointsPerMillisecond = totalPoints / totalDuration
const majorPointInterval = Math.round(majorInterval * pointsPerMillisecond)
const halfMajorPointInterval = Math.round(majorPointInterval / 2)
const tenthMajorPointInterval = Math.round(majorPointInterval / 10)

// 按点索引生成刻度，与时间边界对齐
const alignedTime = Math.floor(firstVisibleTime / majorInterval) * majorInterval
const alignedStartIndex = findPointIndexByTime(alignedTime)
```

### Leaflet 地图坐标偏移修复

**问题背景**：地理信息编辑页面中，天地图和 OSM 的轨迹有偏移，但轨迹详情页正常。其他地图（高德、百度、腾讯）都没有问题。

**根本原因**：后端 `geo_editor` API 的 `TrackPointGeoData` schema 缺少 `latitude_wgs84` 和 `longitude_wgs84` 字段，且 service 代码中 `latitude` 和 `longitude` 使用的是 GCJ02 坐标（与文档注释不符）。

**解决方案**：

1. **Schema 修复** ([`geo_editor.py`](backend/app/schemas/geo_editor.py))：添加 `latitude_wgs84` 和 `longitude_wgs84` 字段

2. **Service 修复** ([`geo_editor_service.py`](backend/app/services/geo_editor_service.py))：`latitude` 和 `longitude` 现在使用 WGS84 坐标（与文档一致）

```python
latitude=p.latitude_wgs84,  # WGS84
longitude=p.longitude_wgs84,  # WGS84
```

3. **LeafletMap 坐标处理** ([`LeafletMap.vue`](frontend/src/components/map/LeafletMap.vue))：
   - 天地图使用 WGS84 坐标（leaflet.chinatmsproviders 会自动转换）
   - OSM 使用 WGS84 坐标
   - 高德/腾讯使用 `latitude_gcj02`/`longitude_gcj02`
   - 百度使用 `latitude_bd09`/`longitude_bd09`

**涉及文件**：
- [`frontend/src/views/GeoEditor.vue`](frontend/src/views/GeoEditor.vue) - 放大倍数显示
- [`frontend/src/components/geo-editor/TimelineScale.vue`](frontend/src/components/geo-editor/TimelineScale.vue) - 刻度生成重构
- [`frontend/src/components/map/LeafletMap.vue`](frontend/src/components/map/LeafletMap.vue) - 坐标处理
- [`backend/app/schemas/geo_editor.py`](backend/app/schemas/geo_editor.py) - Schema 字段添加
- [`backend/app/services/geo_editor_service.py`](backend/app/services/geo_editor_service.py) - Service 坐标修复

### 地理信息编辑器空块操作修复

**问题背景**：

1. 移动空块时，相邻空块被错误删除
2. 调整空块大小时，新空块错误延伸到时间轴尾部

**根本原因**：

1. `shouldAutoMerge` 函数对空块返回 `true`（`null === null`），导致空块自动合并
2. `adjustOverlappingEmptyBlocks` 函数未区分移动和调整大小操作，resize 时错误扩展邻居

**解决方案**：

**1. 空块不自动合并** ([`geoEditor.ts`](frontend/src/stores/geoEditor.ts))

修改 `shouldAutoMerge` 函数，对空块返回 `false`：

```typescript
function shouldAutoMerge(
  segment: TrackSegment,
  adjacent: TrackSegment | null
): boolean {
  if (!adjacent) return false
  // 空块不自动合并
  if (!segment.value || !adjacent.value) return false
  return segment.value === adjacent.value && segment.valueEn === adjacent.valueEn
}
```

**2. 空块 resize 操作特殊处理** ([`geoEditor.ts`](frontend/src/stores/geoEditor.ts))

在 `adjustOverlappingEmptyBlocks` 函数中添加操作类型检测：

```typescript
// 检测是否是 resize 操作（只有一边改变）
const isResize = oldStart === newStart || oldEnd === newEnd
const isLeftResize = oldEnd === newEnd && oldStart !== newStart  // 调整左边界
const isRightResize = oldStart === newStart && oldEnd !== newEnd  // 调整右边界
```

**resize 时的处理**：

- 不扩展邻居（这是移动操作的逻辑）
- 创建新空块填补被缩小部分
- 调整右边界缩小时：在 `(newEnd+1, oldEnd)` 创建新空块
- 调整左边界缩小时：在 `(oldStart, newStart-1)` 创建新空块

**涉及文件**：

- [`frontend/src/stores/geoEditor.ts`](frontend/src/stores/geoEditor.ts) - `shouldAutoMerge` 和 `adjustOverlappingEmptyBlocks` 函数

### 地理信息编辑器撤销/重做修复

**问题背景**：

1. 移动块、改变块大小无法撤销
2. 缺少键盘快捷键（Ctrl+Z 撤销、Ctrl+Y 重做）

**根本原因**：

1. `EditHistory['action']` 类型定义不完整，缺少 `'move'` 类型
2. 前端未绑定键盘快捷键

**解决方案**：

**1. 扩展历史记录操作类型** ([`geoEditor.ts`](frontend/src/stores/geoEditor.ts))

```typescript
export interface EditHistory {
  // ...
  action: 'edit' | 'resize' | 'move'  // 添加 'move' 类型
  // ...
}
```

**2. 添加键盘快捷键** ([`GeoEditor.vue`](frontend/src/views/GeoEditor.vue))

在 `handleGlobalKeydown` 中添加：

```typescript
// Ctrl+Z 撤销 / Ctrl+Y 重做
if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey) {
  if (e.key === 'z') {
    e.preventDefault()
    if (geoEditorStore.canUndo) {
      geoEditorStore.undo()
      ElMessage.success('已撤销')
    }
    return
  }
  if (e.key === 'y') {
    e.preventDefault()
    if (geoEditorStore.canRedo) {
      geoEditorStore.redo()
      ElMessage.success('已重做')
    }
    return
  }
}
```

**3. 撤销/重做逻辑**

```typescript
// 撤销：historyIndex--，恢复到 history[historyIndex].after
function undo() {
  if (!canUndo.value) return
  historyIndex.value--
  restoreState(history.value[historyIndex.value].after)
}

// 重做：historyIndex++，恢复到 history[historyIndex].after
function redo() {
  if (!canRedo.value) return
  historyIndex.value++
  restoreState(history.value[historyIndex.value].after)
}
```

#### 历史记录结构

```text
history[0]: 初始状态 (before = after = 初始状态)
history[1]: resize 操作 (before = 初始状态, after = resize 后)
history[2]: move 操作  (before = resize 后, after = move 后)
```

从 history[2] 撤销 → historyIndex = 1 → 恢复到 history[1].after（resize 后的状态）

**涉及文件**：

- [`frontend/src/stores/geoEditor.ts`](frontend/src/stores/geoEditor.ts) - 类型定义、undo/redo 函数
- [`frontend/src/views/GeoEditor.vue`](frontend/src/views/GeoEditor.vue) - 键盘快捷键绑定

## 最新更改 (2026-02 地图缩放)

### 海报导出地图缩放

**功能背景：** 在导出海报时，地图需要根据 CSS scale（150% 或 200%）调整缩放级别，使轨迹在放大后占据容器的 90%。

**核心原理：**

1. CSS `transform: scale()` 放大的是地图显示，不改变容器尺寸
2. 目标：边界框在放大后占容器 90%，即放大前应占 `90% / scale`
3. 公式：`targetContentWidth = containerWidth * 0.9 / scale`

### 各地图组件的缩放方式

#### 高德地图 (AMap)

```typescript
// 1. 先 setFitView 让地图自动适应边界框
AMapInstance.setFitView(null, false, [padding, padding, padding, padding])

// 2. 延迟后获取当前 zoom 和像素数据
setTimeout(() => {
  const zoomAfter = AMapInstance.getZoom()

  // 3. 将边界框经纬度转换为容器像素
  const swPixel = AMapInstance.lngLatToContainer(new AMap.LngLat(minLng, minLat))
  const nePixel = AMapInstance.lngLatToContainer(new AMap.LngLat(maxLng, maxLat))
  const currentPixelWidth = Math.abs(nePixel.x - swPixel.x)
  const currentPixelHeight = Math.abs(nePixel.y - swPixel.y)

  // 4. 计算目标像素尺寸
  const scale = mapScale / 100
  const targetContentWidth = containerWidth * 0.9 / scale
  const targetContentHeight = containerHeight * 0.9 / scale

  // 5. 使用对数公式计算 zoom 调整量
  const zoomDelta = Math.log2(targetContentWidth / currentPixelWidth)
  const targetZoom = zoomAfter + zoomDelta

  AMapInstance.setZoom(targetZoom)
}, 500)
```

**API：**
- 坐标转像素：`lngLatToContainer(LngLat)`
- Zoom 范围：3-20

#### 百度地图 (BMap)

百度地图有两个版本：**GL 版本**（WebGL）和 **Legacy 版本**（v3.0 JavaScript API）。海报导出使用 Legacy 版本以避免 WebGL 兼容性问题。

**版本检测与兼容：**

```typescript
// 判断是否使用 Legacy 版本（通过 defaultLayerId prop）
const isLegacyMode = computed(() => props.defaultLayerId === 'baidu_legacy')

// 获取对应版本的 API 命名空间
const BMapAPI = computed(() => {
  return isLegacyMode.value ? (window as any).BMap : (window as any).BMapGL
})

// 创建 Point 对象（兼容两个版本）
function createPoint(lng: number, lat: number): any {
  const BMapClass = isLegacyMode.value ? (window as any).BMap : (window as any).BMapGL
  return new BMapClass.Point(lng, lat)
}
```

**版本差异对照表：**

| 功能 | GL 版本 | Legacy 版本 |
|------|---------|-------------|
| API 加载 | `type=webgl` | `v=3.0` |
| 全局对象 | `BMapGL` | `BMap` |
| 缩放控件 | `ZoomControl` | `NavigationControl` |
| 滚轮缩放 | `enableScrollWheelZoom(true)` | 需手动添加事件监听器 |
| getBounds | 返回 `.sw`/`.ne` 属性 | 需调用 `getSouthWest()`/`getNorthEast()` |
| 像素转换 | `pointToOverlayPixel()` | `pointToPixel()` |

**GL 版本缩放方式：**

```typescript
// 1. 先 setViewport 让地图自动适应边界框
BMapInstance.setViewport(bounds, { margins: [padding, padding, padding, padding] })

// 2. 延迟后获取当前 zoom 和像素数据
setTimeout(() => {
  const zoomAfter = BMapInstance.getZoom()

  // 3. 将边界框经纬度转换为容器像素
  const swPixel = BMapInstance.pointToPixel(new BMapGL.Point(minLng, minLat))
  const nePixel = BMapInstance.pointToPixel(new BMapGL.Point(maxLng, maxLat))
  const currentPixelWidth = Math.abs(nePixel.x - swPixel.x)
  const currentPixelHeight = Math.abs(nePixel.y - swPixel.y)

  // 4. 计算目标像素尺寸
  const scale = mapScale / 100
  const targetContentWidth = containerWidth * 0.9 / scale
  const targetContentHeight = containerHeight * 0.9 / scale

  // 5. 使用对数公式计算 zoom 调整量
  const zoomDelta = Math.log2(targetContentWidth / currentPixelWidth)
  const targetZoom = zoomAfter + zoomDelta

  BMapInstance.setZoom(targetZoom)
}, 500)
```

**Legacy 版本缩放方式（精细策略）：**

Legacy 版本使用"先测量后调整"的几何方法，并采用智能舍入策略处理边界情况：

```typescript
// 1. 先设置 zoom=12 建立基准测量环境
BMapInstance.setZoom(12)

// 2. 等待缩放完成后测量边界框像素
setTimeout(() => {
  const swPixel = BMapInstance.pointToPixel(new BMap.Point(minLng, minLat))
  const nePixel = BMapInstance.pointToPixel(new BMap.Point(maxLng, maxLat))
  const currentPixelWidth = Math.abs(nePixel.x - swPixel.x)
  const currentPixelHeight = Math.abs(nePixel.y - swPixel.y)

  // 3. 计算 zoom delta
  const scale = mapScale / 100
  const targetContentWidth = containerWidth * 0.9 / scale
  const targetContentHeight = containerHeight * 0.9 / scale
  const widthZoomDelta = Math.log2(targetContentWidth / currentPixelWidth)
  const heightZoomDelta = Math.log2(targetContentHeight / currentPixelHeight)
  const zoomDelta = Math.min(widthZoomDelta, heightZoomDelta)

  // 4. 计算 zoom 并应用精细策略
  const rawZoom = 12 + zoomDelta
  let targetZoom = Math.floor(rawZoom)

  // 精细策略：当小数部分 ≥ 0.9 时，尝试 zoom+1 并验证边界框是否在容器 95% 内
  const fractionalPart = rawZoom - targetZoom
  if (fractionalPart >= 0.9 && targetZoom < 18) {
    const nextZoom = targetZoom + 1
    const zoomRatio = Math.pow(2, nextZoom - 12)
    const nextPixelWidth = currentPixelWidth * zoomRatio
    const nextPixelHeight = currentPixelHeight * zoomRatio

    // 验证边界框在容器的 95% 内（允许略微超出）
    const fitsWidth = nextPixelWidth <= targetContentWidth / 0.95
    const fitsHeight = nextPixelHeight <= targetContentHeight / 0.95

    if (fitsWidth && fitsHeight) {
      targetZoom = nextZoom
    }
  }

  BMapInstance.setZoom(Math.max(3, Math.min(18, targetZoom)))
}, 400)
```

**精细策略原理：**

- 使用 `Math.floor()` 确保边界框不会超出视野（保守策略）
- 当小数部分 ≥ 0.9 时（如 9.96、11.97），尝试提升 1 级
- 验证提升后的 zoom 是否仍在容器 95% 范围内
- 如果验证通过，使用更高的 zoom，获得更好的显示效果

**测试覆盖：** 12 种场景（横屏/竖屏 × 竖向/横向 × 100%/150%/200%）全部合格。

**涉及文件：**
- [`frontend/src/components/map/BMap.vue`](frontend/src/components/map/BMap.vue) - 百度地图组件
- [`frontend/src/components/map/UniversalMap.vue`](frontend/src/components/map/UniversalMap.vue) - 传递 `defaultLayerId` prop

**API：**
- 坐标转像素：`pointToPixel(Point)`（Legacy）/ `pointToOverlayPixel()`（GL）
- Zoom 范围：3-18（Legacy）、3-20（GL）

#### 腾讯地图 (TencentMap)

```typescript
// 1. 先 fitBounds 让地图自动适应边界框
TMapInstance.fitBounds(boundsObj, { padding })

// 2. 延迟后获取当前 zoom 和像素数据
setTimeout(() => {
  const zoomAfter = TMapInstance.getZoom()

  // 3. 将边界框经纬度转换为容器像素
  const swPixel = TMapInstance.projectToContainer(sw)
  const nePixel = TMapInstance.projectToContainer(ne)
  const currentPixelWidth = Math.abs(nePixel.x - swPixel.x)
  const currentPixelHeight = Math.abs(nePixel.y - swPixel.y)

  // 4. 计算目标像素尺寸
  const scale = mapScale / 100
  const targetContentWidth = containerWidth * 0.9 / scale
  const targetContentHeight = containerHeight * 0.9 / scale

  // 5. 使用对数公式计算 zoom 调整量
  const zoomDelta = Math.log2(targetContentWidth / currentPixelWidth)
  const targetZoom = zoomAfter + zoomDelta

  TMapInstance.setZoom(targetZoom)
}, 500)
```

**API：**
- 坐标转像素：`projectToContainer(LatLng)`
- Zoom 范围：3-20

#### Leaflet 地图

**问题：** Leaflet 在 fitBounds 后会触发多次 zoom 事件，延迟获取时 zoom 可能已经变化，且 `latLngToContainerPoint` 在高 zoom 时可能返回异常值（如负坐标或超大值）。

**解决方案：** 放弃 fitBounds + 像素转换的方式，改用**直接地理范围计算**。

**核心公式：**

```typescript
// 1. 计算边界框的地理范围（公里）
const lngSpan = bounds.getEast() - bounds.getWest()
const latSpan = bounds.getNorth() - bounds.getSouth()
const boundsKmWidth = lngSpan * 111 * Math.cos(centerLat * Math.PI / 180)
const boundsKmHeight = latSpan * 111
const maxKm = Math.max(boundsKmWidth, boundsKmHeight)

// 2. 考虑 CSS scale，计算目标视野
const scale = mapScale / 100
const targetKm = maxKm / 0.9 / scale

// 3. 根据方向匹配选择维度
const isHorizontalMatch = isTrackHorizontal && isContainerHorizontal
const relevantDim = isHorizontalMatch ? max(containerWidth, containerHeight) : min(containerWidth, containerHeight)

// 4. 计算 zoom（Leaflet：zoom=N 时，256px ≈ 40075km / 2^N）
const kmPerPixel = targetKm / relevantDim
const targetZoom = Math.round(Math.log2(40075 / (256 * kmPerPixel))) + offset

// 5. 直接设置中心和 zoom，不用 fitBounds
map.setView([center.lat, center.lng], targetZoom, { animate: false })
```

**偏移量计算：**

```typescript
// 计算宽高比的"极端程度"：ratio=2.5 时为 0，ratio≥6 时为 1
const ratio = boundsKmWidth / (boundsKmHeight || 1)
const extremeRatio = ratio > 1 ? ratio : (1 / ratio)
const extremeFactor = Math.min(1, Math.max(0, (extremeRatio - 2.5) / 3.5))

// 基础偏移：横向匹配用 maxDim 时只需 -1，其他用 minDim 需要 -2
// 加上极端程度调整：极端时额外 -1
const baseOffset = isHorizontalMatch ? -1 : -2
const offset = baseOffset - Math.round(extremeFactor)
```

**规则总结：**

| 场景 | 使用维度 | 基础偏移 | 极端宽高比 | 最终偏移 |
|------|----------|----------|-----------|----------|
| 横屏+横向 | maxDim | -1 | 额外 -1 | -2 或 -3 |
| 竖屏+竖向 | minDim | -2 | 额外 -1 | -3 或 -4 |
| 其他不匹配 | minDim | -2 | 额外 -1 | -3 或 -4 |

**调试函数：** 可在浏览器控制台使用 `setMapZoom(zoom)` 直接设置缩放级别。

**滚轮缩放设置：**

```typescript
L.map(mapContainer, {
  zoomSnap: 1,               // 缩放级别为整数
  wheelPxPerZoomLevel: 240,   // 滚轮每 240 像素改变一个级别
})
```

**API：**
- 坐标转像素：`latLngToContainerPoint(LatLng)`
- Zoom 范围：1-20（天地图）、0-20（OSM）

**涉及文件：**
- [`frontend/src/components/map/AMap.vue`](frontend/src/components/map/AMap.vue) - 高德地图缩放
- [`frontend/src/components/map/BMap.vue`](frontend/src/components/map/BMap.vue) - 百度地图缩放
- [`frontend/src/components/map/TencentMap.vue`](frontend/src/components/map/TencentMap.vue) - 腾讯地图缩放
- [`frontend/src/components/map/LeafletMap.vue`](frontend/src/components/map/LeafletMap.vue) - Leaflet 地图缩放

---

## 百度地图海报生成问题（浏览器端）

### 问题描述

百度地图 Legacy 版本在浏览器端使用 html2canvas 生成海报时，轨迹线无法正确捕获。

### 根本原因

1. **DOM 渲染方式**：百度地图 Legacy 版本使用 DOM 渲染
   - 地图瓦片：`<img>` 元素（来自 `apimaponline*.bdimg.com`）
   - 轨迹线：SVG 元素（位于深层 DOM 结构中）

2. **html2canvas 限制**：
   - 无法正确捕获 SVG 轨迹元素
   - 百度地图瓦片图片没有正确的 CORS 头，导致 canvas 污染

3. **CSS transform scale 影响**：
   - `.map-wrapper-container` 使用 `transform: scale(2)` 实现视觉放大
   - 导致 `getBoundingClientRect()` 返回错误的尺寸
   - 百度地图内部坐标系统混乱

### 解决方案

**对于百度地图，强制使用服务器端生成（Playwright）**

**实现方式**（[`PosterExportDialog.vue`](frontend/src/components/PosterExportDialog.vue)）：

1. **检测百度地图**：
```typescript
const isBaiduMap = computed(() => {
  const provider = getCurrentProvider()
  return provider === 'baidu' || provider === 'baidu_legacy'
})
```

2. **隐藏生成方式选择器**：
```vue
<el-form-item v-if="showGenerationMode" label="生成方式">
  <!-- 百度地图时隐藏 -->
</el-form-item>

const showGenerationMode = computed(() => {
  return !isMobileDeviceComputed.value && !isBaiduMap.value
})
```

3. **对话框打开时强制设置**：
```typescript
watch(() => props.visible, (newVal) => {
  if (newVal) {
    const provider = getCurrentProvider()
    const isBaidu = provider === 'baidu' || provider === 'baidu_legacy'
    if (isBaidu) {
      config.value.generationMode = 'backend'
    }
  }
})
```

4. **前端生成自动切换**：
```typescript
// handlePreview 和 generatePosterFrontend 中
if (isBaidu) {
  config.value.generationMode = 'backend'
  await generatePosterBackend()
  return
}
```

### 技术细节

**百度地图 Legacy 版本 DOM 结构**：
- `.bmap` 容器：包含控件元素（缩放、比例尺等）
- 地图瓦片：44+ 个 `<img>` 元素，绝对定位
- 轨迹 SVG：1 个 SVG 元素，位于深度 3 的嵌套结构中
- SVG 属性示例：`viewBox="-500 -500 2080 2920" style="position: absolute; top: -500px; left: -500px; width: 2080px; height: 2920px;"`

**坐标系统问题**（CSS transform scale(2)）：
- `.bmap` getBoundingClientRect: `x: -540, y: -960, width: 2160, height: 3840`（2倍尺寸）
- SVG getBoundingClientRect: `x: -1540, y: -1960, width: 4160, height: 5840`（偏移+放大）
- 正确的相对位置需要考虑缩放和偏移

### 相关文件

- [`frontend/src/components/PosterExportDialog.vue`](frontend/src/components/PosterExportDialog.vue) - 导出对话框
- [`frontend/src/utils/frontendPosterGenerator.ts`](frontend/src/utils/frontendPosterGenerator.ts) - 前端海报生成器
- [`backend/app/services/poster_service.py`](backend/app/services/poster_service.py) - 后端海报服务（Playwright）

---

## 最新更改 (2026-02 分享嵌入模式)

### 分享轨迹嵌入模式

**功能背景**：通过 iframe 嵌入分享轨迹时，只显示地图组件，隐藏其他所有元素（header、图表、统计等）。在地图右上角提供"查看轨迹详情"按钮，点击后跳转到完整的分享页面。

**URL 格式**：
- 完整分享页：`/s/{token}`
- 嵌入模式：`/s/{token}?embed=true`

**实现要点**：

**1. 嵌入模式检测** ([`SharedTrack.vue`](frontend/src/views/SharedTrack.vue))

```typescript
// 检测是否为嵌入模式
const isEmbed = computed(() => route.query.embed === 'true')

// 嵌入模式：查看详情链接（指向完整分享页面）
const viewDetailsUrl = computed(() => {
  if (!shareToken.value || !isEmbed.value) return ''
  const baseUrl = window.location.origin
  return `${baseUrl}/s/${shareToken.value}`
})
```

**2. 条件渲染模板结构**

```vue
<!-- 嵌入模式：只显示地图 -->
<div v-if="isEmbed" ref="mapElementRef" class="embed-map-container">
  <div v-if="loading" class="embed-loading">加载中...</div>
  <div v-else-if="loadFailed" class="embed-error">加载失败</div>
  <UniversalMap
    v-else-if="trackWithPoints"
    ref="mapRef"
    :tracks="[trackWithPoints]"
    :highlight-track-id="track?.id"
    :highlight-segments="highlightedSegment ? [highlightedSegment] : null"
    :view-details-url="viewDetailsUrl"
    @point-hover="handleMapPointHover"
    @clear-segment-highlight="clearSegmentHighlight"
  />
</div>

<!-- 完整模式：显示完整分享页面 -->
<div v-else ref="containerRef" class="track-detail-container">
  <!-- header、图表、统计等完整内容 -->
</div>
```

**3. 嵌入模式样式**

```css
/* 嵌入模式样式 */
.embed-map-container {
  width: 100%;
  height: 100vh;
  position: relative;
  overflow: hidden;
}

.embed-loading,
.embed-error {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
  font-size: 16px;
  color: #909399;
}

.embed-error {
  color: #f56c6c;
}
```

**4. UniversalMap 查看详情按钮**

[`UniversalMap.vue`](frontend/src/components/map/UniversalMap.vue) 组件已有 `viewDetailsUrl` prop 支持，当传入该 prop 时，会在地图右上角、地图选择器左侧显示"查看轨迹详情"按钮。

**关键技术点**：

1. **完全独立的根容器**：使用 `v-if`/`v-else` 渲染两个不同的根元素，避免样式冲突
2. **100vh 高度**：嵌入模式下容器占据整个视口高度，无滚动条
3. **按钮样式**：与地图控制栏其他按钮保持一致的设计风格
4. **公开访问**：嵌入模式同样不需要登录，通过 token 验证访问权限

**嵌入代码生成**（[`shared.ts`](frontend/src/api/shared.ts)）：

```typescript
// 生成嵌入代码
getEmbedCode(token: string, width = '100%', height = '520'): string {
  const url = this.getShareUrl(token, true)
  return `<iframe src="${url}" width="${width}" height="${height}" frameborder="0" scrolling="no" allowfullscreen allow="fullscreen"></iframe>`
}
```

**涉及文件**：
- [`frontend/src/views/SharedTrack.vue`](frontend/src/views/SharedTrack.vue) - 分享页面主组件
- [`frontend/src/components/map/UniversalMap.vue`](frontend/src/components/map/UniversalMap.vue) - 地图组件（viewDetailsUrl prop）
- [`frontend/src/api/shared.ts`](frontend/src/api/shared.ts) - 分享 API 和嵌入代码生成

---

## 最新更改 (2026-02 轨迹插值功能)

### 功能概述

轨迹插值功能允许用户在轨迹点间隔较大的区段之间，通过添加控制点并使用贝塞尔曲线算法生成中间插值点，使轨迹更加平滑。

**三阶段流程**：
1. **选择区段**：显示所有符合条件的区段（间隔 ≥ 最小间隔），用户选择一个区段
2. **绘制路径**：在地图上点击添加控制点，拖拽调整位置
3. **预览结果**：预览生成的插值点，确认后保存

### 后端架构

**API 端点**（[`interpolation.py`](backend/app/api/interpolation.py)）：
- `GET /interpolation/tracks/{track_id}/available-segments` - 获取可插值区段列表
- `POST /interpolation/preview` - 预览插值结果（不保存）
- `POST /interpolation/tracks/{track_id}/interpolations` - 创建插值配置并插入插值点
- `GET /interpolation/tracks/{track_id}/interpolations` - 获取轨迹的所有插值配置
- `DELETE /interpolation/interpolations/{interpolation_id}` - 删除插值配置及关联的插值点

**数据模型**（[`interpolation.py`](backend/app/schemas/interpolation.py)）：
- `ControlPoint`：贝塞尔曲线控制点（lng、lat、in_handle、out_handle、handles_locked）
- `AvailableSegment`：可插值区段（start_index、end_index、interval_seconds、start_time、end_time）
- `InterpolatedPoint`：插值点数据（point_index、time、三坐标系坐标、speed、course、elevation）
- `InterpolationCreateRequest`：创建插值请求（start_point_index、end_point_index、control_points、interval、algorithm）

**核心服务**（[`bezier_curve_service.py`](backend/app/services/bezier_curve_service.py)）：
- `calculate_cubic_bezier_point()`：计算三次贝塞尔曲线上的点
- `generate_interpolated_points()`：生成插值点数组（包含时间线性插值、速度/方位角计算）

### 前端组件

**主页面**（[`Interpolation.vue`](frontend/src/views/Interpolation.vue)）：

**三阶段状态管理**：
```typescript
const step = ref<'select' | 'draw' | 'preview'>('select')
```

**区段选择阶段**：
- 表格展示可插值区段，每段三行（起点、终点、间隔）
- 列：时间/间隔、位置、速度、方位角
- 单位转换：速度 m/s → km/h，方位角数字显示（° 在表头）
- 选择框列跨越三行

**表格数据结构**（每段三行）：
```typescript
interface TableRow {
  key: string
  segmentKey: string
  type: 'start' | 'end' | 'interval'
  time: string
  location: string
  speed: number | null
  bearing: number | null
  interval?: number
}
```

**绘制路径阶段**：
- 使用 [`PenToolMap.vue`](frontend/src/components/interpolation/PenToolMap.vue) 组件
- 地图点击添加控制点
- 控制点列表显示坐标，支持删除单个点
- 撤销/重做功能（Ctrl+Z / Ctrl+Y）
- 重置按钮清空所有控制点和历史记录

**历史记录管理**：
```typescript
const history: ControlPoint[][] = []
const historyIndex = ref(0)
const isUndoRedoOperation = ref(false)

function saveToHistory() {
  if (isUndoRedoOperation.value) return
  // 删除当前位置之后的历史
  history.splice(historyIndex.value + 1)
  // 添加新状态
  history.push([...controlPoints.value])
  historyIndex.value++
}
```

**预览阶段**：
- 显示插值点数量
- 禁用编辑（`editable: false`）
- 返回修改按钮清空控制点和历史记录
- 确认保存按钮调用创建 API

**API 请求过滤**：
预览请求需要过滤掉控制点中的多余字段（后端 schema 验证）：
```typescript
const filteredControlPoints = controlPoints.value.map(cp => ({
  lng: cp.lng,
  lat: cp.lat,
  in_handle: cp.inHandle,
  out_handle: cp.outHandle,
  handles_locked: cp.handlesLocked
}))
```

### 地图组件集成

**UniversalMap** 新增 props：
- `availableSegments`：可插值区段列表（用于地图交互）
- `coloredSegments`：多段彩色高亮（start、end、color）
- `disablePointHover`：禁用点悬停（绘制路径时）

**各地图组件 coloredSegments 支持**：
- **AMap**：使用 `AMap.Polyline` 绘制彩色区段
- **BMap**：使用 `BMapGL.Polyline` 绘制彩色区段
- **TencentMap**：使用 `TMap.MultiPolyline`，ID 添加索引避免重复
- **LeafletMap**：使用 `L.polyline` 绘制彩色区段

**高亮逻辑**（[`UniversalMap.vue`](frontend/src/components/map/UniversalMap.vue)）：
- 优先级：选中 > 悬停 > 备选
- 如果全是绿色备选区段，不返回 `highlightSegment`（让 `coloredSegments` 处理）

**自动缩放控制**：
- 各地图组件添加 `hasAutoFocused` 标志
- 只在首次加载时自动缩放，编辑过程中不重复缩放

**点击添加控制点**：
- 高德/百度：Marker 和 Polyline 添加 `click` 事件处理，使用 `bubble: true`
- 腾讯：区分点击和拖拽（鼠标移动 < 5px 才触发点击）

### 控制点手柄

**数据结构**：
```typescript
interface ControlPointHandle {
  dx: number  // 经度偏移
  dy: number  // 纬度偏移
}

interface ControlPoint {
  lng: number
  lat: number
  inHandle: ControlPointHandle
  outHandle: ControlPointHandle
  handlesLocked: boolean
}
```

**手柄锁定机制**：
- `handlesLocked = true`：拖拽一个手柄时，另一个对称移动
- `handlesLocked = false`：手柄独立移动

### 样式规范

**区段表格**：
- 选择框列跨越三行
- 间隔行背景色 `#fafafa`，虚线上边框，实线下边框
- 选中行背景色 `#ecf5ff`
- 单位显示在表头：速度、方位角 (°)

**地图标记**：
- 起点标记：绿色圆点
- 终点标记：红色圆点
- 控制点标记：蓝色圆点 + 手柄线
- 插值连线：蓝色虚线

### 涉及文件

**后端**：
- [`backend/app/api/interpolation.py`](backend/app/api/interpolation.py) - 插值 API 路由
- [`backend/app/schemas/interpolation.py`](backend/app/schemas/interpolation.py) - 插值相关 Schemas
- [`backend/app/services/bezier_curve_service.py`](backend/app/services/bezier_curve_service.py) - 贝塞尔曲线服务
- [`backend/app/services/interpolation_service.py`](backend/app/services/interpolation_service.py) - 插值业务逻辑

**前端**：
- [`frontend/src/views/Interpolation.vue`](frontend/src/views/Interpolation.vue) - 插值主页面
- [`frontend/src/components/interpolation/PenToolMap.vue`](frontend/src/components/interpolation/PenToolMap.vue) - 绘制路径地图组件
- [`frontend/src/api/interpolation.ts`](frontend/src/api/interpolation.ts) - 插值 API 客户端
- [`frontend/src/components/map/UniversalMap.vue`](frontend/src/components/map/UniversalMap.vue) - 通用地图组件（新增 props）
- [`frontend/src/components/map/AMap.vue`](frontend/src/components/map/AMap.vue) - 高德地图（coloredSegments、点击事件）
- [`frontend/src/components/map/BMap.vue`](frontend/src/components/map/BMap.vue) - 百度地图（coloredSegments、点击事件）
- [`frontend/src/components/map/TencentMap.vue`](frontend/src/components/map/TencentMap.vue) - 腾讯地图（coloredSegments、点击/拖拽区分）
- [`frontend/src/components/map/LeafletMap.vue`](frontend/src/components/map/LeafletMap.vue) - Leaflet 地图（coloredSegments）

---

## 最新更改 (2026-02 覆盖层模板编辑器)

### 空格键拖动画布功能

**功能背景**：覆盖层模板编辑器中，用户需要按住空格键并拖动鼠标来平移画布，以便查看画布边缘区域。同时，滚动区域应该超出画布边界 50%，提供更灵活的浏览体验。

**核心需求**：
1. 按住空格键 + 鼠标拖动 → 平移画布
2. 滚动区域超出画布 50%（上下左右都一样）
3. 进入页面时自动居中（与点击"适配"效果一致）
4. 拖动过程中禁用滚动条，防止干扰

**实现架构**（[`OverlayTemplateEditor.vue`](frontend/src/views/OverlayTemplateEditor.vue)）：

**1. 滚动包装器设计**

使用双层结构：`.preview-scroll-wrapper` 提供滚动区域，`.preview-content` 使用 `transform: scale()` 实现缩放。

```html
<div class="preview-container" ref="previewContainerRef" tabindex="0">
  <div class="preview-scroll-wrapper" :style="previewScrollWrapperStyle">
    <div class="preview-content" :style="previewContentStyle">
      <!-- 画布内容 -->
    </div>
  </div>
</div>
```

**2. 滚动区域计算**

滚动区域为容器尺寸的 150%，确保可以滚动超出画布边缘：

```typescript
const previewScrollWrapperStyle = computed(() => {
  const canvas = templateConfig.value.canvas
  const aspectRatio = canvas.width / canvas.height
  const scale = zoomLevel.value / 100

  // 缩放后的画布尺寸
  const canvasWidth = BASE_PREVIEW_SIZE * scale
  const canvasHeight = BASE_PREVIEW_SIZE / aspectRatio * scale

  const container = previewContainerRef.value
  if (!container) {
    return {
      width: `${canvasWidth}px`,
      height: `${canvasHeight}px`,
      minWidth: `${canvasWidth}px`,
      minHeight: `${canvasHeight}px`
    }
  }

  const containerRect = container.getBoundingClientRect()
  // 滚动区域为容器尺寸的 150%
  const scrollAreaWidth = containerRect.width * 1.5
  const scrollAreaHeight = containerRect.height * 1.5

  // 取较大值确保能滚动
  const finalWidth = Math.max(scrollAreaWidth, canvasWidth)
  const finalHeight = Math.max(scrollAreaHeight, canvasHeight)

  return {
    width: `${finalWidth}px`,
    height: `${finalHeight}px`,
    minWidth: `${finalWidth}px`,
    minHeight: `${finalHeight}px`
  }
})
```

**3. 空格键拖动状态管理**

```typescript
const isSpacePressed = ref(false)      // 空格键是否按下
const isPanning = ref(false)            // 是否正在拖动
const panStartPos = ref({ x: 0, y: 0 }) // 拖动起始鼠标位置
const panStartScroll = ref({ x: 0, y: 0 }) // 拖动起始滚动位置
const isMouseDownOnCanvas = ref(false)  // 鼠标是否在画布上按下
const lastMousePos = ref({ x: 0, y: 0 }) // 最后的鼠标位置
const shouldLockScroll = ref(false)     // 滚动锁定标志
```

**4. 键盘事件处理**

容器添加 `tabindex="0"` 使其可以接收键盘事件：

```typescript
// 空格键按下
const handleKeydown = (e: KeyboardEvent) => {
  if (e.code === 'Space' && !e.repeat) {
    e.preventDefault()
    e.stopPropagation()

    shouldLockScroll.value = true
    isSpacePressed.value = true

    // 如果鼠标已经在画布上按下，立即启动拖动
    if (isMouseDownOnCanvas.value && previewContainerRef.value) {
      isPanning.value = true
      panStartPos.value = { ...lastMousePos.value }
      panStartScroll.value = {
        x: previewContainerRef.value.scrollLeft,
        y: previewContainerRef.value.scrollTop
      }
    }
  }
}

// 空格键释放
const handleKeyup = (e: KeyboardEvent) => {
  if (e.code === 'Space') {
    isSpacePressed.value = false
    isPanning.value = false
    setTimeout(() => {
      shouldLockScroll.value = false
    }, 100)
  }
}
```

**5. 鼠标事件处理**

```typescript
// 鼠标按下 - 阻止浏览器自动滚动
const handleCanvasMouseDown = (event: MouseEvent) => {
  if (event.button !== 0) return

  event.preventDefault() // 阻止浏览器 autoscroll

  isMouseDownOnCanvas.value = true
  lastMousePos.value = { x: event.clientX, y: event.clientY }

  // 空格键按下时启动拖动
  if (isSpacePressed.value && previewContainerRef.value) {
    event.stopPropagation()
    isPanning.value = true
    panStartPos.value = { x: event.clientX, y: event.clientY }
    panStartScroll.value = {
      x: previewContainerRef.value.scrollLeft,
      y: previewContainerRef.value.scrollTop
    }
    previewContainerRef.value.classList.add('is-panning')
  }
}

// 鼠标移动 - 拖动画布
const handleMouseMove = (event: MouseEvent) => {
  if (isPanning.value && previewContainerRef.value) {
    event.preventDefault()
    event.stopPropagation()

    const deltaX = event.clientX - panStartPos.value.x
    const deltaY = event.clientY - panStartPos.value.y

    const newScrollLeft = panStartScroll.value.x - deltaX
    const newScrollTop = panStartScroll.value.y - deltaY

    const maxScrollLeft = container.scrollWidth - container.clientWidth
    const maxScrollTop = container.scrollHeight - container.clientHeight

    const clampedScrollLeft = Math.max(0, Math.min(maxScrollLeft, newScrollLeft))
    const clampedScrollTop = Math.max(0, Math.min(maxScrollTop, newScrollTop))

    // 使用 requestAnimationFrame 避免事件循环冲突
    requestAnimationFrame(() => {
      if (previewContainerRef.value) {
        previewContainerRef.value.scrollLeft = clampedScrollLeft
        previewContainerRef.value.scrollTop = clampedScrollTop
      }
    })
  }
}

// 鼠标释放
const handleMouseUp = () => {
  isPanning.value = false
  isMouseDownOnCanvas.value = false
  if (previewContainerRef.value) {
    previewContainerRef.value.classList.remove('is-panning')
  }
}
```

**6. 滚动事件锁定**

防止非拖动触发的滚动：

```typescript
if (previewContainerRef.value) {
  let lastValidScrollLeft = 0
  let lastValidScrollTop = 0

  previewContainerRef.value.addEventListener('scroll', (e) => {
    const target = e.target as HTMLElement

    // 拖动时允许滚动
    if (isPanning.value) {
      lastValidScrollLeft = target.scrollLeft
      lastValidScrollTop = target.scrollTop
      return
    }

    // 滚动锁定时阻止滚动
    if (shouldLockScroll.value) {
      target.scrollLeft = lastValidScrollLeft
      target.scrollTop = lastValidScrollTop
      return
    }

    // 记录正常滚动位置
    lastValidScrollLeft = target.scrollLeft
    lastValidScrollTop = target.scrollTop
  })
}
```

**7. 拖动样式**

```css
.preview-container.is-panning {
  user-select: none;
  overscroll-behavior: none;
  overflow: hidden !important;  /* 拖动时禁用滚动条 */
}

.preview-container.is-panning::-webkit-scrollbar {
  display: none;  /* 隐藏滚动条 */
}
```

**8. 初始居中**

进入页面时自动居中画布：

```typescript
const fitToContainer = () => {
  zoomLevel.value = calculateFitZoom()
  isUserZoomed.value = false

  nextTick(() => {
    if (previewContainerRef.value) {
      const container = previewContainerRef.value
      const scrollWrapper = container.querySelector('.preview-scroll-wrapper') as HTMLElement

      if (scrollWrapper) {
        const wrapperWidth = scrollWrapper.offsetWidth
        const wrapperHeight = scrollWrapper.offsetHeight
        const containerWidth = container.clientWidth
        const containerHeight = container.clientHeight

        // 计算居中位置
        container.scrollLeft = (wrapperWidth - containerWidth) / 2
        container.scrollTop = (wrapperHeight - containerHeight) / 2
      }
    }
  })
}

onMounted(async () => {
  await nextTick()
  zoomLevel.value = calculateFitZoom()
  // ... 其他初始化代码
  nextTick(() => {
    fitToContainer() // 初始居中
  })
})
```

**关键技术点**：

1. **双层结构**：`.preview-scroll-wrapper` 提供滚动区域，`.preview-content` 处理缩放
2. **滚动锁定**：使用 `shouldLockScroll` 标志和事件监听器防止非拖动触发的滚动
3. **拖动时禁用滚动**：添加 `is-panning` class 时设置 `overflow: hidden !important`
4. **requestAnimationFrame**：解耦滚动更新与鼠标事件，避免事件循环冲突
5. **preventDefault**：阻止浏览器默认的 autoscroll 行为
6. **tabindex="0"**：使容器可接收键盘事件
7. **全局事件监听**：`mousemove` 和 `mouseup` 绑定到 document，确保拖动不中断

**涉及文件**：
- [`frontend/src/views/OverlayTemplateEditor.vue`](frontend/src/views/OverlayTemplateEditor.vue) - 覆盖层模板编辑器

### 覆盖层模板编辑器控制点位置计算统一

**问题背景**：拖动控制点调整元素宽度时，控制点会突然回缩或增大，宽度变化幅度过大（1 像素导致 10% 变化），控制点不能保持在鼠标位置上。

**根本原因**：三个关键函数计算元素位置和尺寸时使用了不一致的逻辑：

| 函数 | position.x 处理 | 文本格式化 | 字体设置 |
|------|-----------------|-----------|---------|
| `getHandlePosition` | `(position.x / 100) * canvasWidth` | 应用 `format` | 单引号包裹 |
| `handleResizeStart` | `position.x * canvasWidth` ❌ | 未应用 ❌ | 未包裹 ❌ |
| `getElementOutlineStyle` | `(position.x / 100) * canvasWidth` | 应用 `format` | 未包裹 ❌ |

**后端数据规范**（[`overlay_template.py`](backend/app/schemas/overlay_template.py)）：
- `position.x`: 画布宽度的百分比，范围 `-0.5` 到 `0.5`（即 -50% 到 50%）
- `position.y`: 画布高度的百分比，范围 `-0.5` 到 `0.5`
- `layout.width`: 画布宽度的比例，范围 `0` 到 `1`
- `layout.height`: 画布高度的比例，范围 `0` 到 `1`

**解决方案**：

**1. 统一 position.x/y 的坐标转换**

所有函数都使用 `(position.x / 100) * canvasWidth`：

```typescript
// position.x 的单位是画布宽度的百分比（-0.5 到 0.5）
// 需要除以 100 转换为像素偏移
const offsetX = (position.x / 100) * canvasWidth
const offsetY = (position.y / 100) * canvasHeight
```

**2. 统一文本格式化处理**

所有测量函数都应用 `content.format` 字段：

```typescript
let text = getSampleText(content.source, content.sample_text) || ''
const formatStr = content.format || '{}'
try {
  text = formatStr.replace('{}', text)
} catch {
  // 保持原文本
}
```

**3. 统一字体设置格式**

所有函数都使用单引号包裹字体名称：

```typescript
const fontFamily = getFontFamilyName(fontId || 'system_msyh')
const fontCss = fontFamily.replace(/"/g, "'")
tempCtx.font = `${fontSize}px '${fontCss}'`
```

**4. 修复元素拖动的坐标转换**

拖动元素时，像素偏移需要正确转换为画布百分比：

```typescript
// 将视口像素转换为预览内容像素
const deltaPreviewX = deltaX / zoomFactor
const deltaPreviewY = deltaY / zoomFactor

// 转换为预览内容百分比
const deltaPreviewPctX = (deltaPreviewX / previewBaseWidth) * 100
const deltaPreviewPctY = (deltaPreviewY / previewBaseHeight) * 100

// 转换为画布百分比（position.x/y 的单位：-0.5 到 0.5）
const deltaCanvasPctX = deltaPreviewPctX / 100
const deltaCanvasPctY = deltaPreviewPctY / 100

element.position.x = elementStartPos.value.x + deltaCanvasPctX
element.position.y = elementStartPos.value.y + deltaCanvasPctY
```

**5. 调整宽度时的坐标转换**

拖动东/西控制点时，鼠标位置直接转换为预览内容百分比，再转换为画布百分比：

```typescript
// 鼠标位置已经是预览内容百分比（0-100）
// 直接计算新宽度
const newWidthPreviewPct = Math.max(0.01, mousePctX - elemLeft)
const newWidthCanvasPct = newWidthPreviewPct / 100  // 转换为 0-1 范围
layout.width = newWidthCanvasPct
```

**关键技术点**：

1. **position.x 是画布百分比（-0.5 到 0.5）**：需要除以 100 转换为像素偏移
2. **layout.width 是画布比例（0 到 1）**：直接乘以 canvasWidth 得到像素
3. **预览内容百分比（0-100）**：用于控制点位置和 mousemove 计算
4. **画布百分比（0-1）**：存储在数据库中，用于 layout.width/height

**涉及文件**：
- [`frontend/src/views/OverlayTemplateEditor.vue`](frontend/src/views/OverlayTemplateEditor.vue) - `getHandlePosition`、`handleResizeStart`、`getElementOutlineStyle`、`handleMouseMove` 函数
