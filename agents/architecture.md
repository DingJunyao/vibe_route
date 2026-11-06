# 架构核心

## 认证
- 前端 SHA256 加密 → 后端 bcrypt 二次哈希
- 公开配置 `/api/auth/config` vs 管理员 `/admin/config`

### 认证流程（双重加密）

密码在传输和存储过程中经过两次加密：

1. **前端加密** ([`crypto.ts`](frontend/src/utils/crypto.ts))：SHA256 加密
2. **后端存储** ([`security.py`](backend/app/core/security.py))：bcrypt 二次哈希

### 公开配置 vs 管理员配置

- **公开配置** (`GET /api/auth/config`)：任何用户可访问，只返回地图相关配置
- **管理员配置** (`GET /api/admin/config`)：需要管理员权限，返回完整配置

前端 [`config.ts`](frontend/src/stores/config.ts) store 会根据用户权限自动选择合适的 API。

## 多坐标系

- WGS84（GPS 原始）、GCJ02（高德/腾讯）、BD09（百度）
- 地图组件自动切换对应坐标

### 多坐标系支持

轨迹点存储三种坐标系：

- **WGS84**: 国际标准坐标系（GPS 原始坐标）
- **GCJ02**: 中国火星坐标系（高德、腾讯地图、天地图）
- **BD09**: 百度坐标系

地图组件根据选择的底图自动使用对应坐标。

### 境外点坐标口径（2026-11-06 起，勿回退）

**GCJ02/BD09 偏移加密只在中国境内有效；百度海外底图按 WGS84 对齐。** 后端入库时对所有点无条件执行 wgs84→gcj02→bd09 转换，境外点的 gcj02 字段恰好等于 wgs84（`wgs84_to_gcj02` 自带 outOfChina 守卫），但 bd09 字段是套用中国偏移算法的产物（偏差 ~1km，属无效数据、不迁移）。因此**所有百度口径的取点必须先境内判定**：

- `utils/coordTransform.ts`：`gcj02ToBd09`/`bd09ToGcj02` 带 outOfChina 守卫（境外原样返回）；导出 `isInChina(lng, lat)` 粗判矩形与 `isChinaRegionPoints(points, sample=20)` 采样多数判定（按轨迹整体选口径，避免跨界轨迹逐点跳变）
- `BMap.vue`：`pickBaiduLngLat()` 统一取点（境内 bd09 / 境外 wgs84），`getBD09Coords`、动画适配器、customOverlay、热力图全走此口径或 `wgs84ToBd09` 守卫
- `TrackAnimationPlayer.vue`：`isBD09Provider` = `mapProvider === 'baidu' && isChinaRegionPoints(points)`；`LeafletMap.vue` `getCoordsByCRS` bd09 分支同口径

### Google 底图坐标口径（2026-11-06 实测，勿回退）

**Google 的中国数据两张底图口径不一致**（Google 自身的历史问题）：路网（roadmap，`lyrs=m`）的图元按 **GCJ-02** 偏移，卫星图（`lyrs=s`）是 **WGS84** 真值。实测方法：同一段境内轨迹分别用 WGS84 与 GCJ-02 口径叠加——路网图上 GCJ-02 压路、WGS84 偏 500m；卫星图上恰好相反。**本项目只配置路网图层（`google`），全链路统一按 GCJ-02**（境外 gcj02 == wgs84，转换守卫兜底）：

- `GoogleMap.vue`（SDK）：`getMapCoords()` 统一取点（优先 gcj02 字段、缺失时 wgs84→gcj02 转换），轨迹/动画双色线/标记/bounds/highlight/最新点全走它；热力图（WGS84 输入）投影前 `wgs84ToGcj02`；customOverlay（绘制路径模式）同转换；**`map-click` 对外发射前 `gcj02ToWgs84`**（地图空间是 GCJ-02，外部约定 WGS84）
- `TrackAnimationPlayer.vue`：`isGCJ02Provider` 含 `google`（相机/标记/插值全用 gcj02，与 Leaflet 按图层 `crs: gcj02` 画的轨迹一致——修前播放器用 WGS84 而 Leaflet 轨迹用 GCJ，标记与轨迹错开 500m）
- **未配置 `google_satellite`**：若将来启用，该图层是 WGS84 卫星底图（配 crs: wgs84），不能复用上述 GCJ-02 口径；SDK 播放器按 `mapProvider`（只有 'google'）无法区分变体，届时需要把图层 CRS 透传到播放器

## 数据库驱动与平台兼容性

项目支持三种数据库：SQLite、MySQL、PostgreSQL。不同平台下驱动选择：

