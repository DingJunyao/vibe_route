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

## 地区（Region）与多语言

### 地区贯通

- **上传**: 上传对话框可选地区（中国 / 印尼），缺省 `cn`
- **编辑**: 编辑对话框可改轨迹地区。默认**只改轨迹行级**（新填充/新导入点的默认值）；勾选「同时更新已有轨迹点地区（共 N 个点）」（`sync_points_region=true`，**默认不勾选**）批量刷点级 region。**勾选即同步**，不要求地区变化——行级已对而点级错位时（如填充跑在旧代码上），勾选是唯一修复入口；未勾选但地区变了 → 保存时弹框确认（选「仅更改轨迹信息」不中止保存）。点级是图标渲染的权威，未同步时改地区**不会**让已有轨迹点换用新地区路牌
- **填充地理编码**: `POST /api/tracks/{id}/fill-geocoding` 支持 `region` 参数，缺省回读轨迹自身 region
- **CSV 行级 region**: 导入以文件内每行的 `region` 列为准（跨地区文件的主通道，一个文件可含多地区点）
- **合并轨迹**: 逐点复制点级 region
- **地图组件 tooltip（气泡）**: 与区域树同口径支持多地区——五个地图组件（AMap/BMap/Tencent/Leaflet/Google）共用 [`tooltipRoadSign.ts`](frontend/src/utils/tooltipRoadSign.ts)（模块级缓存五引擎共享），按**点级 region** 分派：cn 走 `parseRoadNumber` 国标解析；id 编号原样交后端判级，name 兜底链 road_name → road_name_id → road_name_en，nameId 传 road_name_id（TOL 判定）。数据流：详情页/分享页 `trackWithPoints` 映射透传 `region`/`road_name_id`/`road_name_en`（Point 接口已含）；**主页** `getPoints` 返回完整 TrackPoint 原样透传（`samplePoints` 仅采样不裁字段），气泡同样按点级 region 分派。多语显示文本仍由前端回退链处理（zh → id → en）

### 反向地理编码（多语）

- region=id 时 Nominatim 发**三次**请求（`zh-CN` / `id` / `en`），分别写中文列 / `_id` / `_en`
- 省级中文名回填表（**34 个印尼省 × 三语键 = 102 条**，自 gpxutil 移植，含前缀容错）；查不到中文时**留空**而非填英文
- 展示侧回退链 **zh → id → en**，故中文留空不会显示空段

### 道路图标

| 节点 region | 编号解析 | 生成 |
|------|------|------|
| `cn` | 前端 `parseRoadNumber` 解析国标编号 | 后端国标盾牌 |
| `id` | 前端**不解析**，编号原样交后端 | 后端按编号 + 路名判级，生成六边形盾牌 |

前端按节点 region 分派（详情页 [`TrackDetail.vue`](frontend/src/views/TrackDetail.vue)、分享页 [`SharedTrack.vue`](frontend/src/views/SharedTrack.vue)，共用 `renderNodeLabel`）。

- **id 等级判定**（后端）:
  - 3 位编号 → `PROVINSI`（蓝 `#003E86`）；1-2 位编号 → `TOL` / `NASIONAL`（均红 `#B5273C`）
  - `TOL` 条件：路名命中关键词（中文子串「收费」或 ASCII 词边界 `Tol`），或请求带 `force_tol=true`（前端「收费公路」勾选框，仅 1-2 位编号有效）
- **地区代码（kode wilayah）**: 交通部法规 `KP.1324/AJ.001/DRJD/2019 Lampiran I`，省级为 **1-34 序号**（东爪哇 `16`），**与 BPS/ISO 码无关**（旧表东爪哇为 `35`，已废弃）；县市码为 `省码.省内序号`（如 `16.17`）。色带来源按优先级：
  1. 编号内嵌前缀且命中值集（`16-024` → `PROVINSI 16`；`16.17-024` → `PROVINSI 16.17`）
  2. 内嵌前缀未命中（`99-024`、`abc-024`、`-024`、**旧数据 `35-024`**）→ 回退省名文本查表
  3. 省名文本（中/英/印尼语，含无前缀容错如 `Jawa Timur`）或直接传省码字符串（`16`）
  4. 都查不到 → 色带只显示等级词、不带地区码（如 `NASIONAL`）
- **生成入口**: 生成页 [`RoadSignGenerator.vue`](frontend/src/views/RoadSignGenerator.vue) 与主页内嵌对话框 [`Home.vue`](frontend/src/views/Home.vue) 均有地区切换；id 模式字段为 编号 / 中文路名 / 印尼语路名 / 省份文本 / 收费公路勾选框。主页的国标字体检查（`areFontsConfigured`）**仅 cn 分支执行**——印尼盾牌用 `data/fonts/` 的 Clearview 字体，与 A/B/C 配置无关
- **缓存键含 region**: 后端 `road_sign_cache` 与前端内存缓存均按 region 隔离；id 分支的键**还含路名与印尼语路名**（后端对两段文本联合判 TOL，防「同编号不同路名」串用同一张图）
- 生成失败回退纯文本
- **配置** `indonesia_road_sign`: `template`（`backend/data/templates/id_sheild.svg`）、`tol_keywords`、`font_upper` / `font_lower`（Clearview 字体，商业字体，许可记录在案）

