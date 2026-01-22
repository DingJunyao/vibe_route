# Vibe Route - 轨迹管理系统

基于 [gpxutil](https://github.com/DingJunyao/gpxutil) 构建的全栈 Web 轨迹管理系统。

每一次旅程都是生命中独一无二的叙事。从山峦叠嶂到城市街巷，从晨光熹微到暮色四合，足迹在时空之中交织出属于自己的轨迹。这些轨迹不仅记录了走过的距离，更承载着沿途的风景、心境与回忆。

Vibe Route 旨在将这些数字化的足迹转化为可被感知、被分享、被珍藏的记忆。系统将地理坐标、海拔变化、速度节奏等多维数据融合，让平面的线条在地图上重新呼吸。

无论是独自探索的远足，每一次呼吸都与山林同频；或是与朋友共享的骑行，车轮转动间传递着欢笑与默契；亦或是自驾追寻远方，引擎的轰鸣伴随夕阳的余晖——每一条轨迹都成为个人行走的诗篇。

技术架构的精心设计支撑着这一愿景。双层加密确保数据安全，多坐标系的自由适应让地理表达更加精准，而 Web 端的可视化与生成功能则赋予了创作者丰富的表达空间。从原始的 GPX 文件到精美的覆盖层，从单一的数据点到完整的叙事弧线，系统始终致力于为创作者提供最流畅的体验。

这不仅仅是一个轨迹管理系统，更是一个个人历史档案馆，一个行走记忆的数字化画布。

## 项目进度

### 已完成 ✅

- [x] 项目基础架构搭建
- [x] 数据库模型设计（支持 SQLite/MySQL/PostgreSQL）
- [x] JWT 认证系统
- [x] 用户注册和登录 API
- [x] 管理员用户管理 API
- [x] 系统配置 API
- [x] 邀请码系统
- [x] 前端 Vue 3 + TypeScript 项目搭建
- [x] 登录/注册页面
- [x] 首页布局
- [x] 坐标系转换
- [x] 地理编码填充
- [x] 轨迹列表和详情
- [x] 地图可视化（Leaflet/高德/百度）
- [x] 轨迹统计图表
- [x] 后台管理界面

### 待实现 🚧

- [ ] gpxutil 核心功能集成
- [ ] 轨迹上传和解析
- [ ] 信息覆盖层生成
- [ ] 道路标志生成

## 技术栈

### 后端
- FastAPI + Python 3.11+
- SQLAlchemy + Alembic
- JWT 认证
- SQLite / MySQL / PostgreSQL

### 前端
- Vue 3 + TypeScript + Vite
- Element Plus
- Pinia
- Vue Router
- Leaflet
- ECharts

## 快速开始

### 后端启动

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 复制配置文件
cp .env.example .env

# 创建数据目录
mkdir -p data/uploads data/temp data/exports data/road_signs

# 运行开发服务器
uvicorn app.main:app --reload
```

后端将运行在 `http://localhost:8000`

API 文档：`http://localhost:8000/docs`

### 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 运行开发服务器
npm run dev
```

前端将运行在 `http://localhost:5173`

## 数据库配置

项目默认使用 SQLite，无需额外配置。

### 切换到 MySQL

在 `backend/.env` 中配置：

```env
DATABASE_TYPE=mysql
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=vibe_route
MYSQL_PASSWORD=your-password
MYSQL_DB=vibe_route
```

### 切换到 PostgreSQL

在 `backend/.env` 中配置：

```env
DATABASE_TYPE=postgresql
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=vibe_route
POSTGRES_PASSWORD=your-password
POSTGRES_DB=vibe_route
```

## 项目结构

```
vibe_route/
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── api/            # API 路由
│   │   ├── core/           # 核心配置
│   │   ├── models/         # 数据库模型
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # 业务逻辑
│   │   ├── utils/          # 工具函数
│   │   └── gpxutil_wrapper/  # gpxutil 集成
│   └── requirements.txt
├── frontend/               # Vue 3 前端
│   ├── src/
│   │   ├── api/           # API 客户端
│   │   ├── components/    # 组件
│   │   ├── views/         # 页面
│   │   ├── stores/        # Pinia stores
│   │   ├── router/        # 路由
│   │   └── utils/         # 工具函数
│   └── package.json
└── docker-compose.yml
```

## 许可证

MIT
