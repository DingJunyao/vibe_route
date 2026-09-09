# 变更历史

详细历史版本已归档到 `ref/CLAUDE_ARCHIVE.md`，以下是简要记录：

## 2026-09

- 添加 Docker 支持（参考 live_calc 方案）：根级多 target Dockerfile（`frontend-builder`/`backend`/`all-in-one`/`frontend`，backend 含 playwright chromium + libcairo2）、`docker-compose.example.yml`（all-in-one 一体化）+ `docker-compose.split.yml`（前后端分开）、`deploy/`（nginx 模板含 WebSocket upgrade + `/exports` 反代、supervisord、entrypoint 脚本）、`.dockerignore`、`.github/workflows/docker-publish.yml`（GHCR 必推 + Docker Hub 可选，amd64/arm64，aio/frontend/backend 三 variant 标签）。旧失效开发模式 docker-compose.yml 删除（引用的 Dockerfile/app.worker 均不存在；后端实际未使用 Redis/Celery），docker-compose.yml 入 .gitignore（用户从 example 复制自定义）
- 修复任务路由双前缀 bug：`tasks.py` router prefix `/api/tasks` 与 `main.py` include 的 `/api` 拼接成 `/api/api/tasks/*`（其它 router 均无此问题），任务下载 404；改为 `/tasks`。同步修复前端 `task.ts` 下载 URL 拼接（改用 `getBackendOrigin()` 统一后端 origin 逻辑，废弃 `VITE_API_URL` 依赖及 Dockerfile 构建参数）
- 修复 `/health` 健康检查 SQLAlchemy 2.x 警告（`execute("SELECT 1")` 改 `text("SELECT 1")`），database 状态恢复 healthy（此前误报 degraded）
- 前后端端口自定义：后端 `APP_HOST`/`APP_PORT` 环境变量（`run.py` 读取，原硬编码 8000）；前端 `VITE_DEV_PORT`/`VITE_DEV_BACKEND_URL`（vite.config.ts 读取，原硬编码 5173/8000）；compose 宿主端口 `${APP_PORT:-80}`
- 实现动画导出服务端录制（Playwright `record_video`）：前端导出模式（`?export=true` 自动播放、`body.dataset` 进度/完成信号）、token 注入复用登录会话、`FRONTEND_URL` 配置、整体超时兜底 `(时长/速度)*2+60s`
- 导出画面与用户视图一致：起点（currentTime）、相机/朝向/标记样式、地图图层（`exportLayerId`）、缩放中心（UniversalMap 暴露 `getCurrentViewState`/`setMapViewState` + 全局视图状态提供者）随请求传递
- 导出模式强制桌面布局：`isMobile`/`isTallScreen` 导出感知 + `body.export-mode` CSS 恢复桌面布局（修复低分辨率录制视口命中移动端媒体查询导致地图容器高度塌陷）
- 导出画面全屏地图：`body.export-mode` 隐藏页面头部/右侧面板/图表卡片/图层切换/缩放/全屏/动画入口/键盘快捷键等控件；控制面板（AnimationHUD）导出模式不渲染，信息浮层由 showHUD 开关控制；`show_hud=0` 时同时关闭信息浮层
- 导出画幅 zoom 修正：用户 zoom 基于详情页画幅调整，导出画幅（分辨率视口）不同——按最小维度比例 `log2(export_min/viewport_min)` 修正 zoom，保证用户构图内容完整包含在导出画面中（前端上报地图画幅尺寸，后端计算）
- 导出信息浮层增加进度/当前时间/剩余时间行；下载修复：`downloadFile` 拼接后端 origin（相对路径被 Vite SPA fallback 返回 HTML）；ffmpeg 裁剪录制开头遮罩期（可用时），视频从地图起点画面开始
- 修复 `AnimationExportTask` 模型未继承 `Base`、缺少外键（任务创建 500、mapper 配置失败）
- 修复 `TrackDetail.vue` 导出路径（移动端 HUD `@export` 打开对话框、`exportApi` 误传、缺失 `videoExport` 导入）
- 导出对话框移除格式/帧率选项（Playwright 固定 webm、帧率不可控）；任务状态补充 `cancelled`
- 修复动画导出 404：`videoExport.ts` 三处原生 `fetch` 硬编码 `/api/v1` 前缀且未带认证头，改用统一 `http` 客户端（`baseURL='/api'` + 自动 token，轮询请求 `skipProgress`）
- 修复动画导出 500：`animation_export.py` 误用 `TrackPoint.index`（模型字段实为 `point_index`），是被 404 掩盖的历史遗留 bug
- 后端 `main.py` 挂载 `/exports` 静态目录（`StaticFiles`，指向 `settings.EXPORT_DIR`），修复动画导出 `download_url` 无法下载
- 修复 `TrackDetail.vue` 向 `exportWithPlaywright` 误传 `exportApi`（API 对象）作为 `onProgress` 导致轮询崩溃，改为空回调
- 合并轨迹功能（多段轨迹按时间合并、重叠自动去重、地图预览、原轨迹保留）
- 合并预览空缺补全：段间隔 >5 分钟判空缺，衔接线渲染（空缺橙虚线/正常灰实线）+ 警告与明细，不生成插值点
- 地图引擎虚线渲染补齐：Google Symbol repeat 方案、腾讯 dashArray、Leaflet 空格分隔解析；修复 LeafletMap 挂载后不绘制 customOverlays 的缺陷
- 上传/合并成功后自动跳转到新轨迹详情页（原先分别跳轨迹列表/询问是否查看）
- 修复 Google 地图认证失败时无法切换图层：认证失败（gm_authFailure）地图实例存在但 `getCenter()` 返回 undefined，`getCurrentViewState` 抛 TypeError 中断 `switchLayer`（`currentLayerId` 赋值不执行，用户被困坏地图）。重构 `getCurrentViewState` 为 `getActiveMapInstance` + `normalizeCenter`（统一处理高德/百度/Leaflet 属性式与 Google/腾讯方法式 LatLng，及异常状态），`switchLayer` 视角保存加 try-catch；GoogleMap 增加 `gm_authFailure` 监听输出诊断指引
- 地理编码填充支持增量模式：`fill_geocoding_info` 增加 `incremental` 参数（仅处理 province 为空的点，不覆盖已有数据），API `POST /tracks/{id}/fill-geocoding?incremental=true`，前端已填充轨迹的确认对话框改为三选（仅补充缺失/全部重新填充/关闭）；增量无缺失点时直接标记 completed。背景：印尼轨迹 GPX 导入后填充时 Nominatim 数据源缺当地数据，43 个点（0.37%）province 为 NULL，区域树按"每次 province 变化新建节点"渲染成约 43 个"未知区域"，换数据源后增量补漏秒级完成（全量重刷需 40-60 分钟）

