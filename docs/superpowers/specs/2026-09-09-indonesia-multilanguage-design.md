# 印尼多语言轨迹信息与道路图标适配设计

日期：2026-09-09

## 背景与目标

Vibe Route 此前仅针对中国大陆适配：轨迹点行政区划/道路名只存中文（无后缀列）与英文（`*_en` 列）；geocoding 按中国规则解析；道路图标为 GB 5768.2 国标样式（普通道路圆角矩形、高速绿盾牌）。现需：

1. 保存、导入、导出**多语言的轨迹信息**（地区名/道路名，中文 + 印尼语 + 英语）
2. 生成**其他地区的道路图标**（先印尼：六边形路牌），并能按地区在轨迹详情正确显示
3. 架构上**预留其他地区**的适配（region 可扩展）

参考：同作者项目 gpxutil（`D:\code\gpxutil`）最近完成印尼适配（提交 7b96599），其设计文档 `docs/plans/2026-09-09-indonesia-multilanguage-design.md` 与实现可直接借鉴移植。参考数据：样例多语言 CSV（`2026-08-29 15 49 16.csv`），地区/道路名列含 `zh`（无后缀）、`id`（印尼语，`_id` 后缀）、`en`（英语，`_en` 后缀）三种语言，`road_num` 形如 `3`（国家公路）、`35-024`（省道，前缀为省代码）。

## 决策记录

| 决策点 | 结论 |
|---|---|
| 多语言数据来源 | CSV/XLSX 导入与 geocoding 填充链路**都要**支持多语言 |
| 印尼轨迹中文译名 | 尽力而为：Nominatim 三语请求 + 内置 38 省译名表回查省级；仍缺则**留空**，前端显示回退到其他语言 |
| 展示形态 | 节点文本按回退链显示（zh → id → en → 原文）+ tooltip 展示全部语言 |
| 地区（region）判定 | **不自动判定、不按编号格式猜测**（香港快速路等纯数字编号会与印尼撞格式）；显式参数贯穿各入口，默认 `cn` |
| 图标体系归属 | **严格跟随 region**，权威在**点级**（`track_points.region`），跨地区轨迹（深港、港珠澳）由行级数据承载 |
| DB 多语言字段 | 语言后缀平铺列（沿用现有 `*_en` 惯例）：中文无后缀、新增 `*_id` 印尼语列（`id` = ISO 639-1 印尼语代码） |
| CSV/XLSX 列名 | 全显式语言后缀 `*_zh / *_id / *_en` + `region` 列；导入兼容样例/gpxutil 与旧版 vibe 导出列名（别名表） |
| 印尼 TOL 判定 | `\btol\b` 词边界（不误伤 `Toleransi` 等）+ 中文「收费」子串 |
| 旧轨迹 | 点级缺省 `'cn'`；跨地区旧轨迹需重新填充（选对 region）或行级导入修正 |
| 改动范围 | 覆盖层模板/海报/动画文本、前端 UI i18n、admin_divisions 扩区划、自动判定 均**不在本次范围** |

## 1. 总体架构

核心概念：**Region（地区）+ 语言后缀列**，两者独立：

- **Region**（`'cn' | 'id'`，可扩展）决定：① 图标用哪套模板/解析规则；② geocoding 请求哪些语言、按哪套规则解析。与 gpxutil 单 CLI 参数不同，本系统需要落库与跨地区支持，因此 region 有**点级权威存储**（见下）。
- **语言后缀列**承载多语言文本：数据按列自描述，与 region 无关——文件里有什么语言列就存什么、导出什么。

### Region 存储模型（三层）

| 表 | 列 | 语义 |
|---|---|---|
| `tracks` | `region`，默认 `'cn'` | 创建/修改轨迹时选择；作为**新点的默认 region** 与填充语言集默认 |
| `track_points` | `region`，默认 `'cn'` | **图标与显示的权威来源**（点级） |
| `road_sign_cache` | `region`，默认 `'cn'` | 同编号不同地区的图标不同，缓存键含 region |

region 值域与「编号解析器 + 图标生成器」注册表集中在后端一处（常量 + 分派函数），新增地区 = 注册新枚举值 + 解析器/生成器 + 语言集，不动现有分支。

