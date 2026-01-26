# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Vibe Route** 是一个基于 [gpxutil](https://github.com/DingJunyao/gpxutil) 构建的全栈 Web 轨迹管理系统。用户可以上传 GPX 文件，系统会解析轨迹数据，进行坐标转换（WGS84/GCJ02/BD09）、地理编码填充，并在地图上可视化展示。

## Development Commands

### Backend

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env

# 创建数据目录
mkdir -p data/uploads data/temp data/exports data/road_signs

# 运行开发服务器
uvicorn app.main:app --reload

# 数据库迁移
alembic upgrade head

# 运行测试
pytest
```

后端运行在 `http://localhost:8000`，API 文档：`http://localhost:8000/docs`

### Frontend

```bash
cd frontend

# 安装依赖
npm install

# 运行开发服务器
npm run dev

# 构建生产版本
npm run build

# 代码检查
npm run lint
```

前端运行在 `http://localhost:5173`

## Architecture Overview

### 认证流程（双重加密）

**关键设计**：密码在传输和存储过程中经过两次加密：

1. **前端加密** ([`crypto.ts`](frontend/src/utils/crypto.ts))：使用 `js-sha256` 库对明文密码进行 SHA256 加密
2. **后端存储** ([`security.py`](backend/app/core/security.py))：后端接收前端传来的 SHA256 哈希值，再用 bcrypt 进行二次哈希后存储

```typescript
// 前端: crypto.ts
const hashedPassword = await hashPassword(password)  // SHA256
await authApi.login({ username, password: hashedPassword })
```

```python
# 后端: security.py
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
hashed_password = pwd_context.hash(sha256_password_from_frontend)
```

### 公开配置 vs 管理员配置

系统有两套配置 API，根据用户权限区分：

- **公开配置** (`GET /api/auth/config`)：任何用户可访问，只返回地图相关配置（`default_map_provider`, `map_layers`）
- **管理员配置** (`GET /api/admin/config`)：需要管理员权限，返回完整配置（包括注册开关、邀请码配置等）

前端 [`config.ts`](frontend/src/stores/config.ts) store 会根据用户权限自动选择合适的 API。

### 多坐标系支持

轨迹点存储三种坐标系（[`track.py:62-67`](backend/app/models/track.py)）：
- **WGS84**: 国际标准坐标系（GPS 原始坐标）
- **GCJ02**: 中国火星坐标系（高德、腾讯地图、天地图）
- **BD09**: 百度坐标系

地图组件（[`LeafletMap.vue`](frontend/src/components/map/LeafletMap.vue)）根据选择的底图自动使用对应坐标。

### 用户状态字段

用户模型有两个易混淆的状态字段：

- **`is_valid`**: 软删除标记，用于逻辑删除用户。查询用户时会过滤 `is_valid = False` 的记录
- **`is_active`**: 账户启用状态，控制用户能否登录。被禁用的用户无法登录但数据仍保留

用户创建时会复用已删除（`is_valid = False`）用户的用户名或邮箱记录，而非创建新记录。

### 数据库模型

核心模型：
- [`User`](backend/app/models/user.py): 用户表，首位注册用户自动成为管理员
- [`Track`](backend/app/models/track.py): 轨迹表，存储统计信息和处理状态
- [`TrackPoint`](backend/app/models/track.py): 轨迹点表，存储三种坐标和地理编码信息
- [`Task`](backend/app/models/task.py): 异步任务（信息覆盖层生成等）
- [`Config`](backend/app/models/config.py): 系统配置（邀请码、地图提供商等）

所有模型继承 [`AuditMixin`](backend/app/models/base.py)，包含 `created_at`, `updated_at`, `created_by`, `updated_by`, `is_valid` 字段。

### 路由守卫

前端路由守卫（[`router/index.ts:71-94`](frontend/src/router/index.ts)）：
- `guest`: 未登录用户可访问（登录页、注册页）
- `requiresAuth`: 需要登录
- `requiresAdmin`: 需要管理员权限

### API 请求拦截

[`request.ts`](frontend/src/api/request.ts) 配置：
- 自动添加 `Authorization: Bearer {token}` 头
- 401 响应使用后端返回的具体错误信息（如"用户名或密码错误"）
- 如果不在登录页，401 会清除 token 并跳转登录页
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
- viewport 配置禁止页面缩放：`maximum-scale=1.0, user-scalable=no`

### 响应式布局与视口适配

为了确保内容能在第一屏完整显示，首页和轨迹详情页采用了基于视口高度（vh）的动态布局方案。

#### 核心技术

##### 1. 视口高度单位 (vh)

使用 `vh`（视口高度百分比）动态计算元素高度，自动适应不同屏幕尺寸：

```css
/* 主容器高度 = 视口高度 - 导航栏高度 */
.main {
  height: calc(100vh - 60px);
}

/* 地图容器使用视口高度的百分比 */
.normal-map-container {
  height: 40vh;
  min-height: 300px;
}

.chart {
  height: 22vh;
  min-height: 180px;
}
```

##### 2. 窗口大小监听

使用 `ref` 和事件监听器追踪窗口尺寸变化：

```typescript
const screenWidth = ref(window.innerWidth)
const screenHeight = ref(window.innerHeight)
const isMobile = computed(() => screenWidth.value <= 1366)
const isTallScreen = computed(() => !isMobile.value && screenHeight.value >= 800)

function handleResize() {
  screenWidth.value = window.innerWidth
  screenHeight.value = window.innerHeight
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})
```

##### 3. Flexbox 布局

使用 flex 布局实现自适应空间分配：

```css
.main {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 60px);
}

.stats-row {
  flex-shrink: 0; /* 防止被压缩 */
}

.map-card {
  flex: 1; /* 自动填充剩余空间 */
  min-height: 0; /* 允许 flex 子元素缩小 */
}
```

