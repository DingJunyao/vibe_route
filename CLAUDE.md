# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Vibe Route** 是一个基于 [gpxutil](https://github.com/DingJunyao/gpxutil) 构建的全栈 Web 轨迹管理系统。用户可以上传 GPX 文件，系统会解析轨迹数据，进行坐标转换（WGS84/GCJ02/BD09）、地理编码填充，并在地图上可视化展示。

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
