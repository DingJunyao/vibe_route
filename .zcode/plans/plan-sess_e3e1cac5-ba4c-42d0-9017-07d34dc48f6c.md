plan=# 各地图 SDK 回放导出完善（参照 amap_remotion 方案）

## Context

此前用各家 SDK 地图为背景录制轨迹回放非常困难。`~/code/amap_remotion` 给出了可参考的方案：逐帧驱动真实 SDK 地图（setCenter/setRotation）+ 画面收敛轮询 + 截图；它"能动但方向不对、轨迹抖动严重"，而其 `TRACK-REPLAY-NOTES.md` 正好记录了修正这些缺陷的方法（相机平滑、航向窗口测向圆滑、亚像素跳帧、收敛轮询）。

vibe_route 已有完整录屏任务管线（后端 Playwright 双模式采集 + 任务队列，`engine=sdk` 与 Leaflet 同源），SDK 引擎相比参照项目缺 4 块能力：

1. **SDK 适配器没有 `waitForIdle()`**（仅 LeafletMap 实现）→ 逐帧模式退化为固定 250ms，瓦片没画完就截图（灰块）。
2. **没有 SDK 渲染收敛检测**——SDK 无 pendingTileCount DOM 信号（现有 `pendingTileCount()` 只认 Leaflet），AMap 也没有 renderComplete 事件。
3. **没有亚像素跳帧**——SDK 对微小移动去重会导致 moveend 不触发、等待链悬挂（amap_remotion 踩过的坑）；静止段每帧仍全量等待。
4. **方位角数学缺陷**：`animationUtils.ts` `interpolatePosition` 对 bearing 裸线性插值（350°→10° 绕远路反向长弧）；无任何平滑 → track-up 旋转抖动；相机用原始插值位置，GPS 噪声直接入镜。

另：`AMap.vue` 初始化 `viewMode:'2D'`（AMap.vue:902），JSAPI 2.0 旋转需 3D 视图，导出 track-up 可能静默无效——实现时实测确认。

用户未对「平滑范围」提问作答，按推荐方案执行：**平滑全局生效**（交互回放与导出共用同一套相机计算）。

## 改动

### 1. 渲染收敛等待（新 util + 四个 SDK 适配器实现 waitForIdle）

- 新增 `frontend/src/utils/animation/renderIdle.ts`：`waitForRenderIdle(container, opts)` —— 移植 amap_remotion `GpxDriveVector.tsx` L177-212 的收敛判定：双 rAF → 轮询地图容器主画布 64×64 缩略图 `toDataURL`，连续 2 次采样不变（≥350ms 起判，2.5s 兜底强制放行）才返回；容器无 canvas（DOM 渲染引擎如百度 Legacy）退化为固定 400ms；drawImage/toDataURL 异常按 `'err'` 信号处理不阻塞。
- `AMap.vue` / `BMap.vue`（GL 与 Legacy）/ `TencentMap.vue` / `GoogleMap.vue` 的 animationAdapter 各自新增 `waitForIdle()`：先 race 引擎事件（AMap/BMap `moveend`、Google `idle`，300ms 超时；腾讯无可靠 idle 事件直接进轮询）→ `await waitForRenderIdle(容器)`。接口已在 `useAnimationMap.ts:61` 预留，`waitForMapIdle()`（L190-195）自动走新实现，无需改动。

### 2. 亚像素跳帧（`TrackAnimationPlayer.vue` 的 `__seekExportFrame`）

记录上次 seek 的相机状态（lat/lng/bearing/zoom）；本次与上次相机位移 < 0.6px（按当前 zoom 的 m/px 换算，复用 `getFixedCenterZoom` 同款 156543.03 公式）且 |Δbearing| < 0.06° 且 zoom 未变 → 直接 return 复用上一帧画面（不调 `updateAnimation`、不等 idle）。解决 SDK 亚像素移动去重导致 moveend 不触发的问题，静止段大幅提速。引擎切换/组件重挂载时重置记录。

### 3. 方向与抖动修正（新 util + 播放器接线）