#### 首页布局 ([`Home.vue`](frontend/src/views/Home.vue))

| 端       | 主容器高度            | 统计卡片                  | 地图卡片               |
|----------|-----------------------|---------------------------|------------------------|
| 电脑端   | `calc(100vh - 60px)`  | 固定高度（4 列横向）      | `flex: 1` 填充剩余     |
| 移动端   | `calc(100vh - 60px)`  | 70-80px 高度（2x2 网格）  | `flex: 1`，最小 200px  |

#### 轨迹详情页布局 ([`TrackDetail.vue`](frontend/src/views/TrackDetail.vue))

**固定布局**（电脑端高度 >= 800px）：

- 左侧固定（地图 + 图表），右侧滚动
- 地图使用 `flex: 1` 自适应填充

**常规布局**（电脑端高度 < 800px）：

- 左右独立滚动
- 地图：40vh（最小 300px）
- 图表：22vh（最小 180px）

**移动端布局**：

- 单列流式布局，所有卡片垂直排列（不分左右区域）
- 地图：30vh（最小 200px）
- 图表：20vh（最小 150px）

#### 轨迹详情页"轨迹信息"卡片结构

轨迹详情页的"轨迹信息"卡片（[`TrackDetail.vue`](frontend/src/views/TrackDetail.vue)）整合了多项轨迹信息：

1. **起止时间**（卡片顶部）：
   - 时间大字显示（18px 粗体）
   - 日期小字显示（12px）
   - 起止日期相同时，日期显示在中间分隔线上替代时钟图标
   - 移动端保持水平排列（不分行）

2. **统计信息**（中间部分，2x2 网格）：
   - 总里程、总时长、总爬升、总下降

3. **备注**（卡片底部）：
   - 仅在有备注时显示
   - 使用分隔线与上方内容分隔

#### 地图响应式重绘

使用 `ResizeObserver` 监听地图容器大小变化，触发地图重绘：

```typescript
// 在 TrackDetail.vue 中
const mapWrapperRef = ref<HTMLElement>()
let mapResizeObserver: ResizeObserver | null = null

onMounted(() => {
  if (mapWrapperRef.value) {
    mapResizeObserver = new ResizeObserver(() => {
      if (mapRef.value?.resize) {
        mapRef.value.resize()
      }
    })
    mapResizeObserver.observe(mapWrapperRef.value)
  }
})
```

所有地图组件（[`LeafletMap.vue`](frontend/src/components/map/LeafletMap.vue)、[`AMap.vue`](frontend/src/components/map/AMap.vue)、[`BMap.vue`](frontend/src/components/map/BMap.vue)、[`TencentMap.vue`](frontend/src/components/map/TencentMap.vue)）都暴露了 `resize()` 方法，通过 [`UniversalMap.vue`](frontend/src/components/map/UniversalMap.vue) 统一调用。

#### 移动端分页器固定底部

轨迹列表页（[`TrackList.vue`](frontend/src/views/TrackList.vue)）移动端需要固定分页器在底部，确保始终可见且不被浏览器地址栏遮挡。

**问题背景**：不同移动浏览器的地址栏/工具栏高度差异很大：

- iOS Safari: ~42px
- iOS Edge: ~12px
- Android Chrome: ~96px
- Android Edge: ~115px

由于页面采用 `position: fixed` 容器布局不可滚动，分页器一旦被遮挡就无法访问。

**解决方案**：使用 `position: fixed` 将分页器固定在屏幕底部，并给列表添加底部 padding 防止内容被遮挡。

```css
@media (max-width: 1366px) {
  /* 列表底部留出分页器空间 */
  .mobile-card-list {
    padding-bottom: 70px;  /* 分页器高度 + 安全区域 */
  }

  /* 分页器固定在底部 */
  .pagination {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 100;
    background: #f5f7fa;
    padding: 10px;
    /* 适配安全区域（刘海屏） */
    padding-bottom: max(10px, env(safe-area-inset-bottom));
    box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.1);
  }
}
```

**关键技术点**：

1. **固定定位**：`position: fixed; bottom: 0` 确保分页器始终在视口底部
2. **背景色**：添加 `background` 和 `box-shadow` 确保在滚动内容之上可见
3. **安全区域适配**：`env(safe-area-inset-bottom)` 适配 iPhone 刘海屏
4. **列表留白**：滚动容器添加 `padding-bottom` 防止最后一项被分页器遮挡

### 地图与图表双向同步

轨迹详情页（[`TrackDetail.vue`](frontend/src/views/TrackDetail.vue)）实现了地图与图表的双向交互：

#### 桌面端 - 鼠标悬停

- 地图鼠标悬停 → 图表高亮对应点
- 图表鼠标悬停 → 地图显示标记和 tooltip

#### 移动端 - 点击

- 点击地图靠近轨迹 → 显示对应点的 tooltip
- 点击地图远离轨迹 → 隐藏 tooltip

#### 关键技术点

- 动态触发距离：`Math.pow(2, 12 - zoom) * 0.008` 随缩放级别调整

- 几何计算：点到线段距离、最近点查找

- 位置信息格式化：`省 市 区 road_number road_name`（多条道路编号逗号分隔转斜杠）

- **高德地图**事件处理：`mousemove`/`click` + DOM 捕获阶段备用

- **百度地图**事件处理：`addEventListener('mousemove')`/`addEventListener('click')`

- **Leaflet 地图**事件处理：`mousemove`/`click` 直接监听地图实例

- 图表同步：ECharts `dispatchAction` 触发 `showTip`/`highlight`

- Polyline `bubble: true`（高德）允许事件冒泡

- 蓝色圆点标记：`#409eff` 背景，`2px solid #fff` 边框，`border-radius: 50%`