## 2026-01

- DateTime 时区统一为 timezone-naive UTC
- 地理编码失败跟踪
- PostGIS 空间计算支持
- 实时记录架构改进（一对一 Track）
- 地理编码服务配置缓存

## 2026-02

- 多边形几何字段 + Shapely 精确匹配
- 省辖县级行政单位分类修复
- 地理信息编辑器（刻度条、撤销/重做、空块操作）
- 地图缩放（海报导出）
- 分享嵌入模式
- 轨迹插值功能
- 覆盖层模板编辑器（空格键拖动、坐标系统重构）

### 文本对齐功能完善

- 添加垂直对齐控制（上/中/下）
- 两端对齐对所有行生效
- 添加"自定义文本"数据源选项
- 示例文本支持多行输入
- 修正文本整体高度计算（排除最后一行下方空间）

### GB 5765 字体支持

- 后端启动时预转换为 WOFF2 格式（`_convert_gb5765_fonts_to_woff2()`）
- 删除问题表（VDMX、GASP、GDEF、GPOS、GSUB、gasp、gvar、fvar、STAT、trak、kern、vhea、vmtx）
- 重建最小化 post 表（format 3.0）
- WOFF2 缓存机制（`backend/data/fonts/woff2_cache/`）
- 前端动态加载字体（`user_font_${fontId}` 命名）
- `OverlayTemplateEditor.getFontFamilyName()` 支持用户字体映射
- `FontSelector` 为 GB 5765 字体添加时间戳绕过浏览器缓存

### 覆盖层模板编辑器 UI 完善