- 新增 `frontend/src/utils/animation/cameraSmoothing.ts`（移植 amap_remotion `track.ts` 数学，适配 TrackPoint 结构与 CRS 字段选择）：
  - `smoothedCameraAt(t, points, startTime, crs)`：±1.5s 7 采样滑动平均（相机/固定中心标记专用；画线仍用原始点）。
  - `cameraHeadingAt(t, points, startTime)`：±2.5/5/10/20s 窗口测向（窗口位移 <6m 视为静止）→ ±1s 圆周平滑（circular mean，不可算术平均）；静止时向前/向后最多 4min 找运动方向，找不到回退播放器缓存的上次航向。内部位置采样走精简二分+线性插值，时间数组按 points WeakMap 缓存。
  - 点无时间数据时返回 null，调用方回退旧行为。
- `frontend/src/utils/animationUtils.ts` `interpolatePosition`（L144-151）：bearing 插值改最短路径角差（复用同文件已有 `calculateShortestRotation`），修复 350°→10° 绕远 bug——全局受益（交互+导出、全引擎）。
- `TrackAnimationPlayer.vue` `updateAnimation`（L365-414）：
  - fixed-center：相机中心与移动标记均用 `smoothedCameraAt` 平滑位置（标记恒居中，与「固定中心」语义一致；full 模式标记仍用原始位置压线）；`getFixedCenterZoom` 继续用原始 pos.speed/lat。
  - track-up 旋转角与标记朝向用 `cameraHeadingAt`；north-up 时标记朝向也用平滑航向（更稳），无时间数据回退 `pos.bearing`。
  - HUD 信息、移动端 `position-changed` emit 保持原始值（信息展示用途）。

### 4. SDK 导出模式初始化参数（AMap.vue）

- `AMap.vue` initMap 检测 `document.body.classList.contains('export-mode')` 时改用：`viewMode:'3D'`（2D 下 setRotation 无效）、`animateEnable:false`、`dragEnable:false`、`zoomEnable:false`、`rotateEnable:true`、`WebGLParams:{preserveDrawingBuffer:true}`（WebGL 画布可读回，收敛轮询依赖；headless 降级 DomRender 也不受影响）。交互模式维持 `viewMode:'2D'` 不变。
- 实现时实测确认：JSAPI 2.0 2D 下 setRotation 是否确实无效；百度 GL `enableRotate:false`（BMap.vue:1030）是否影响程序化 setHeading（预期不影响，只禁手势）。实测若 2D 能转则 3D 改动仅保留 animateEnable/preserveDrawingBuffer。

### 5. 后端小调整

- `backend/app/utils/playwright_export.py` L274：逐帧总预算 `frame_count * 2.5 + 120` → `frame_count * 3.0 + 120`（SDK 单帧 idle 上限 2.5s 后原预算不足）。

### 明确不做

- 不改任务队列/调度器/预热页逻辑；不新增导出弹窗选项；不改交互模式地图初始化（AMap 交互仍 2D）；百度 Legacy 仍不支持旋转（维持 warn）；Google 本机无法加载 SDK，仅代码层实现（heading 仅矢量底图生效的既有 try/catch 保留，符号无法实测校准）；流式模式（>30s 输出）的 SDK 瓦片门控维持现状（靠预热页 + 实时节奏）。

## 验证

1. `npx vite build` 通过（vue-tsc 本机不可用）。
2. 数值先验（参照项目方法论「先出数值再出画面」）：headless Chromium 里对 `cameraHeadingAt` 打印若干时刻航向序列，确认直道稳定、转弯圆滑、静止段保持。
3. 截图对比（项目 `.venv` Playwright + headless Chromium + localStorage token 注入，账号 billding）：track 90（巴厘岛）在 amap / tencent / baidu(GL) / leaflet(对照组) 四引擎下 `export=true&engine=...` 页面 `__seekExportFrame` 抽帧截图——检查：无灰块瓦片、track-up 旋转方向与 Leaflet 对照一致（顺带校准百度 GL setHeading 符号）、标记居中朝上、亚像素跳帧生效（静止段 seek 立即返回）。
4. 端到端冒烟：`POST /api/animation/export?track_id=90`（start_time 取末段、speed=8 压到 ≤30s 输出走逐帧模式），amap 引擎跑通产出 mp4，抽首/中/尾帧确认画面。
5. 文档：按项目规范更新 `agents/features.md`（轨迹回放-视频导出节）与 `agents/changelog.md`。

改动不自行提交（当前工作区 master 干净；遵守禁用 `git add -A` 规则）。