##### 百度地图 GL 特殊处理

百度地图 GL 版本 ([`BMap.vue`](frontend/src/components/map/BMap.vue)) 有以下特殊要求：

1. **自定义覆盖物必须继承`BMapGL.Overlay`**：标记类需要继承覆盖物基类，并实现 `initialize(map)` 和 `draw()` 方法

2. **监听地图移动/缩放事件**：在 `initialize` 方法中添加 `moveend` 和 `zoomend` 监听器，确保地图拖动或缩放时标记位置自动更新：

   ```javascript
   map.addEventListener('moveend', this._mapMoveHandler)
   map.addEventListener('zoomend', this._mapMoveHandler)
   ```

3. **使用标准覆盖物 API**：添加/移除覆盖物使用 `map.addOverlay(overlay)` 和 `map.removeOverlay(overlay)`

4. **InfoWindow 状态冲突**：百度地图的 InfoWindow 有状态管理问题，连续调用 `openInfoWindow` 可能不生效。解决方法：

   ```javascript
   BMapInstance.closeInfoWindow()
   setTimeout(() => {
     BMapInstance.openInfoWindow(newTooltip, bmapPoint)
   }, 0)
   ```

5. **资源清理**：在覆盖物的 `remove()` 方法中移除事件监听器，避免内存泄漏

##### 腾讯地图 GL JS API 特殊处理

腾讯地图 GL JS API 版本 ([`TencentMap.vue`](frontend/src/components/map/TencentMap.vue)) 有以下特殊要求：

1. **坐标转换 API 不可用**：腾讯地图 GL JS API 不提供 `containerToLatLng`、`pointToLngLat` 等坐标转换方法，需要手动计算：

   ```javascript
   const bounds = TMapInstance.getBounds()
   const ne = bounds.getNorthEast()
   const sw = bounds.getSouthWest()
   const lngRange = ne.lng - sw.lng
   const latRange = ne.lat - sw.lat
   const xRatio = x / rect.width
   const yRatio = y / rect.height
   const lng = sw.lng + lngRange * xRatio
   const lat = ne.lat - latRange * yRatio
   ```

2. **使用 MultiMarker 显示标记**：创建 Canvas 绘制的蓝色圆点作为 data URL，配合 `TMap.MultiMarker` 显示悬停标记：

   ```javascript
   const canvas = document.createElement('canvas')
   canvas.width = 16
   canvas.height = 16
   const ctx = canvas.getContext('2d')
   // 绘制白色边框和蓝色圆点
   const dataUrl = canvas.toDataURL()
   mouseMarker = new TMap.MultiMarker({
     map: null,
     styles: {
       'blue-dot': new TMap.MarkerStyle({
         width: 16,
         height: 16,
         anchor: { x: 8, y: 8 },
         src: dataUrl,
       }),
     },
     geometries: [],
   })
   ```

3. **事件监听在 DOM 容器上**：使用 `addEventListener` 在 `mapContainer` 上监听 `click` 和 `touchend` 事件，捕获阶段（`capture: true`）确保事件能被捕获

4. **避免重复设置 lastHoverIndex**：在事件处理器中不要提前设置 `lastHoverIndex`，应让 `updateMarker` 函数来设置，否则会被"同一索引"检查拦截而跳过更新

5. **InfoWindow 样式覆盖**：使用 `:deep()` 选择器移除默认的 padding 和 margin：

   ```css
   :deep(.tmap-infowindow-content) {
     padding: 0 !important;
     margin: 0 !important;
   }
   ```

##### 自定义 Tooltip 实现

为了避免原生地图 InfoWindow/Popup 的闪烁问题，Leaflet 和百度地图组件实现了自定义 HTML tooltip。

**问题背景**：

- 百度地图：每次更新都创建新 InfoWindow 实例，导致明显闪烁
- Leaflet 地图：Popup 在快速更新时也会出现闪烁和位置问题

**解决方案**：使用自定义 HTML 元素替代原生 InfoWindow/Popup

**Leaflet 地图** ([`LeafletMap.vue`](frontend/src/components/map/LeafletMap.vue))：

```typescript
// 自定义 tooltip 元素
const customTooltip = ref<HTMLElement | null>(null)
const currentHighlightPoint = ref<{ index: number; position: [number, number] } | null>(null)

// 创建自定义 tooltip
function createCustomTooltip() {
  if (!mapContainer.value) return
  const tooltipDiv = document.createElement('div')
  tooltipDiv.className = 'custom-map-tooltip'
  tooltipDiv.style.cssText = `
    position: absolute;
    z-index: 1000;
    pointer-events: none;
    display: none;
    padding: 8px 12px;
    background: rgba(255, 255, 255, 0.95);
    border-radius: 6px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
    font-size: 12px;
    line-height: 1.6;
    white-space: nowrap;
  `
  mapContainer.value.appendChild(tooltipDiv)
  customTooltip.value = tooltipDiv
}

// 智能更新 tooltip 位置（避免超出视口）
function updateCustomTooltip(content: string, pointPixel: L.Point, containerSize: { x: number; y: number }) {
  if (!customTooltip.value) return
  const tooltip = customTooltip.value
  tooltip.innerHTML = content
  tooltip.style.display = 'block'

  const tooltipRect = tooltip.getBoundingClientRect()
  const tooltipWidth = tooltipRect.width
  const tooltipHeight = tooltipRect.height
  const padding = 10

  let positionX = pointPixel.x
  let positionY = pointPixel.y - tooltipHeight - 10  // 默认在上方

  // 检查上方空间，不足则显示在下方
  if (pointPixel.y - tooltipHeight < padding) {
    if (pointPixel.y + tooltipHeight + 10 < containerSize.y - padding) {
      positionY = pointPixel.y + 10
    }
  }

  // 检查左右空间，防止超出边界
  if (pointPixel.x - tooltipWidth / 2 < padding) {
    positionX = padding + tooltipWidth / 2
  } else if (pointPixel.x + tooltipWidth / 2 > containerSize.x - padding) {
    positionX = containerSize.x - padding - tooltipWidth / 2
  }

  tooltip.style.left = `${positionX - tooltipWidth / 2}px`
  tooltip.style.top = `${positionY}px`
}

// 地图移动时更新 tooltip 位置（保持同步）
map.value.on('move', () => {
  if (currentHighlightPoint.value && customTooltip.value) {
    // 重新计算 tooltip 位置并更新
  }
})
```

