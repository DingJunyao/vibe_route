# 部署指南

本文档介绍如何在不同环境下部署 Vibe Route 轨迹管理系统。

## 目录

- [系统要求](#系统要求)
- [开发环境部署](#开发环境部署)
- [生产环境部署](#生产环境部署)
- [Docker 部署](#docker-部署)
- [Nginx 反向代理配置](#nginx-反向代理配置)
- [常见问题](#常见问题)

---

## 系统要求

### 最低配置

| 组件 | 最低要求 | 推荐配置 |
|------|----------|----------|
| CPU | 2 核 | 4 核+ |
| 内存 | 2 GB | 4 GB+ |
| 存储 | 10 GB | 20 GB+ |
| Python | 3.11+ | 3.11+ |
| Node.js | 18+ | 20+ |

### 支持的操作系统

- Linux (Ubuntu 20.04+, Debian 11+, CentOS 8+)
  - ARM 架构（树莓派等）需要额外配置
- macOS 12+
- Windows 10/11 (开发环境)

### ARM 架构特殊说明

在 ARM 架构（如树莓派）上部署时，以下包需要从源码编译：

| 包 | 说明 | 处理方式 |
|----|------|----------|
| `bcrypt` | 密码哈希 | 需要 Rust 工具链 |
| `asyncmy` | MySQL 异步驱动 | 需要 Rust 工具链 |
| `asyncpg` | PostgreSQL 异步驱动 | 需要编译 |
| `psycopg2-binary` | PostgreSQL 同步驱动 | 需要编译 |
| `lxml` | XML 处理 | 需要编译 |

**ARM 平台安装步骤**：

> **重要提示**：piwheels 上某些包（如 uvicorn 旧版本）存在元数据损坏，会导致 pip 依赖解析卡住。**建议直接从 PyPI 安装所有依赖**。

```bash
# 1. 安装 Rust 工具链
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env

# 2. 安装系统编译依赖
sudo apt-get install -y build-essential libffi-dev python3-dev libpq-dev

# 3. 从 PyPI 安装所有依赖（避免 piwheels 元数据问题）
pip install fastapi uvicorn[standard] sqlalchemy alembic aiosqlite asyncmy aiomysql asyncpg pymysql psycopg2-binary bcrypt python-jose[cryptography] passlib[bcrypt] python-dotenv celery redis pydantic pydantic-settings email-validator httpx aiofiles requests gpxpy lxml pandas geopandas shapely svgwrite fonttools pillow cairosvg imageio numpy tqdm pyyaml pypinyin loguru openpyxl pytest pytest-asyncio rarfile playwright==1.58.0 --index-url https://pypi.org/simple
```

### 支持的数据库

- SQLite 3.35+ (默认，适合小型部署)
- MySQL 8.0+ / MariaDB 10.6+
- PostgreSQL 14+ (推荐用于生产环境)

---

## 开发环境部署

### ARM 架构（树莓派等）

如果使用 ARM 架构设备，请先完成前置步骤：

```bash
# 1. 安装 Rust 工具链
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env

# 2. 安装系统编译依赖
sudo apt-get install -y build-essential libffi-dev python3-dev libpq-dev

# 3. 安装 Playwright 浏览器（如需海报生成功能）
playwright install chromium
```

### 1. 克隆项目

```bash
git clone https://github.com/DingJunyao/vibe_route.git
cd vibe_route
```

### 2. 后端部署

```bash
cd backend

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Linux/macOS:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# 安装依赖

# ARM 架构：从 PyPI 安装（避免 piwheels 元数据问题）
pip install fastapi uvicorn[standard] sqlalchemy alembic aiosqlite asyncmy aiomysql asyncpg pymysql psycopg2-binary bcrypt python-jose[cryptography] passlib[bcrypt] python-dotenv celery redis pydantic pydantic-settings email-validator httpx aiofiles requests gpxpy lxml pandas geopandas shapely svgwrite fonttools pillow cairosvg imageio numpy tqdm pyyaml pypinyin loguru openpyxl pytest pytest-asyncio rarfile playwright==1.58.0 --index-url https://pypi.org/simple

# x86/x64 架构：可使用 requirements.txt
# pip install -r requirements.txt

# 复制配置文件
cp .env.example .env

# 编辑配置文件（可选）
# vim .env

# 创建必要目录
mkdir -p data/uploads data/temp data/exports data/road_signs

# 数据库迁移
alembic upgrade head

# 启动开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端服务将运行在 `http://localhost:8000`

API 文档访问：`http://localhost:8000/docs`

### 3. 前端部署

```bash
cd frontend

# 安装依赖
npm install

# 复制环境变量配置（可选）
cp .env.example .env.local

# 启动开发服务器
npm run dev
```

前端服务将运行在 `http://localhost:5173`

### 4. 访问应用

打开浏览器访问 `http://localhost:5173`

首次访问时，注册的第一个用户将自动成为管理员。

---

## 生产环境部署

### 使用 Systemd 部署后端

#### 1. 创建服务文件

创建 `/etc/systemd/system/vibe-route-backend.service`：

```ini
[Unit]
Description=Vibe Route Backend
After=network.target mysql.service postgresql.service

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/opt/vibe_route/backend
Environment="PATH=/opt/vibe_route/backend/venv/bin"
ExecStart=/opt/vibe_route/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 2. 启动服务

```bash
# 重载配置
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start vibe-route-backend

# 开机自启
sudo systemctl enable vibe-route-backend

# 查看状态
sudo systemctl status vibe-route-backend
```

### 使用 PM2 部署前端

#### 1. 安装 PM2

```bash
npm install -g pm2
```

#### 2. 构建前端

```bash
cd frontend
npm run build
```

#### 3. 配置 PM2

创建 `ecosystem.config.js`：

```javascript
module.exports = {
  apps: [{
    name: 'vibe-route-frontend',
    script: 'npm',
    args: 'run preview',
    cwd: '/opt/vibe_route/frontend',
    env: {
      NODE_ENV: 'production'
    }
  }]
}
```

#### 4. 启动服务

```bash
cd /opt/vibe_route/frontend
pm2 start ecosystem.config.js
pm2 save
pm2 startup
```

### 使用 Gunicorn 部署后端（替代方案）

```bash
# 安装 Gunicorn
pip install gunicorn

# 启动服务
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

---

## Docker 部署

### 使用 Docker Compose

项目提供了 `docker-compose.yml` 配置文件。

#### 1. 构建镜像

```bash
docker-compose build
```

#### 2. 启动服务

```bash
docker-compose up -d
```

#### 3. 查看日志

```bash
docker-compose logs -f
```

#### 4. 停止服务

```bash
docker-compose down
```

### 环境变量配置

创建 `.env` 文件：

```env
# 后端配置
DATABASE_TYPE=postgresql
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_USER=vibe_route
POSTGRES_PASSWORD=your-password
POSTGRES_DB=vibe_route

# 前端配置
VITE_API_URL=http://localhost:8000
```

### 数据持久化

Docker Compose 配置已包含数据卷挂载：

- `./data/uploads:/app/backend/data/uploads` - 上传文件
- `./data/exports:/app/backend/data/exports` - 导出文件
- `./data/road_signs:/app/backend/data/road_signs` - 道路标志缓存

---

## Nginx 反向代理配置

### 基础配置

创建 `/etc/nginx/sites-available/vibe-route`：

```nginx
# 上游服务器
upstream backend {
    server 127.0.0.1:8000;
}

upstream frontend {
    server 127.0.0.1:5173;
}

# HTTP 重定向到 HTTPS（可选）
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

# 主服务器配置
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL 证书配置
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # 安全头部
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # 客户端上传大小限制
    client_max_body_size 100M;

    # 前端静态文件
    location / {
        proxy_pass http://frontend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 后端 API
    location /api/ {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 超时配置
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }

    # WebSocket 端点
    location /api/ws/ {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 超时配置
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

### 启用配置

```bash
# 创建符号链接
sudo ln -s /etc/nginx/sites-available/vibe-route /etc/nginx/sites-enabled/

# 测试配置
sudo nginx -t

# 重载 Nginx
sudo systemctl reload nginx
```

---

## 数据库配置

### MySQL 配置

创建数据库和用户：

```sql
CREATE DATABASE vibe_route CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'vibe_route'@'localhost' IDENTIFIED BY 'your-password';
GRANT ALL PRIVILEGES ON vibe_route.* TO 'vibe_route'@'localhost';
FLUSH PRIVILEGES;
```

### PostgreSQL 配置

创建数据库和用户：

```sql
CREATE DATABASE vibe_route;
CREATE USER vibe_route WITH PASSWORD 'your-password';
GRANT ALL PRIVILEGES ON DATABASE vibe_route TO vibe_route;
```

启用 PostGIS 扩展（可选）：

```sql
\c vibe_route
CREATE EXTENSION IF NOT EXISTS postgis;
```

---

## 常见问题

### 端口被占用

```bash
# 查看端口占用
sudo lsof -i :8000
sudo lsof -i :5173

# 更改端口
# 后端: uvicorn app.main:app --port 8001
# 前端: 修改 vite.config.ts 中的 server.port
```

### 权限问题

```bash
# 设置目录权限
sudo chown -R www-data:www-data /opt/vibe_route/backend/data
sudo chmod -R 755 /opt/vibe_route/backend/data
```

### 数据库连接失败

检查防火墙设置：

```bash
# Ubuntu/Debian
sudo ufw allow 3306  # MySQL
sudo ufw allow 5432  # PostgreSQL

# CentOS/RHEL
sudo firewall-cmd --add-port=3306/tcp --permanent
sudo firewall-cmd --add-port=5432/tcp --permanent
sudo firewall-cmd --reload
```

### WebSocket 连接失败

确保 Nginx 配置正确处理 WebSocket 升级请求：

```nginx
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
```

### ARM 架构依赖安装失败

**问题 1**：`pip install -r requirements.txt` 卡住不动。

**原因**：piwheels 上某些包（如 uvicorn 旧版本）存在元数据损坏，导致 pip 依赖解析陷入死循环。

**解决方案**：直接从 PyPI 安装所有依赖

```bash
pip install fastapi uvicorn[standard] sqlalchemy alembic aiosqlite asyncmy aiomysql asyncpg pymysql psycopg2-binary bcrypt python-jose[cryptography] passlib[bcrypt] python-dotenv celery redis pydantic pydantic-settings email-validator httpx aiofiles requests gpxpy lxml pandas geopandas shapely svgwrite fonttools pillow cairosvg imageio numpy tqdm pyyaml pypinyin loguru openpyxl pytest pytest-asyncio rarfile playwright==1.58.0 --index-url https://pypi.org/simple
```

**问题 2**：树莓派上安装依赖时出现 `No matching distribution found` 错误。

**原因**：某些包（如 `asyncmy`、`bcrypt`）在 piwheels 上没有预编译的 wheel。

**解决方案**：

1. 安装 Rust 工具链：
   ```bash
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
   source $HOME/.cargo/env
   ```

2. 从 PyPI 安装：
   ```bash
   pip install asyncmy bcrypt psycopg2-binary asyncpg lxml --index-url https://pypi.org/simple
   ```

3. 如果仍然失败，使用纯 Python 替代方案：
   ```bash
   # 用 aiomysql 替代 asyncmy（已在 requirements.txt 中配置）
   pip install aiomysql
   ```

---

## 日志查看

### Systemd 服务日志

```bash
# 查看实时日志
sudo journalctl -u vibe-route-backend -f

# 查看最近 100 条日志
sudo journalctl -u vibe-route-backend -n 100
```

### PM2 日志

```bash
# 查看实时日志
pm2 logs vibe-route-frontend

# 查看所有日志
pm2 logs
```

### 应用日志

后端日志位置（取决于配置）：

- 开发环境：控制台输出
- 生产环境：`backend/logs/` 目录

---

## 备份与恢复

### 数据库备份

```bash
# SQLite
cp backend/data/vibe_route.db backup/vibe_route_$(date +%Y%m%d).db

# MySQL
mysqldump -u vibe_route -p vibe_route > backup/vibe_route_$(date +%Y%m%d).sql

# PostgreSQL
pg_dump -U vibe_route vibe_route > backup/vibe_route_$(date +%Y%m%d).sql
```

### 数据恢复

```bash
# SQLite
cp backup/vibe_route_20240101.db backend/data/vibe_route.db

# MySQL
mysql -u vibe_route -p vibe_route < backup/vibe_route_20240101.sql

# PostgreSQL
psql -U vibe_route vibe_route < backup/vibe_route_20240101.sql
```

### 文件备份

```bash
# 备份上传文件
rsync -av backend/data/uploads/ backup/uploads_$(date +%Y%m%d)/

# 备份导出文件
rsync -av backend/data/exports/ backup/exports_$(date +%Y%m%d)/
```
