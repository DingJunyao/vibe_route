# 变更历史

详细历史版本已归档到 `ref/CLAUDE_ARCHIVE.md`，以下是简要记录：

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