**百度地图** ([`BMap.vue`](frontend/src/components/map/BMap.vue))：

```typescript
let customTooltip: HTMLElement | null = null
let currentHighlightPoint: { index: number; position: { lng: number; lat: number }; point: Point } | null = null

// 坐标转换：经纬度 → 容器像素
function lngLatToContainerPoint(lng: number, lat: number): { x: number; y: number } | null {
  if (!BMapInstance || !mapContainer.value) return null
  const BMapGL = (window as any).BMapGL
  const point = new BMapGL.Point(lng, lat)
  const pixel = BMapInstance.pointToOverlayPixel(point)
  if (!pixel) return null
  return { x: pixel.x, y: pixel.y }
}

// 监听地图移动事件
BMapInstance.addEventListener('moveend', () => {
  if (currentHighlightPoint && customTooltip && mapContainer.value) {
    const pointPixel = lngLatToContainerPoint(currentHighlightPoint.position.lng, currentHighlightPoint.position.lat)
    if (pointPixel) {
      // 重新生成内容并更新位置
    }
  }
})
```

**关键技术点**：

1. **自定义 HTML 元素**：使用绝对定位的 `div`，`pointer-events: none` 防止干扰鼠标事件
2. **智能定位**：根据视口边界自动调整 tooltip 显示位置（上下左右）
3. **移动同步**：监听地图 `move`/`moveend` 事件，地图平移时实时更新 tooltip 位置
4. **避免闪烁**：只更新现有元素的内容和位置，不创建/销毁 DOM 元素
5. **坐标转换**：

   - Leaflet: `map.latLngToContainerPoint(latlng)`
   - 百度: `map.pointToOverlayPixel(point)`

**高德地图无需修改**：高德地图使用单个 InfoWindow 实例配合 `setContent()` 更新内容，不存在闪烁问题。

### 轨迹详情页"经过区域"点击高亮功能

轨迹详情页（[`TrackDetail.vue`](frontend/src/views/TrackDetail.vue)）实现了点击"经过区域"树中的项目高亮对应路径段的功能。

#### 功能说明

- 点击"经过区域"树中的任意项目（省/市/区/道路），地图上对应路径段显示为蓝色高亮
- 地图右上角（地图选择器左边）出现清除按钮（关闭图标）
- 点击清除按钮取消高亮，按钮同时消失
- 移动端点击时会自动滚动到地图位置

#### 后端实现

**文件**: [`backend/app/services/track_service.py`](backend/app/services/track_service.py)

在 `get_region_tree` 方法中，为每个区域节点添加 `start_index` 和 `end_index` 字段，记录该区域对应的轨迹点索引范围：

```python
def create_node(name: str, node_type: str, road_number: str = None) -> dict:
    return {
        # ... 其他字段 ...
        'start_index': -1,  # 起始点索引
        'end_index': -1,    # 结束点索引
        'children': [],
    }
```

使用数据库中的 `point.point_index` 字段作为索引来源，确保索引的准确性。

**文件**: [`backend/app/schemas/track.py`](backend/app/schemas/track.py)

更新 `RegionNode` schema，添加索引字段：

```python
class RegionNode(BaseModel):
    # ... 其他字段 ...
    start_index: int = -1
    end_index: int = -1
    children: List['RegionNode'] = []
```

#### 前端实现

**文件**: [`frontend/src/api/track.ts`](frontend/src/api/track.ts)

更新 `RegionNode` 接口：

```typescript
export interface RegionNode {
  start_index: number
  end_index: number
  // ... 其他字段 ...
}
```

**地图组件** - 所有四个地图引擎（[`LeafletMap.vue`](frontend/src/components/map/LeafletMap.vue)、[`AMap.vue`](frontend/src/components/map/AMap.vue)、[`BMap.vue`](frontend/src/components/map/BMap.vue)、[`TencentMap.vue`](frontend/src/components/map/TencentMap.vue)）都实现了路径段高亮：

- 添加 `highlightSegment` prop（类型：`{ start: number; end: number } | null`）
- 在 `drawTracks` 方法中绘制高亮路径段（蓝色，线宽 7）
- 清除轨迹时同时清除高亮层

**坐标对象注意事项**：

- **高德地图**：需要使用 `AMap.LngLat` 对象，不能使用普通 `{ lng, lat }` 对象
- **百度地图**：需要使用 `BMapGL.Point` 对象，不能使用普通 `{ lng, lat }` 对象
- **腾讯地图**：使用 `TMap.LatLng` 对象（已在 `trackPath` 中使用）
- **Leaflet 地图**：使用 `[lat, lng]` 数组格式

**UniversalMap 组件** ([`frontend/src/components/map/UniversalMap.vue`](frontend/src/components/map/UniversalMap.vue))：

- 添加 `highlightSegment` prop 并传递给所有地图引擎
- 添加 `clear-segment-highlight` emit 事件
- 在地图控制栏添加清除高亮按钮（地图选择器左边，使用 Close 图标）
- 仅当 `highlightSegment` 不为空时显示按钮

**TrackDetail 页面** ([`frontend/src/views/TrackDetail.vue`](frontend/src/views/TrackDetail.vue))：

