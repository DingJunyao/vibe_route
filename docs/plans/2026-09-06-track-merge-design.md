# 合并轨迹功能设计

日期：2026-09-06（空缺补全增强：2026-09-07）
状态：已确认

## 需求

- 选择多段轨迹合并为一条新轨迹，按时间顺序组合
- 合并前可预览效果（地图 + 统计信息）
- 原轨迹全部保留，不做任何修改；用户如需删除须自行操作
- 时间段重叠时自动去重（重叠区间保留时间靠后的段），并向用户提示
- 段间时间空缺需要补全（不插值，衔接保持连续结果），预览地图上着重提示

## 交互设计

- 独立页面 `frontend/src/views/TrackMerge.vue`，路由 `/merge`
- 入口：轨迹列表页头部工具栏"合并轨迹"按钮（桌面直接显示，移动端在下拉菜单）
- 两步式流程（el-steps）：
  1. **选择轨迹**：表格多选（含实时记录产生的轨迹，进行中的实时记录不可选），支持搜索，按开始时间排序；实时显示已选轨迹的时间顺序；至少 2 条才能下一步
  2. **预览与确认**：地图绘制合并轨迹，各源轨迹段不同颜色区分；侧栏展示合并统计（总距离、总时长、点数、起止时间）与各段时间范围；重叠时显示警告条（含剔除点数明细）；输入新轨迹名称（自动生成默认值）与描述；确认合并
- 合并成功后提示并自动跳转新轨迹详情页（2026-09-07 调整，不再询问）

## 后端设计

无数据库表结构变更（复用 `tracks` / `track_points`）。

### API 端点（backend/app/api/tracks.py）

- `POST /api/tracks/merge/preview`：`{track_ids: []}` → 合并方案（不落库）
  - 段信息：id、名称、颜色序号、时间范围、保留/剔除点数
  - 重叠警告明细（按段剔除数）
  - 衔接信息 `gaps[]`：from_segment/to_segment/time_gap（秒，时间缺失为 null）/distance（米，水平 Haversine）/is_gap
  - 合并统计（距离、时长、爬升/下降、点数、起止时间）
  - 轻量点列表（经纬度 + segment_index，支持 crs 参数）
- `POST /api/tracks/merge`：`{track_ids, name, description}` → 新轨迹

### 服务层（backend/app/services/track_service.py）

- `merge_preview` / `merge_tracks` 共用 `_build_merge_plan`（预览与执行同一逻辑）
- 算法：
  1. 校验：≥2 条、存在、属主匹配
  2. 段按 `start_time` 升序；点按 `time asc, created_at asc` 加载
  3. 去重（后段优先）：排序键 = `time`（空则回退 `created_at`）；每段截断于下一段首点排序键（`>=` 边界归后段），重叠区间保留时间靠后的段
  4. 空缺判定：基于非空段序列，相邻段「前段末点时间 → 后段首点时间」间隔 > `MERGE_GAP_THRESHOLD_SECONDS`（300 秒）判为空缺；任一端时间缺失则 `time_gap=null`、`is_gap=false`
  5. 统计重算：距离（相邻点累计）、时长、爬升/下降，与 `create_from_gpx` 同口径
  6. 落库：新 `Track`（`original_crs` 取首段、`original_filename` 形如 `merge:1+5+9`）；分批 500 条复制点（保留坐标/海拔/速度/地理编码/备注/`is_interpolated`；`interpolation_id` 置空）；`point_index` 重编号；`has_area_info`/`has_road_info` 按源点数据判定

## 前端设计

- API 封装新增 `mergePreview` / `mergeTracks`
- 地图预览复用现有地图适配体系（高德/百度 GL/Legacy/腾讯/Google/Leaflet），每段一条彩色 polyline（调色板循环取色），含首末标记
- 响应式（断点 1366px）：桌面左地图右信息栏，移动端上下堆叠；选择步骤移动端卡片列表
- 前端先做粗略时间区间重叠检测，提前提示

## 空缺补全与预览提示（2026-09-07 增强）

不生成插值点；相邻段「末点 → 下一段首点」画衔接直线保持结果连续，空缺处醒目提示。

- **数据**：预览响应 `gaps[]`（见 API 设计）；前端 `MergeGapInfo` 类型（`frontend/src/api/track.ts`）
- **渲染**（`TrackMerge.vue` `mapOverlays` computed，走 `customOverlays` 的 `dashArray` 属性）：
  - 空缺衔接线：橙色 `#e6a23c` 虚线（`dashArray: '12 8'`，weight 5，opacity 0.95）
  - 正常衔接线：灰色 `#909399` 实线（weight 2）
- **提示**：地图图例（正常衔接/空缺衔接线样）；存在空缺时 el-alert 警告条 + 空缺明细列表（衔接段、时间间隔、直线距离）
- **各引擎 dashArray 实现差异**：
  - 高德：`strokeStyle: 'dashed'` + `strokeDasharray` 原样传字符串
  - 百度 GL/Legacy：`strokeStyle: 'dashed'` / `'solid'`（不支持自定义间隔）
  - 腾讯：`TMap.PolylineStyle.dashArray` 数组（解析 `'12 8'` → `[12, 8]`）
  - Google：不支持 `strokeDasharray`，用 Symbol repeat 方案（`icons` + path `M 0,-1 0,1` + `strokeOpacity: 0`）
  - Leaflet：`dashArray` 数组（解析兼容空格/逗号分隔）
- **附带修复**（LeafletMap.vue）：dashArray 解析原先按逗号分隔，空格格式 `'12 8'` 会退化为 `[12]`；`onMounted` 原先只调 `drawTracks()` 不绘制 overlays（watch 无 immediate，挂载时已有数据则永不绘制），改为 `updateTracks()` 与其他四引擎 init 尾部行为对齐

## 错误处理

- 预览与执行均重新校验；合并后有效点数为 0 → 400
- 落库单事务，失败整体回滚
- 前端接口异常 ElMessage 提示，停留在当前步骤

## 测试

- 后端 pytest：段排序、重叠去重（含空时间回退）、统计口径、字段复制完整性、`interpolation_id` 置空、原轨迹零修改、权限校验
- 前端：vue-tsc 类型检查与构建通过；手动验证桌面/移动端、多地图引擎预览