- 安全区输入框宽度统一（使用 visibility: hidden 占位）
- 前缀后缀输入框支持多行文本（textarea, 2 行）
- 示例文本输入框高度与描述输入框一致（2 行）
- 画布宽高输入框和字体下拉框宽度延伸到右边（100%）
- 画布渲染支持用户/管理员上传字体

### 轨迹动画功能完善

- 标记样式切换（箭头/汽车/人员）
- 播放控件显示控制（默认隐藏，点击播放按钮后显示）
- 所有标记样式支持方位旋转
- 使用 `vehicle.svg` 和 `location.svg` 图标替代 CSS 绘制
- 添加样式缓存避免标记闪烁

### Leaflet 地图坐标系统修复

- 修复了百度地图标记旋转问题（使用 class 选择器而非通用 div 选择器）
- 修改了 `getCoordsByCRS()` 函数，根据地图提供商选择正确坐标系：
  - 天地图：使用 WGS84 坐标（leaflet.chinatmsproviders 会自动转换）
  - 高德/腾讯地图：使用 GCJ02 坐标（插件期望 GCJ02 坐标）
  - 百度地图：使用 BD09 坐标
- 修改了 `TrackAnimationPlayer.vue` 的 `isGCJ02Provider` 逻辑，正确识别高德/腾讯地图
- 修复了 `setAnimationPlaying()` 函数，让灰色轨迹也使用 `getCoordsByCRS()` 来正确选择坐标系统（之前硬编码 WGS84）
- 减少了调试日志输出，保持关键信息
- 结果：所有 Leaflet 地图的轨迹（红色/灰色）和标记点现在都正确

### 腾讯地图动画标记和 HUD 控制修复

- 动画标记显示默认样式：`TMap.DOMOverlay.extend` 不是一个函数，改用 Canvas 绘制旋转后的图标并转换为 data URL
- HUD 控制无响应：点击事件监听使用了 `useCapture: true`，改为 `useCapture: false` 让事件在冒泡阶段处理
- `updateStyles` API 错误：`TMap.MultiMarker` 没有 `updateStyles` 方法，改用 `setStyles` 方法
- HUD 被覆盖：腾讯地图的控件层（`z-index: 1000`）覆盖了 HUD，将 HUD 的 `z-index` 提高到 `10000`
- 结果：腾讯地图的动画标记和 HUD 控制都正常工作

### 腾讯地图动画标记 DOM 实现重构（2026-02-17）

- 问题：Canvas 方式导致标记旋转时变形和闪烁
- 解决方案：重写 `AnimationDOMOverlay` 类，使用普通 DOM 元素 + CSS transform
- 核心实现：
  - 使用 `TMap.projectToContainer()` 将地理坐标转换为像素坐标（而非不存在的 `mapFromLngLat`）
  - 外层 `element` 绝对定位，内层 `innerElement` 用于 CSS `rotate()` 旋转
  - 监听 `moveend` 和 `zoomend` 事件，确保地图移动/缩放时标记自动更新位置
  - 标记尺寸：car 60×40，arrow/person 36×36
  - z-index: 999，确保在 HUD（10000）下方

## 2026-02-18

### 轨迹动画功能完善

- 在 BMap.vue 的 `animationAdapter` 中添加了缺失的 `fitTrackWithPadding(bottomPaddingPx: number)` 方法
- 修复了全轨迹模式下切换地图时百度地图不缩放的问题
- 清理了回放时产生的大量调试日志：
  - 删除了 `[BMap] setMarkerPosition` 每帧输出
  - 删除了 `[BMap] rotateMarker applied` 标记旋转日志
  - 删除了 `[AnimationMap]` composable 中的所有日志（adapter registered/unregistered, setPassedSegment, setMarkerPosition, setCameraToMarker, fitTrackWithPadding）
  - 删除了 `[TrackAnimationPlayer]` 中的 export progress 和地图切换日志
- 保留了错误相关的 `console.warn`（如不支持旋转、无法获取坐标等）
- 结果：回放时日志输出大幅减少，便于调试查看重要信息

## 2026-02-23

### Chrome DevTools MCP 环境配置