- 添加 `highlightedSegment` 状态管理
- 实现 `handleRegionNodeClick` 处理函数
  - 设置高亮路径段
  - 移动端自动滚动到地图（使用 `containerRef.value?.scrollTo({ top: 0, behavior: 'smooth' })`）
- 实现 `clearSegmentHighlight` 清除函数
- 在 `el-tree` 上绑定 `@node-click="handleRegionNodeClick"`
- 在 `UniversalMap` 上绑定 `@clear-segment-highlight="clearSegmentHighlight"`

#### 实现要点

1. **滚动容器**：页面使用 `.track-detail-container` 作为滚动容器（`overflow-y: auto`），不是 `window`，因此需要使用 `containerRef.value?.scrollTo()` 而非 `window.scrollTo()`

2. **索引追踪**：使用数据库字段 `point.point_index` 而非手动维护索引计数器，确保索引的准确性和一致性

3. **节点切换处理**：当切换省份/城市/行政区时，需要先结束当前活跃的子节点，确保所有节点的 `end_index` 被正确设置

4. **地图坐标对象**：不同地图引擎需要特定的坐标对象类型，使用前需转换

### 首页地图轨迹信息显示模式

首页地图使用不同的交互模式，显示轨迹信息而非单点信息。

#### 模式区分

地图组件支持两种模式，通过 `mode` prop 控制：

- **`home`模式**（首页）：悬停/点击轨迹时显示轨迹信息
  - 轨迹名称
  - 时间起止（同一天时终止时间只显示时间）
  - 里程
  - 历时

- **`detail`模式**（轨迹详情页）：悬停/点击时显示点信息
  - 位置信息
  - 海拔
  - 时间
  - 速度

#### Track 接口扩展

```typescript
interface Track {
  id: number
  points: Point[]
  name?: string           // 轨迹名称
  start_time?: string | null   // 开始时间
  end_time?: string | null     // 结束时间
  distance?: number          // 里程（米）
  duration?: number          // 历时（秒）
}
```

#### 事件处理

- **home 模式**：发射 `track-hover` 事件，参数为 `trackId`
- **detail 模式**：发射 `point-hover` 事件，参数为 `(point, pointIndex)`

#### 移动端特殊处理

在移动端，所有地图引擎的点击事件处理器都会检查 `props.mode`：

```typescript
if (props.mode === 'home') {
  // 显示轨迹信息
} else {
  // 显示点信息
}
```

#### 腾讯地图移动端修复

腾讯地图在移动端有以下特殊处理：

1. **移除 mouseout 监听器**（仅桌面端添加）：移动端的 `touchend` 会触发 `mouseout` 事件，导致刚显示的 InfoWindow 被立即关闭

   ```javascript
   const isMobile = window.innerWidth <= 1366
   if (!isMobile) {
     TMapInstance.on('mouseout', () => {
       hideMarker()
     })
   }
   ```

2. **防抖标志**：防止 `touchend` 和 `click` 重复触发

   ```javascript
   let isClickProcessing = false

   // click 事件
   if (isClickProcessing) return

   // touchend 事件
   e.preventDefault()
   isClickProcessing = true
   setTimeout(() => {
     isClickProcessing = false
   }, 300)
   ```

3. **InfoWindow 参数**：创建时必须指定 `map`、`offset` 和 `enableCustom` 参数

   ```javascript
   infoWindow = new TMap.InfoWindow({
     map: TMapInstance,
     position: nearestPosition,
     content: content,
     offset: { x: 0, y: -40 },
     enableCustom: true,
   })
   ```

#### Leaflet 地图切换底图修复

切换底图时需要清除提示框，避免残留：

```javascript
function addTileLayer(layerId: string) {
  if (!map.value) return

  // 切换底图时清除提示框和标记
  hideMarker()

  // ... 切换底图逻辑
}
```

#### 涉及文件

- [`LeafletMap.vue`](frontend/src/components/map/LeafletMap.vue) - Leaflet 地图组件（支持 OSM、天地图等）
- [`AMap.vue`](frontend/src/components/map/AMap.vue) - 高德地图组件
- [`BMap.vue`](frontend/src/components/map/BMap.vue) - 百度地图组件
- [`TencentMap.vue`](frontend/src/components/map/TencentMap.vue) - 腾讯地图组件
- [`UniversalMap.vue`](frontend/src/components/map/UniversalMap.vue) - 地图引擎包装器
- [`TrackDetail.vue`](frontend/src/views/TrackDetail.vue) - 轨迹详情页
- [`Home.vue`](frontend/src/views/Home.vue) - 首页（使用 `mode="home"`）

### 地图居中按钮

地图控制栏在全屏按钮左边提供了一个居中按钮，点击后将所有轨迹居中显示，四周留 5% 的空间。

#### 功能说明

- **按钮位置**：全屏按钮左边，地图选择器右边
- **按钮图标**：靶心图标（中心圆点 + 十字准星）
- **功能**：移动、缩放地图，将所有轨迹居中在画面，四周留 5% 的边距

#### 前端实现

**UniversalMap 组件** ([`frontend/src/components/map/UniversalMap.vue`](frontend/src/components/map/UniversalMap.vue))：

- 添加居中按钮（使用内联 SVG 绘制靶心图标）
- 添加 `fitBounds()` 方法，根据当前地图引擎调用对应方法
- 将 `fitBounds` 暴露给父组件

**各地图引擎的 fitBounds 实现**：

所有四个地图引擎（[`LeafletMap.vue`](frontend/src/components/map/LeafletMap.vue)、[`AMap.vue`](frontend/src/components/map/AMap.vue)、[`BMap.vue`](frontend/src/components/map/BMap.vue)、[`TencentMap.vue`](frontend/src/components/map/TencentMap.vue)）都实现了 `fitBounds()` 方法：

