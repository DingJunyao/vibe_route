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