- **Linux 系统浏览器适配**：
  - 检测到系统使用 `/usr/bin/chromium` 而非 Google Chrome
  - 修改 MCP 配置文件 `~/.claude.json` 中的 `chrome-devtools` 服务器配置
  - 使用 `--browserUrl` 参数连接到现有浏览器实例（`http://127.0.0.1:9222`）
  - 配置内容：
    ```json
    "chrome-devtools": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "chrome-devtools-mcp@latest",
        "--browserUrl",
        "http://127.0.0.1:9222"
      ]
    }
    ```
- **使用方式**：
  - 以远程调试模式启动 Chromium：`chromium --remote-debugging-port=9222`
  - 重启 VS Code 让 MCP 服务器读取新配置
  - 通过 Chrome DevTools MCP 工具直接操作浏览器中的页面
- **可用的调试功能**：
  - 查看页面列表和内容
  - 操作页面元素（点击、填写表单、悬停等）
  - 查看控制台消息和网络请求
  - 执行 JavaScript 代码
  - 性能分析
  - 模拟不同设备视口和网络条件

## 2026-02-22

### 移动端轨迹回放功能修复

- **动画标记显示问题**：
  - 在 `TrackAnimationPlayer.vue` 中添加播放状态变化和 seek 操作时的 `updateAnimation()` 调用
  - 添加 `position-changed` 事件监听到 `TrackDetail.vue`，用于更新 HUD 的位置数据
  - 在移动端布局中添加 `TrackAnimationPlayer` 组件（之前只在桌面端）
  - 修复 `updateAndEmitPosition` 缺失 `getLastPosition` 方法的问题，添加位置缓存机制

- **HUD 位置信息更新问题**：
  - 在 `TrackDetail.vue` 中添加 `handleAnimationPositionChanged` 函数处理 `position-changed` 事件
  - `currentPosition` ref 正确接收并传递给 `AnimationHUD` 组件

- **图表渲染问题**：
  - 为桌面端和移动端使用不同的 chartRef（`desktopChartRef` 和 `mobileChartRef`）
  - 修复骨架屏 `loading` 变量未定义问题（改为 `!track && !loadFailed`）
  - 移除错误的 `loading.value = false` 赋值

- **进度条时间计算错误**：
  - 修复 `duration` 计算错误，移除多余的 `* 1000`（`calculateDuration` 已返回毫秒）

- **标记样式按钮显示问题**：
  - 恢复移动端标记样式按钮显示，移除 `v-if="!isMobile"` 条件

- **调试工具**：
  - 启用 eruda 调试工具（开发环境）
  - 添加关键位置的调试日志（播放状态、位置更新、图表渲染等）

- **结果**：
  - 移动端轨迹回放功能完全修复
  - 地图动画标记正常显示
  - 进度条和播放时间正确显示
  - 海拔和速度图表正常渲染
  - HUD 位置信息（时间、速度、海拔）正确更新
  - 标记样式按钮在移动端正常显示

### 腾讯地图移动端标记点定位修复（2026-02-22）

- **问题**：移动端轨迹回放时标记点不显示
- **根因分析**：
  - `AnimationDOMOverlay` 元素缺少 `top: 0; left: 0;` 初始定位
  - 导致元素被流式布局到容器底部（`offsetTop: 253` 等于容器高度）
  - `translate3d` 偏移被加到了错误的基础位置上

- **修复**：
  - 在 `AnimationDOMOverlay` 构造函数中添加 `top: 0; left: 0;` 到元素样式
  - 增强容器查找逻辑，优先选择 canvas 父级作为目标容器
  - 添加容器样式诊断日志（position、overflow、尺寸等）
  - z-index 从 999 提高到 10000

- **移动端缩放修复**：
  - 将底部 padding 从固定 100px 改为容器的 10%
  - 确保移动端视野合理显示轨迹

- **结果**：
  - 移动端标记点正确显示在轨迹位置
  - 日志显示 `elementOffset.offsetTop` 从 253 降至 0
  - `elementRect.y` 与 `parentRect.top + newTop` 对齐

### 桌面端和移动端轨迹回放功能统一适配（2026-02-23）

- **桌面端控制浮窗和信息浮层显示修复**：
  - 在 `TrackAnimationPlayer.vue` 中使用 `v-if="!isMobile"` 条件渲染桌面端组件
  - 恢复桌面端的 `AnimationHUD` 组件渲染
  - 恢复桌面端的信息浮层（`info-panel`）
  - 添加 `isMobile` 计算属性用于判断当前是桌面端还是移动端
  - 恢复 `currentPosition` 计算属性和相关的格式化函数（`formatTime`、`formatSpeed`、`formatElevation`）
  - 保留移动端的位置计算和 `emit` 逻辑（`updateAndEmitPosition`）