1. **Leaflet 地图**：
   - 计算所有轨迹点的边界（使用 `L.latLngBounds()`）
   - 调用 `map.fitBounds(bounds, { padding: L.point(padding, padding) })`
   - padding 使用 `L.point()` 对象格式

2. **高德地图**：
   - 使用 `AMapInstance.setFitView(null, false, [padding, padding, padding, padding])`

3. **百度地图**：
   - 使用 `BMapInstance.setViewport(bounds)`

4. **腾讯地图**：
   - 计算 LatLngBounds
   - 使用 `TMapInstance.fitBounds(boundsObj, { padding })`

#### 关键技术点

1. **坐标系转换**：每个地图引擎根据自身坐标系（WGS84/GCJ02/BD09）获取对应的坐标字段

2. **坐标有效性检查**：严格检查坐标类型和值
   ```typescript
   if (typeof lat === 'number' && typeof lng === 'number' && !isNaN(lat) && !isNaN(lng)) {
     bounds.extend([lat, lng])
   }
   ```

3. **坐标返回格式**：
   - Leaflet/天地图/OSM：`getCoordsByCRS()` 返回 `[lat, lng]` 数组
   - 高德/腾讯地图：`getGCJ02Coords()` 返回 `{ lat, lng }` 对象
   - 百度地图：`getBD09Coords()` 返回 `{ lat, lng }` 对象

4. **Padding 计算**：取地图容器宽高中较大值的 5%
   ```typescript
   const padding = Math.round(Math.max(width, height) * 0.05)
   ```

### 道路标志生成功能

首页提供道路标志 SVG 生成功能，支持普通道路和高速公路标志。

#### 功能说明

- **普通道路**（`way`）：字母 + 三位数字，如 G221（国道-红）、S221（省道-黄）、X221（县道-白）
- **高速公路**（`expwy`）：
  - 国家高速：G + 1-4位数字，如 G5、G45、G4511
  - 省级高速：S + 纯数字(1-4位) 或 S + 字母 + 可选数字（**仅限四川省**）
    - 如 S1、S11、S1111（通用格式）
    - 或 SA、SC、SA1、SA12（四川省专用格式）

#### 对话框响应式宽度

所有对话框采用统一的响应式宽度模式：

```vue
<!-- 桌面端固定宽度 -->
<el-dialog width="500px">
  <!-- 道路标志对话框稍宽，因为表单较复杂 -->
  <el-dialog width="600px">
```

```css
/* 移动端自适应 */
@media (max-width: 1366px) {
  .responsive-dialog {
    width: 95% !important;
  }
}
```

**涉及文件**：

- [`TrackDetail.vue`](frontend/src/views/TrackDetail.vue)：4 个对话框
- [`Home.vue`](frontend/src/views/Home.vue)：1 个对话框（道路标志生成，600px）
- [`Admin.vue`](frontend/src/views/Admin.vue)：2 个对话框

#### 单选按钮说明文字模式

当单选按钮文本较长时，采用简化标签 + 动态说明的模式：

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

```css
/* 单选按钮说明文字 */
.radio-hint {
  display: block;
  width: 100%;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 12px;
  line-height: 1.5;
}
```

**关键技术点**：

1. 使用 `display: block; width: 100%` 确保说明文字始终在单选组下方
2. 根据 `v-model` 的值动态显示对应的说明内容
3. 说明文字使用次要颜色，视觉上与选项区分

#### 表单变更自动清除预览

道路标志生成对话框中，任何表单字段变更都会清除 SVG 预览：

```typescript
// 监听道路类型或高速类型变化，清空编号和预览
watch(() => [roadSignForm.sign_type, roadSignForm.is_provincial], () => {
  roadSignForm.code = ''
  roadSignForm.expwyCode = ''
  generatedSvg.value = ''
})

// 监听省份变化，更新完整编号并清空预览
watch(() => roadSignForm.province, () => {
  updateFullCode()
  generatedSvg.value = ''
})

// 监听 expwyCode 变化，更新完整编号并清空预览
watch(() => roadSignForm.expwyCode, () => {
  updateFullCode()
  generatedSvg.value = ''
})

// 监听普通道路编号变化，清空预览
watch(() => roadSignForm.code, () => {
  generatedSvg.value = ''
})

// 监听道路名称相关字段变化，清空预览
watch(() => [roadSignForm.has_name, roadSignForm.name], () => {
  generatedSvg.value = ''
})
```

#### 四川省字母格式限制

省级高速的字母格式编号（SA、SC、SA1 等）仅限四川省使用。

**前端验证** ([`Home.vue`](frontend/src/views/Home.vue))：

```typescript
function validateRoadCode(code: string, signType: string, province?: string): { valid: boolean; message?: string } {
  // ... 其他验证 ...
  } else if (signType === 'expwy') {
    if (trimmedCode.startsWith('S')) {
      // 字母格式仅限四川（川）
      const letterFormatMatch = /^S[A-Z]\d{0,3}$/.exec(trimmedCode)
      if (letterFormatMatch) {
        if (province !== '川') {
          return {
            valid: false,
            message: '字母格式的省级高速编号仅限四川省使用，请选择四川或使用纯数字编号（如 S1、S11）'
          }
        }
      }
    }
  }
  return { valid: true }
}
```

**后端验证** ([`road_signs.py`](backend/app/api/road_signs.py))：

使用 Pydantic 的 `model_validator` 进行多字段验证：