| 驱动 | 用途 | x86/x64 | ARM (树莓派) |
|------|------|---------|--------------|
| `aiosqlite` | SQLite 异步 | ✅ wheel | ✅ wheel |
| `asyncmy` | MySQL 异步（高性能） | ✅ wheel | ❌ 需 Rust 编译 |
| `aiomysql` | MySQL 异步（纯 Python） | ✅ | ✅ wheel |
| `asyncpg` | PostgreSQL 异步 | ✅ wheel | ❌ 需编译 |
| `pymysql` | Alembic 迁移（MySQL） | ✅ | ✅ wheel |
| `psycopg2-binary` | Alembic 迁移（PostgreSQL） | ✅ wheel | ❌ 需编译 |
| `bcrypt` | 密码哈希 | ✅ wheel | ❌ 需 Rust 编译 |

### ARM 平台安装注意事项

1. **必须安装 Rust 工具链**：编译 `bcrypt` 和 `asyncmy`
   ```bash
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
   source $HOME/.cargo/env
   ```

2. **从 PyPI 安装**：piwheels 可能没有某些包的 wheel
   ```bash
   pip install asyncmy bcrypt psycopg2-binary asyncpg --index-url https://pypi.org/simple
   ```

3. **系统依赖**：
   ```bash
   sudo apt-get install -y build-essential libffi-dev python3-dev libpq-dev
   ```

## 用户状态字段

- **`is_valid`**: 软删除标记，查询用户时会过滤 `is_valid = False` 的记录
- **`is_active`**: 账户启用状态，控制用户能否登录

用户创建时会复用已删除（`is_valid = False`）用户的记录。

## 数据库模型

核心模型：

- [`User`](backend/app/models/user.py): 用户表，首位注册用户自动成为管理员
- [`Track`](backend/app/models/track.py): 轨迹表
- [`TrackPoint`](backend/app/models/track.py): 轨迹点表
- [`Task`](backend/app/models/task.py): 异步任务
- [`Config`](backend/app/models/config.py): 系统配置
- [`LiveRecording`](backend/app/models/live_recording.py): 实时记录

所有模型继承 [`AuditMixin`](backend/app/models/base.py)，包含 `created_at`, `updated_at`, `created_by`, `updated_by`, `is_valid` 字段。

## 地区（Region）与多语言字段

### region 三层存储（点级为权威）

| 层 | 字段 | 语义 |
|------|------|------|
| 轨迹（行级） | `tracks.region` | 归属地区，默认 `'cn'`，编辑对话框可改 |
| 轨迹点（**点级权威**） | `track_points.region` | **决定图标渲染与文本显示**；改轨迹 region **不覆盖**已有点 |
| 道路标牌缓存 | `road_sign_cache.region` | 缓存隔离，同编号不同地区不串样 |

当前取值 `cn`（中国）/ `id`（印尼）。图标与文本一律读**点级** region，故一个文件里跨地区的轨迹能逐点正确渲染。

### 语言后缀平铺列

`province` / `city` / `district` / `road_name` 四组，每组三列：中文**无后缀**（历史列，旧数据零迁移）、印尼语 `_id`、英语 `_en`。

- 用平铺列而非 JSON：旧数据可直接读，导出 CSV 可直列
- 扩展新地区 = 再加一组后缀列（当前 cn 无后缀 + id/en 已占位）
- 注意 CSV 沿用历史列名：`district` 在 CSV 中为 `area`，`road_number` 为 `road_num`

### 迁移

- `016_add_multilanguage_region`：`tracks` / `track_points` 加 `region`（默认 `'cn'`）、`track_points` 加 4 个 `*_id` 印尼语列、`road_sign_cache` 加 `region`；附 sqlite / mysql / postgresql 三份 SQL（sqlite 版为本次新增）
- `017_widen_road_sign_province`：`road_sign_cache.province` `10 → 100`。016 在开发库先被 stamped、该 DDL 追加在 016 之后而从未落地，故单开一支补齐

## 路由守卫
- `guest`: 未登录可访问
- `requiresAuth`: 需登录
- `requiresAdmin`: 需管理员

## 响应式设计

- 移动端断点: `screenWidth <= 1366px`
- 高度单位: `vh` 实现，如 `height: calc(100vh - 60px)`
- 地图重绘: `ResizeObserver` 监听容器变化

### 布局规则
| 页面 | 桌面端 (height>=800px) | 桌面端 (height<800px) | 移动端 |
|------|------------------------|----------------------|--------|
| 首页 | 统计固定 + 地图填充 | 独立滚动 | 单列流式 |
| 详情页 | 左侧固定 + 右侧滚动 | 地图 40vh + 图表 22vh | 地图 30vh + 图表 20vh |