### 点级 region 写入来源（谁产生点、谁标 region）

| 路径 | 行为 |
|---|---|
| GPX/CSV 上传创建轨迹 | 上传对话框选地区 → 作为 `track.region`，并注入全部新点 |
| CSV/XLSX 行级 `region` 列 | 有列 → 逐行写入（**跨地区文件的主通道**，如深港/港珠澳一次性导入）；无列 → 用轨迹级默认 |
| 修改轨迹 / 导入点覆盖更新（`import_points_from_file`） | 同上；可只覆盖部分点 → 天然支持后补导入一段其他地区的数据 |
| fill-geocoding | 请求带 region → 被填充的点 `region` 写为该值，完成时 `track.region` 同步为该值 |

### 显示回退链

任一展示位取名称时按 `zh → id → en → 原文` 取第一个非空值（含「（无名）」等现状哨兵值处理不变）。

## 2. 数据模型与迁移

### 后端模型

- `TrackPoint` 新增 4 列（与 `*_en` 同构）：`province_id`、`city_id`、`district_id`、`road_name_id`
- `road_number` 为编号本身（`35-024`、`3`），不分语言，不变
- `Track` 与 `TrackPoint` 各新增 `region` 列；`RoadSignCache` 新增 `region` 列
- 全部为普通列（无空间几何）→ 迁移产物：**alembic 一份 + SQL 脚本 ×3（SQLite / MySQL / PostgreSQL）**，无需 PostGIS 版

### 前端接口字段

- 轨迹详情/轨迹点/区域树相关 API 返回新增字段（`province_id` 等 + `region`）
- 区域树聚合节点（`RegionNode`）扩展：`region`、`names: {zh, id, en}`（该组聚合值的各语言代表文本，非空才出现）

## 3. 导入 / 导出（CSV 与 XLSX 同结构）

### 导出列（新格式，语言后缀全显式）

```
index, time_date, time_time, time_microsecond, elapsed_time,
longitude_wgs84, latitude_wgs84, longitude_gcj02, latitude_gcj02, longitude_bd09, latitude_bd09,
elevation, distance, course, speed,
region,
province_zh, province_id, province_en,
city_zh, city_id, city_en,
area_zh, area_id, area_en,
road_num, road_name_zh, road_name_id, road_name_en, memo
```

- `region` 列每行写该点 `region`（导出再导入、人工改段完全闭环）
- 坐标、时间等既有列不重排、不变
- 某语言列无值则留空（不因 region 省略列——文件结构稳定、自描述）
- KML 导出维持现状（无多语言/region 概念）

### 导入列名兼容（别名表，识别三类格式）

| 语义 | 新格式 | 样例/gpxutil 格式 | 旧 vibe 导出格式 |
|---|---|---|---|
| 中文省/市/区 | `province_zh`… | `province`…（无后缀） | `province`…（无后缀） |
| 印尼语省/市/区 | `province_id`… | `province_id`… | — |
| 英语省/市/区 | `province_en`… | `province_en`… | `province_en`… |
| 中文路名 | `road_name_zh` | `road_name` | `road_name` |
| 印尼语路名 | `road_name_id` | `road_name_id` | — |
| 路号 | `road_num` | `road_num` | `road_num` |
| 地区 | `region`（可选） | — | — |

- 同一列头在不同文件里可能语义相同（无后缀 = 中文），解析按固定别名表，不存在歧义
- 导入无 `region` 列时，点级 region 用轨迹级默认

## 4. geocoding 填充扩展（Nominatim）

- `NominatimGeocoding` 语言请求集按 region：
  - `cn`（现状不变）：`zh-CN` + `en`
  - `id`：`zh-CN` + `id` + `en`，返回字段增加 `province_id/city_id/area_id/road_name_id`（level4/5/6 与 road name 的印尼语请求结果）