```python
from pydantic import BaseModel, Field, field_validator, model_validator

class RoadSignRequest(BaseModel):
    sign_type: str
    code: str
    province: Optional[str] = None
    name: Optional[str] = None

    @field_validator('code')
    @classmethod
    def normalize_code(cls, v: str) -> str:
        """规范化道路编号：转大写"""
        return v.strip().upper()

    @model_validator(mode='after')
    def validate_road_sign(self) -> 'RoadSignRequest':
        """校验道路编号（可访问多个字段）"""
        code = self.code
        sign_type = self.sign_type
        province = self.province

        if sign_type == 'expwy':
            if code.startswith('S'):
                # 字母格式仅限四川省
                letter_format_match = re.match(r'^S([A-Z]\d{0,3})$', code)
                if letter_format_match and province != '川':
                    raise ValueError("字母格式的省级高速编号仅限四川省使用")

        return self
```

**关键技术点**：

1. **`model_validator` vs `field_validator`**：
   - `field_validator` 只能访问当前字段的值
   - `model_validator(mode='after')` 可以通过 `self` 访问所有字段
   - 当验证需要跨字段检查时，必须使用 `model_validator`

2. **验证顺序**：
   - `field_validator` 先执行（如 `normalize_code` 转大写）
   - `model_validator` 后执行（使用处理后的值进行跨字段验证）

3. **前后端双重验证**：前端提供即时反馈，后端确保数据安全

#### 相关文件

**前端**：

- [`Home.vue`](frontend/src/views/Home.vue)：道路标志生成对话框
- [`TrackDetail.vue`](frontend/src/views/TrackDetail.vue)：导入对话框（单选按钮说明模式）
- [`Admin.vue`](frontend/src/views/Admin.vue)：后台管理对话框

**后端**：

- [`road_signs.py`](backend/app/api/road_signs.py)：道路标志 API 和验证逻辑
- [`road_sign_service.py`](backend/app/services/road_sign_service.py)：道路标志服务
- [`svg_gen.py`](backend/app/gpxutil_wrapper/svg_gen.py)：SVG 生成逻辑

## File Structure Highlights

```text
backend/
├── app/
│   ├── api/              # API 路由 (auth, tracks, admin, tasks, road_signs)
│   ├── core/
│   │   ├── config.py     # 配置（数据库、CORS、JWT 等）
│   │   ├── deps.py       # 依赖注入（get_current_user, get_current_admin_user）
│   │   └── security.py   # JWT 和密码哈希
│   ├── models/           # SQLAlchemy 模型
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # 业务逻辑层
│   └── gpxutil_wrapper/  # gpxutil 集成

frontend/
├── src/
│   ├── api/              # API 客户端（使用 axios）
│   ├── components/
│   │   ├── map/LeafletMap.vue    # 地图组件
│   │   └── charts/ElevationChart.vue
│   ├── stores/           # Pinia stores (auth, config)
│   ├── utils/            # crypto.ts (密码加密)
│   └── views/            # 页面组件
```

## Common Patterns

### 添加新的 API 端点

1. 在 [`backend/app/api/`](backend/app/api/) 创建路由文件
2. 使用依赖注入获取当前用户：`current_user: User = Depends(get_current_user)`
3. 管理员端点使用：`current_user: User = Depends(get_current_admin_user)`
4. 在 [`main.py:49-53`](backend/app/main.py) 注册路由

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

## Important Notes

1. **密码处理**: 修改登录/注册相关代码时，确保前端使用 `hashPassword()` 加密
2. **用户复用**: 用户创建时会复用已删除用户的用户名/邮箱，避免数据库唯一约束冲突
3. **配置 API**: 普通用户使用 `/auth/config`，管理员使用 `/admin/config`
4. **CORS**: 开发环境后端配置允许所有来源 (`CORS_ORIGINS = ["*"]`)
5. **网络访问**: Vite 配置使用 `host: '0.0.0.0'` 支持局域网访问
6. **地图 z-index**: 导航栏 `z-index: 1000`，地图容器 `z-index: 1`
7. **首用户管理员**: [`config.py:81`](backend/app/core/config.py) 配置 `FIRST_USER_IS_ADMIN = True`
8. **移动端 viewport**: `maximum-scale=1.0, user-scalable=no` 防止页面缩放

### 后台管理页面

后台管理页面（[`Admin.vue`](frontend/src/views/Admin.vue)）提供用户管理和系统配置功能。

#### 功能特性

1. **用户管理**：
   - 分页用户列表
   - 搜索用户名或邮箱
   - 按创建时间/用户名/邮箱排序
   - 按角色（管理员/普通用户）和状态（正常/已禁用）筛选
   - 设置管理员、禁用/启用用户、重置密码、删除用户

2. **系统配置**：
   - 注册开关控制
   - 邀请码要求设置
   - 地图提供商配置
   - 地图层启用/禁用和排序

3. **邀请码管理**：
   - 创建邀请码
   - 分页查看邀请码列表
   - 删除邀请码

#### 用户保护规则

后端 ([`admin.py`](backend/app/api/admin.py)) 实施了以下保护规则：

1. **不能操作自己**：不能修改自己的管理员状态、不能禁用自己、不能删除自己、不能重置自己的密码
2. **保护首位用户**：不能取消首位用户的管理员状态、不能禁用首位用户、不能删除首位用户、不能重置首位用户的密码
3. **保留至少一位管理员**：取消用户管理员身份或删除管理员时，系统至少需要保留一位管理员

#### Axios 数组参数序列化

**问题**：Axios 默认将数组序列化为 `roles[0]=admin&roles[1]=user`，但 FastAPI 期望 `roles=admin&roles=user` 格式（重复键名）。

**解决方案**：在 [`request.ts`](frontend/src/api/request.ts) 中配置 `paramsSerializer`：

```typescript
const request: AxiosInstance = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
  paramsSerializer: {
    indexes: null, // 数组序列化为 roles=a&roles=b 而不是 roles[0]=a&roles[1]=b
  },
})
```

#### 筛选按钮视觉反馈

当筛选项不是默认值时，筛选按钮会高亮显示（`type="primary"`）：

