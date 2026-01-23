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

- 移动端断点：`screenWidth <= 768px`
- 桌面端隐藏类：`.desktop-only`
- 移动端使用卡片列表替代表格
- viewport 配置禁止页面缩放：`maximum-scale=1.0, user-scalable=no`

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

- 事件处理：高德地图 `mousemove`/`click` + DOM 捕获阶段备用

- 图表同步：ECharts `dispatchAction` 触发 `showTip`/`highlight`

- Polyline `bubble: true` 允许事件冒泡

#### 涉及文件

- [`AMap.vue`](frontend/src/components/map/AMap.vue) - 高德地图组件
- [`UniversalMap.vue`](frontend/src/components/map/UniversalMap.vue) - 地图引擎包装器
- [`TrackDetail.vue`](frontend/src/views/TrackDetail.vue) - 轨迹详情页

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