- 印尼区划层级映射沿用现状：Nominatim admin level4/5/6 → province/city/district（Kabupaten → city、Kecamatan → district，与样例 CSV 一致）
- **中文尽力而为**：省级名称若 `zh-CN` 结果为空或与印尼语相同，用内置 38 省译名表回查（表 = gpxutil `INDONESIA_PROVINCE_CODE_MAP` 移植：印尼语省名 ↔ 中文省名 ↔ 两位省代码，双键）；市/区/路名缺中文则留空
- 道路编号处理：印尼无需「省级高速加省份前缀」这类中国专属逻辑，raw `ref` 直接入 `road_number`；多编号逗号分隔逻辑保留
- 其他 provider（amap/baidu/gdf）只服务中国，不变
- fill-geocoding API 增加 `region` 参数（必填由前端从轨迹带入）

## 5. 道路图标生成（印尼六边形盾牌）

### 资源（拷贝自 gpxutil `asset/`，同作者项目）

- `asset/template/id_sheild.svg` → `backend/data/templates/`
- `ClearviewHwy1W.ttf`（色带小字）→ `backend/data/fonts/`
- `ClearviewHwy2W.ttf`（白色区大字）→ `backend/data/fonts/`

> 注意：Clearview 系商业字体。若 gpxutil 中字体文件的许可无法确认，需评估替换为开源公路字体（本机个人项目 + 同源项目内使用，风险自担，写入计划前向开发者确认即可）。

### 编号解析（移植 gpxutil `parse_indonesia_road_num` + 38 省代码表）

| 输入 `road_num` | 等级 | 盾牌大字 | 色带 |
|---|---|---|---|
| `35-024` | PROVINSI | `024` | `PROVINSI 35` |
| `023`（3 位，无省码） | PROVINSI | `023` | `PROVINSI` + 省码（从地区文本查表，可无） |
| `3`、`15`（1-2 位） | NASIONAL | `3` | `NASIONAL` + 省码 |
| 1-2 位且路名含 TOL 关键词 | TOL | `3` | `TOL` + 省码 |
| 空/无法识别 | 无盾牌（前端只显示文本） | — | — |

- NASIONAL 与 TOL 编号体系相同（无法从数字区分），靠路名关键词：判定文本取 `road_name` 与 `road_name_id` 任一命中；**TOL 匹配用词边界 `\btol\b`（大小写不敏感）+「收费」子串**，不误伤 `Toleransi` 等含 tol 的词
- 省码来源优先级：编号内嵌（`35-024` 前段，需命中 38 省代码表）→ 地区文本（印尼语名或中文名）查表 → 无

### 生成器（移植 gpxutil `svg_gen.py` 的印尼盾牌函数）

- 读取 `id_sheild.svg`：白底六边形 + 顶部色带 + 占位文字
- 色带颜色：NASIONAL/TOL = 红（复用现有红色系，国标红 `#ED1724` 或 gpxutil 印尼配置 `#B5273C`，实现时对齐 gpxutil），PROVINSI = 蓝（新增配置默认 `#003E86`）
- 排版：文字锚点从模板元素 bbox 推导（不硬编码坐标，换模板自适应）；Clearview 1-W（默认高 45px）色带字、2-W（默认高 135px）大字，坐标系统一为模板 viewBox 坐标系；复用现有「字体转路径」底层（TTFont + SVGPathPen，`svg_gen.py` 已有）
- 该字体为拉丁字母，与现有中文字体（jtbz 系）互不干扰

### API 与缓存

- `POST /road-signs/generate` 请求增加可选 `region`（默认 `'cn'`）：
  - `cn`：现有正则校验与输出**完全不变**
  - `id`：忽略 `sign_type`，后端按「编号 + 路名 + 地区文本」解析等级后生成
- 响应回显 `region`
- `road_sign_cache` 表加 `region` 列；缓存键 = md5(含 region)；旧行自然失效（孤儿行无碍）

## 6. 区域树聚合与前端

### 区域树（后端 `track_service.get_region_tree`，`RegionNode`）

- 分组键加入 region：同文本不同 region 的节点分开（深港轨迹 → 「广东省·深圳」[cn] 与「香港特别行政区」[cn/hk] 各自成组）
- 节点携带：显示文本（回退链后）、`names`（各语言代表值）、`region`、`road_number`、`promoted_*`（现状保留）
- 节点文本本身按回退链输出（如印尼轨迹中文缺失时直接显示印尼语/英语）