- **桌面端全轨迹模式缩放逻辑修复**：
  - 恢复 `handleHeightChanged` 函数，用于监听 HUD 高度变化并调整地图视野
  - 恢复 `hudHeight` 状态
  - 恢复相机模式变化时的缩放逻辑：`fitTrackWithPadding(hudHeight.value + 20)`
  - 恢复地图切换时的缩放逻辑
  - 这些逻辑只对桌面端生效（因为移动端不调用 `handleHeightChanged`）

- **移动端标记点移动修复**：
  - 问题：移动端在 `updateAnimation()` 函数中调用了 `updateAndEmitPosition.getLastPosition?.()`，但 `updateAndEmitPosition()` 本身从未被调用
  - 修复：在 `updateAnimation()` 函数开始时，如果是移动端，先调用 `updateAndEmitPosition()` 更新位置

- **AnimationHUD 样式修复**：
  - 调整模板结构，将 `hudContentRef` 绑定到内部的 `div.hud-content` 元素上
  - 桌面端：定位在底部居中，使用半透明背景和阴影效果
  - 移动端：使用静态定位（不定位），样式由父容器控制
  - 移除调试用的 `watch` 监听代码

- **移动端兼容性**：
  - 移动端的 `AnimationHUD` 在 `TrackAnimationPlayer` 中不渲染（通过 `v-if="!isMobile"` 控制）
  - 移动端的控制卡片仍然由 `TrackDetail.vue` 中的独立 `AnimationHUD` 组件处理
  - 移动端的 `position-changed` 事件正常发送，用于更新卡片中的信息显示

- **结果**：
  - 桌面端：点击开始回放按钮，控制浮窗和信息浮层正常显示
  - 桌面端：全轨迹模式下，缩放逻辑正确考虑 HUD 高度，轨迹填充画幅（除 HUD 高度外）
  - 移动端：标记点正常移动，位置信息正确更新
  - 桌面端和移动端功能互不干扰，各自保持原有体验

## 2026-09-06

### Google 地图支持

- **单一 `google` 图层**（与高德/腾讯一致的引擎选择模式）：
  - 配置了 `api_key` → Google Maps JS API SDK 引擎；未配置 → Leaflet 瓦片（GCJ02，瓦片源 `www.google.cn`，大陆直连）
  - 后端 `config_service.py` 新增 `google` 图层默认配置（含 `api_key` / `api_base_url`），合并时自动清理已废弃的 `google_js` 图层
- **SDK 引擎**：
  - 新建 [`GoogleMap.vue`](../frontend/src/components/map/GoogleMap.vue)：完整引擎（轨迹渲染、图表联动、自定义 tooltip、高亮、fitBounds、海报缩放、动画适配器）
  - 坐标系 WGS84；坐标↔像素转换使用 OverlayView 投影助手（`toContainerPixel` / `toLatLng`）
  - [`UniversalMap.vue`](../frontend/src/components/map/UniversalMap.vue) 新增 `useGoogleEngine` 路由，未配置 Key 时回退 Leaflet
  - 海报生成与动画视频导出强制后端 Playwright（WebGL/瓦片 CORS 限制，同百度处理）
- **反向地理编码**（`google` provider）：
  - [`geocoding.py`](../backend/app/gpxutil_wrapper/geocoding.py) 新增 `GoogleGeocoding`（`/maps/api/geocode/json`，WGS84 输入，支持 `get_en_result`、`freq` 限流、`api_base_url` 反向代理）
  - 行政区划映射：`administrative_area_level_1/2` → 省/市，`locality`/`sublocality` → 区，`sublocality_level_1/2` → 街道；道路名遍历 `route` 组件
- **Schema**：`MapLayerConfig` 新增 `api_base_url` 字段；`GeocodingProvider` 新增 `GOOGLE`
- **管理后台**：地图配置区 Google Key/地址输入框；地理编码提供商新增 Google 选项及配置表单
- **数据库**：无需迁移（config 为 key-value JSON，默认配置自动合并补全）