### 区域树

- 端点 `GET /api/tracks/{id}/regions`
- 按 **(region, 文本)** 分组：同一文本不同 region 不合并 → 跨地区文件出现并列根节点（如「东爪哇省」与「广东省」两个根）
- 节点带 `names`（存在的语言才出现该键）与 `region`；道路节点带 `road_number`
- **多语 tooltip**: 原生 `title` 属性，`names` 中非空语言 ≥ 2 种时展示（如 `东爪哇省 / Provinsi Jawa Timur / Province of East Java`）；单语言**无 tooltip**
- 道路编号标牌受配置 `show_road_sign_in_region_tree` 控制（关闭则纯文本）

### 导入导出

- **导出 30 列**（原 22 列）: 新增 `region`，`province` / `city` / `area` / `road_name` 扩为 `_zh` / `_id` / `_en` 三列，另有 `road_num`
- **导入别名表**: 兼容三种列名格式——新格式（带语言后缀）、样例格式、旧版 vibe 导出（无后缀列按中文处理）
- 导出 → 再导入闭环成立（`region`、三语列、`road_name` 为空时的回退链均可往返）

### 已知限制

- **实时记录链路恒为 `cn`**: `live_recording_service.py` 走自己的内联地理编码（`geo_service.get_point_info(lat, lon)`），**不经过** `fill_geocoding_info` → 既不写 `*_id` 也不写点级 `region`；且 `LiveRecording` 模型**无 region 列**，`app/api/live_recordings.py` 调 `create_from_gpx` 不传 region → 模型默认 `'cn'`。后果：印尼实时记录的轨迹按 cn 渲染图标、走中文回退文本。**绕行方案**：录完后 `PATCH /api/tracks/{id}` 把 `track.region` 改为 `'id'`，再跑一次 fill-geocoding（`region` 缺省时后端回读轨迹自身 region）即可回填点级 region 与 `*_id`。**实时记录界面的地区选择属后续工作**（需新迁移 + 前端改造），列为本次范围外
- **Geo Editor（地理信息编辑器）不认识多语言字段**: `geo_editor_service.py` 读路径构造的 `TrackPointGeoData` 只含 `province` / `city` / `district` / `road_number` / `road_name` 及其 `_en` 对，写路径的 `field_mapping` 同样只映射这几对，**不含 `*_id`、不含 region**。后果：在 Geo Editor 里修改印尼轨迹的路名后，`road_name` 更新而 `road_name_id` 保持旧值 → **tooltip 与 TOL 判定读的是 `*_id`，会与实际路名不一致**。**无数据丢失风险**（`.values()` 只写列出的字段，不误伤 `*_id` / `region`）；**region 与图标不受影响**。修它要改 `app/schemas/geo_editor.py` + 前端 Geo Editor 界面，属独立议题；最小改动是给 `TrackPointGeoData` / `GeoSegmentUpdate` 加 `*_id` 字段并纳入 `field_mapping`
- **fill-geocoding 的地区/provider 不匹配只告警、不拦截**（本次范围内**唯一会静默填出整段错区数据**的路径）：`fill_geocoding_info` 有两条降级路径，均只打 `logger.warning` 后照常填充：
  1. **地区值非法**（`track_service.py:585-587`）：`region` 缺省时回读轨迹自身 region，若仍不在 `('cn','id')` 内则**静默按 `'cn'` 填充**。API 层用 `Literal['cn','id']` 校验（`api/tracks.py:511`），故正常请求到不了这里，只影响内部直接调用。
  2. **地区合法但 provider 不支持**（`track_service.py:639-645`，**可达**）：`region='id'` 而 provider 非 `NominatimGeocoding` 时同样只告警；默认配置正是 `gdf`（`config_service.py:27`，只服务中国）。随后照常用中文数据填充，并把 `point.region = 'id'`（L704）、`track.region = 'id'`（L752，注释写明「填充地区成为该轨迹的默认地区」）。**后果**：整轨点被标成印尼却只有中文数据，国标编号（如 `G221`）按 id 判级失败 → 原本的国标盾牌退化为纯文本。
  **未拦截的原因**：修它要先定产品语义（直接返回 400 拒绝，还是按 provider 自动分流），属独立议题；最小改动是在 API 层前置校验，或让 `fill_geocoding_info` 对 `region == 'id' and not supports_id` 直接置 `failed` 状态返回

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