### 前端

- `roadSignParser.ts`：`parseRoadNumber(code, region?)` 按 region 分派——`cn` 走现有国标解析；`id` 不透传猜测，返回原编号交后端解析；渲染道路节点图标时用**节点 region**（而非轨迹 region，跨地区同屏正确）
- TrackDetail 区域树（`renderNodeLabel`）：印尼节点渲染六边形 SVG（沿用现有内联机制与 `show_road_sign_in_region_tree` 开关）；生成请求带 region；失败回退纯文本（现状兜底）
- 名称 tooltip：非道路/道路节点 hover 展示该组全部语言（如「东爪哇省 / Provinsi Jawa Timur / Province of East Java」）；单语言则无 tooltip
- 上传/创建/修改轨迹、填充地理编码的对话框增加「地区」选择（中国/印尼，默认中国）
- UI 自身文案语言不变（无 i18n）

## 7. 配置

`config_service.DEFAULT_CONFIGS` 新增（全部带默认值，admin 可改，`cn` 键不动）：

```python
"indonesia_road_sign": {
    "template": "id_sheild.svg",          # backend/data/templates/
    "tol_keywords": ["收费", "Tol"],       # 词边界 + 子串匹配逻辑见 5 节
    "font_upper": "ClearviewHwy1W.ttf",   # 色带字，默认高 45
    "font_lower": "ClearviewHwy2W.ttf",   # 大字，默认高 135
},
```

## 8. 测试策略

1. 印尼编号解析单测：`3`→NASIONAL、1-2 位+`Tol`/`收费`→TOL、`Tol` 词边界（`Toleransi` 不误伤、大小写）、`023`→PROVINSI、`35-024`→PROVINSI+省码 35、`99-024` 非省码回退、空/乱串→None
2. 38 省代码表完整性（38 条、键无重复、中文 ↔ 印尼语互查）
3. 印尼盾牌 SVG：可解析、色带颜色（NASIONAL/TOL 红、PROVINSI 蓝）、色带文字含等级词与省码、大字为纯编号、字号字体正确、无省码降级
4. 解析器分派：cn 输出与现状一致；id 分支行为正确
5. 导入器三格式列名映射（含行级 `region` 落点级、缺列用默认）
6. 导出表头（新格式）与行值（含 region 列与语言列空值规则）
7. 区域树：跨地区分组、节点 region/names、回退链
8. 缓存键含 region 不串样（同 code 不同 region 两次生成）
9. 端到端冒烟：样例印尼 CSV 导入 → 区域树六边形盾牌 + tooltip 三语；混合 region 文件两段各自正确
10. 前端：parse 分派单测 + 类型检查/构建

## 9. 兼容性

- 全部默认 `cn`，不选地区 = 现状全链路不变（上传、填充、图标、区域树、导入旧文件）
- 导入兼容三类列名格式（见第 3 节）
- 图标 API 向后兼容（`region` 可选）
- 旧轨迹 region 缺省 `'cn'`：纯中国轨迹无感知；跨地区旧轨迹重新填充（选对 region）或行级导入修正后生效

## 10. 实施顺序建议

1. 后端 models + alembic + SQL 脚本（列与 region 落库）
2. 资源拷贝（模板 + 字体）与许可确认
3. `svg_gen.py`：移植编号解析、38 省表、印尼盾牌生成函数（含居中排版）
4. `road_sign_service` + `/road-signs/generate`：region 参数、缓存键
5. Nominatim 多语言请求 + 填充服务写 `*_id`
6. 导入导出：新列名 + 别名表 + 行级 region
7. 区域树聚合（region 分组、names）
8. 前端：对话框地区选择、parse 分派、tooltip、回退
9. 测试（后端 pytest + 前端构建）、端到端冒烟
10. 记录要点（cc 文档）

## 范围外（后续如有需要单独评估）

- 视频覆盖层模板/海报/动画导出中的多语言文本与印尼图标
- 前端 UI 文案 i18n
- `admin_divisions` 扩展印尼行政区划（区域树中文层级联动）
- 自动国境判定、gpxutil 侧兼容/词边界同步修正