```typescript
const hasActiveFilters = computed(() => {
  const roleFilterActive = userRoleFilters.value.length !== 2  // 默认全选
  const statusFilterActive = userStatusFilters.value.length !== 1 || userStatusFilters.value[0] !== 'active'  // 默认只选"正常"
  return roleFilterActive || statusFilterActive
})
```

```vue
<el-button :type="hasActiveFilters ? 'primary' : ''">
  筛选
  <el-icon class="el-icon--right"><ArrowDown /></el-icon>
</el-button>
```

#### 移动端响应式布局

后台管理页面移动端布局 ([`Admin.vue`](frontend/src/views/Admin.vue))：

**用户筛选卡片**：

- 搜索框：全宽（`:xs="24"`）
- 排序按钮 + 筛选按钮：同一行，各占半宽（`:xs="12"`）
- 搜索框和按钮行之间有 8px 间距
- 排序按钮防止换行（`flex-wrap: nowrap`），缩小字体和内边距

```css
@media (max-width: 1366px) {
  /* 搜索框和按钮之间的间距 */
  .filter-card .el-row .el-col:nth-child(2),
  .filter-card .el-row .el-col:nth-child(3) {
    margin-top: 8px;
  }

  /* 排序按钮防止换行 */
  .sort-buttons {
    gap: 4px;
    flex-wrap: nowrap;
  }

  .sort-buttons .el-button {
    font-size: 11px;
    padding: 5px 8px;
  }
}
```

**地图层列表移动端排序按钮**：

- 桌面端使用拖拽手柄（`.desktop-only`）
- 移动端隐藏拖拽手柄，显示上下箭头按钮

```vue
<!-- 桌面端拖拽手柄 -->
<el-icon class="drag-handle desktop-only">
  <Rank />
</el-icon>

<!-- 移动端排序按钮 -->
<div class="mobile-sort-buttons">
  <el-button :icon="ArrowUp" @click="moveLayerUp(layer)" />
  <el-button :icon="ArrowDown" @click="moveLayerDown(layer)" />
</div>
```

#### 系统配置未保存更改保护

后台管理页面的系统配置 tab 实现了未保存更改的保护机制，防止用户意外丢失配置修改。

**文件**: [`frontend/src/views/Admin.vue`](frontend/src/views/Admin.vue)

##### 功能说明

1. **Tab 切换保护**：当从"系统配置" tab 切换到其他 tab 时，如果有未保存的更改，会弹出确认对话框
2. **路由离开保护**：使用 `onBeforeRouteLeave` 守卫，在用户尝试离开后台管理页面时检查是否有未保存的配置
3. **浏览器刷新/关闭保护**：监听 `beforeunload` 事件，在刷新或关闭浏览器时显示原生确认对话框

##### 实现要点

```typescript
// 1. 保存原始配置（深拷贝），用于检测未保存的更改
const originalConfig = ref<SystemConfig | null>(null)

// 2. 加载配置时保存原始状态
async function loadConfig() {
  const data = await adminApi.getConfig()
  Object.assign(config, data)
  // 保存原始配置（深拷贝）
  originalConfig.value = JSON.parse(JSON.stringify(config))
}

// 3. 检测配置是否有未保存的更改
function hasUnsavedConfigChanges(): boolean {
  if (!originalConfig.value) return false
  const currentConfig = JSON.parse(JSON.stringify(config))
  return JSON.stringify(currentConfig) !== JSON.stringify(originalConfig.value)
}

// 4. 保存成功后更新原始配置
async function saveConfig() {
  await configStore.updateConfig(updateData)
  ElMessage.success('配置保存成功')
  originalConfig.value = JSON.parse(JSON.stringify(config))
}

// 5. 监听 tab 切换
watch(activeTab, async (newTab, oldTab) => {
  if (oldTab === 'config' && hasUnsavedConfigChanges()) {
    try {
      await ElMessageBox.confirm('系统配置有未保存的更改，确定要离开吗？', '提示', {
        confirmButtonText: '离开',
        cancelButtonText: '留在本页',
        type: 'warning',
      })
      // 用户选择离开，重置为原始配置
      if (originalConfig.value) {
        Object.assign(config, originalConfig.value)
      }
    } catch {
      // 用户选择留在本页，切回原来的 tab
      activeTab.value = oldTab
    }
  }
})

// 6. 路由离开守卫
onBeforeRouteLeave(async (to, from, next) => {
  if (activeTab.value === 'config' && hasUnsavedConfigChanges()) {
    try {
      await ElMessageBox.confirm('系统配置有未保存的更改，确定要离开吗？', '提示', {
        confirmButtonText: '离开',
        cancelButtonText: '留在本页',
        type: 'warning',
      })
      next()
    } catch {
      next(false)
    }
  } else {
    next()
  }
})

// 7. 浏览器刷新/关闭提示
function handleBeforeUnload(e: BeforeUnloadEvent) {
  if (activeTab.value === 'config' && hasUnsavedConfigChanges()) {
    e.preventDefault()
    e.returnValue = '' // Chrome 需要设置 returnValue
    return ''
  }
}

onMounted(() => {
  window.addEventListener('beforeunload', handleBeforeUnload)
})

onUnmounted(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
})
```

##### 关键技术点

1. **深拷贝**：使用 `JSON.parse(JSON.stringify())` 进行深拷贝，确保原始配置不受后续修改影响
2. **条件检查**：只在"系统配置" tab 且有未保存更改时才触发保护
3. **配置重置**：用户选择离开时，将当前配置重置为原始配置，避免"假保存"状态
4. **事件清理**：组件卸载时移除 `beforeunload` 监听器，避免内存泄漏
5. **路由守卫**：只有当前在"系统配置" tab 时才检查，从其他 tab 离开不受影响
