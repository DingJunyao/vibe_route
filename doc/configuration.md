# 配置指南

本文档详细介绍 Vibe Route 轨迹管理系统的各项配置选项。

## 目录

- [后端配置](#后端配置)
- [前端配置](#前端配置)
- [数据库配置](#数据库配置)
- [地图配置](#地图配置)
- [系统配置](#系统配置)

---

## 后端配置

### 环境变量

后端配置文件位于 `backend/.env`，复制 `backend/.env.example` 创建配置文件：

```bash
cd backend
cp .env.example .env
```

### 基础配置

```env
# 应用配置
APP_NAME=Vibe Route
APP_VERSION=1.0.0
DEBUG=false
SECRET_KEY=your-secret-key-here-change-in-production

# 服务器配置
HOST=0.0.0.0
PORT=8000
```

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `APP_NAME` | 应用名称 | Vibe Route |
| `APP_VERSION` | 应用版本 | 1.0.0 |
| `DEBUG` | 调试模式 | false |
| `SECRET_KEY` | JWT 加密密钥 | 随机生成 |
| `HOST` | 服务器监听地址 | 0.0.0.0 |
| `PORT` | 服务器端口 | 8000 |

> **安全提示**：生产环境中务必修改 `SECRET_KEY` 为随机字符串，并设置 `DEBUG=false`。

### 数据库配置

#### SQLite（默认）

```env
DATABASE_TYPE=sqlite
SQLITE_DB_PATH=data/vibe_route.db
```

#### MySQL

```env
DATABASE_TYPE=mysql
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=vibe_route
MYSQL_PASSWORD=your-password
MYSQL_DB=vibe_route
MYSQL_CHARSET=utf8mb4
```

#### PostgreSQL

```env
DATABASE_TYPE=postgresql
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=vibe_route
POSTGRES_PASSWORD=your-password
POSTGRES_DB=vibe_route
```

### CORS 配置

```env
# CORS 允许的来源（逗号分隔）
CORS_ORIGINS=http://localhost:5173,http://192.168.1.100:5173
```

### 文件上传配置

```env
# 上传文件大小限制（字节）
MAX_UPLOAD_SIZE=104857600

# 允许的文件扩展名
ALLOWED_EXTENSIONS=.gpx,.csv,.xlsx,.kml,.kmz

# 上传目录
UPLOAD_DIR=data/uploads

# 临时目录
TEMP_DIR=data/temp

# 导出目录
EXPORT_DIR=data/exports

# 道路标志缓存目录
ROAD_SIGNS_DIR=data/road_signs
```

### JWT 配置

```env
# JWT 访问令牌有效期（秒）
ACCESS_TOKEN_EXPIRE_MINUTES=60

# JWT 刷新令牌有效期（秒）
REFRESH_TOKEN_EXPIRE_DAYS=7
```

### 首位用户配置

```env
# 首位注册用户自动成为管理员
FIRST_USER_IS_ADMIN=true
```

### 速率限制配置

```env
# API 速率限制（请求/分钟）
RATE_LIMIT=60
```

### 空间服务配置

```env
# 空间服务后端（auto/postgis）
SPATIAL_BACKEND=auto
```

---

## 前端配置

### 环境变量

前端配置文件位于 `frontend/.env.local`，复制 `frontend/.env.example` 创建配置文件：

```bash
cd frontend
cp .env.example .env.local
```

### API 配置

```env
# 后端 API 地址
VITE_API_URL=http://localhost:8000

# WebSocket 地址（通常自动从 API URL 推导）
# VITE_WS_URL=ws://localhost:8000
```

### 内网穿透配置

当使用内网穿透（如 frp、ngrok）访问前端服务时：

```env
# 完整的访问地址（协议 + 域名）
VITE_ORIGIN=https://your-domain.com

# 禁用 HMR（内网穿透环境下 WebSocket 连接不稳定）
VITE_DISABLE_HMR=true

# 允许的主机列表（逗号分隔）
VITE_ALLOWED_HOSTS=your-domain.com,.your-domain.com
```

### 远程日志配置

```env
# 是否启用远程日志（开发环境默认启用）
VITE_REMOTE_LOG=true
```

---

## 数据库配置

### SQLite 配置

SQLite 是默认配置，无需额外设置。数据库文件位于 `backend/data/vibe_route.db`。

### MySQL 配置

#### 创建数据库

```sql
CREATE DATABASE vibe_route CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'vibe_route'@'localhost' IDENTIFIED BY 'your-password';
GRANT ALL PRIVILEGES ON vibe_route.* TO 'vibe_route'@'localhost';
FLUSH PRIVILEGES;
```

#### 字符集配置

确保 MySQL 使用 UTF-8 字符集：

```ini
[client]
default-character-set = utf8mb4

[mysqld]
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci
```

### PostgreSQL 配置

#### 创建数据库

```sql
CREATE DATABASE vibe_route;
CREATE USER vibe_route WITH PASSWORD 'your-password';
GRANT ALL PRIVILEGES ON DATABASE vibe_route TO vibe_route;
```

#### 启用 PostGIS（可选）

PostGIS 提供空间数据支持：

```sql
\c vibe_route
CREATE EXTENSION IF NOT EXISTS postgis;
```

---

## 地图配置

### 地图提供商

系统支持以下地图提供商：

| 提供商 | 引擎 | 坐标系 | 需要 API Key |
|--------|------|--------|--------------|
| 高德地图 | AMap GL | GCJ02 | 可选 |
| 百度地图 | BMapGL | BD09 | 需要 |
| 腾讯地图 | TMap GL | GCJ02 | 需要 |
| OpenStreetMap | Leaflet | WGS84 | 不需要 |

### API Key 配置

地图 API Key 在系统后台管理页面配置：

1. 登录管理员账户
2. 进入"后台管理"
3. 切换到"系统配置"标签
4. 找到"地图配置"
5. 配置各地图的 API Key

#### 高德地图 API Key

1. 访问 [高德开放平台](https://lbs.amap.com/)
2. 注册/登录账户
3. 创建应用，选择"Web端(JS API)"
4. 获取 Key 和 安全密钥

#### 百度地图 API Key

1. 访问 [百度地图开放平台](https://lbsyun.baidu.com/)
2. 注册/登录账户
3. 创建应用，选择"浏览器端"
4. 获取 AK（访问应用密钥）

#### 腾讯地图 API Key

1. 访问 [腾讯位置服务](https://lbs.qq.com/)
2. 注册/登录账户
3. 创建应用，选择"Web端API"
4. 获取 Key

### 地图层配置

在系统配置中可以配置各地图的默认图层：

#### 高德地图图层

- 标准图层
- 卫星图层
- 路网图层

#### 百度地图图层

- 标准地图
- 卫星图
- 地形图

#### 腾讯地图图层

- 标准地图
- 卫星图

#### Leaflet 图层

- OpenStreetMap 标准层
- OpenStreetMap 卫星层
- 天地图（需要申请 Key）

### 坐标系说明

| 坐标系 | 说明 | 使用场景 |
|--------|------|----------|
| WGS84 | 国际标准坐标系 | GPS 原始数据、国际地图 |
| GCJ02 | 中国火星坐标系 | 高德地图、腾讯地图、天地图 |
| BD09 | 百度坐标系 | 百度地图 |

### 坐标系转换

系统自动在三种坐标系之间转换：

- 上传时：根据原始坐标系存储
- 显示时：根据选择的地图自动使用对应坐标系
- 导出时：可选择导出坐标系

---

## 系统配置

### 通过后台管理配置

登录管理员账户后，可在后台管理页面配置以下选项：

### 注册设置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| 允许注册 | 是否开放用户注册 | true |
| 需要邀请码 | 注册时是否需要邀请码 | false |

### 邀请码配置

邀请码可以限制注册用户数量：

1. 创建邀请码时设置：
   - 使用次数
   - 有效期
2. 用户注册时输入邀请码
3. 邀请码用完后自动失效

### 道路标志字体配置

系统支持自定义道路标志字体：

1. 进入后台管理 → 字体管理
2. 上传 TTF/OTF/TTC 字体文件
3. 设置 A/B/C 三种类型的激活字体

| 字体类型 | 说明 |
|----------|------|
| A 类 | 国道、国家高速 |
| B 类 | 省道、省级高速 |
| C 类 | 县道、乡道 |

---

## 日志配置

### 后端日志

后端日志级别根据 `DEBUG` 配置自动调整：

- `DEBUG=true`：DEBUG 级别
- `DEBUG=false`：WARNING 级别

日志格式：

```
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

### 日志位置

- 开发环境：控制台输出
- 生产环境：可配置文件输出

### 远程日志

前端支持远程日志推送：

1. 移动端：URL 添加 `?remote-log` 参数
2. 电脑端：访问 `/log-viewer` 查看实时日志

---

## 安全配置

### 密码策略

系统使用双重加密：

1. **前端加密**：SHA256
2. **后端存储**：bcrypt

密码要求：

- 最少 8 个字符
- 无其他强制要求

建议在生产环境中配置更严格的密码策略。

### HTTPS 配置

生产环境强烈建议使用 HTTPS：

#### 使用 Let's Encrypt

```bash
# 安装 Certbot
sudo apt install certbot python3-certbot-nginx

# 获取证书
sudo certbot --nginx -d your-domain.com

# 自动续期
sudo certbot renew --dry-run
```

### 速率限制

默认配置：每分钟 60 个请求。

可在 `backend/.env` 中调整：

```env
RATE_LIMIT=120
```

---

## 备份配置

### 自动备份

建议配置定期备份任务：

#### Cron 配置

```bash
# 编辑 crontab
crontab -e

# 添加每日备份任务
0 2 * * * /path/to/backup/script.sh
```

#### 备份脚本示例

```bash
#!/bin/bash
# backup.sh

DATE=$(date +%Y%m%d)
BACKUP_DIR="/path/to/backup"

# 备份数据库
if [ "$DATABASE_TYPE" = "mysql" ]; then
    mysqldump -u vibe_route -p vibe_route > "$BACKUP_DIR/vibe_route_$DATE.sql"
elif [ "$DATABASE_TYPE" = "postgresql" ]; then
    pg_dump -U vibe_route vibe_route > "$BACKUP_DIR/vibe_route_$DATE.sql"
else
    cp backend/data/vibe_route.db "$BACKUP_DIR/vibe_route_$DATE.db"
fi

# 备份上传文件
rsync -av backend/data/uploads/ "$BACKUP_DIR/uploads_$DATE/"

# 清理旧备份（保留 30 天）
find "$BACKUP_DIR" -name "vibe_route_*" -mtime +30 -delete
```

---

## 性能优化

### 数据库优化

#### 索引优化

系统已创建必要的索引，无需额外配置。

#### 连接池配置

生产环境建议调整数据库连接池大小。

### 缓存配置

系统使用内存缓存：

- 配置缓存：5 分钟过期
- 道路标志缓存：永不过期

### 文件上传优化

大文件使用异步任务处理：

- 在任务列表查看进度
- 可取消正在进行的任务

---

## 监控配置

### 健康检查

系统提供健康检查端点：

```
GET /health
```

响应：

```json
{
  "status": "ok",
  "database": "healthy",
  "version": "1.0.0"
}
```

### 日志监控

推荐使用以下工具监控日志：

- **Linux**：`journalctl -u vibe-route-backend -f`
- **Docker**：`docker-compose logs -f`
- **远程日志**：访问 `/log-viewer`

---

## 故障排查

### 配置问题

#### 问题：数据库连接失败

解决：

1. 检查数据库服务是否运行
2. 检查 `backend/.env` 中的数据库配置
3. 检查防火墙设置

#### 问题：地图不显示

解决：

1. 检查网络连接
2. 检查 API Key 是否正确配置
3. 尝试切换底图

#### 问题：文件上传失败

解决：

1. 检查文件大小是否超过限制
2. 检查文件格式是否支持
3. 检查上传目录权限

---

## 附录

### 完整配置示例

#### backend/.env

```env
# 应用配置
APP_NAME=Vibe Route
APP_VERSION=1.0.0
DEBUG=false
SECRET_KEY=your-random-secret-key-min-32-characters

# 服务器配置
HOST=0.0.0.0
PORT=8000

# 数据库配置
DATABASE_TYPE=postgresql
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=vibe_route
POSTGRES_PASSWORD=your-password
POSTGRES_DB=vibe_route

# CORS 配置
CORS_ORIGINS=https://your-domain.com

# 文件上传配置
MAX_UPLOAD_SIZE=104857600
UPLOAD_DIR=data/uploads
TEMP_DIR=data/temp
EXPORT_DIR=data/exports
ROAD_SIGNS_DIR=data/road_signs

# JWT 配置
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

# 首位用户配置
FIRST_USER_IS_ADMIN=true

# 速率限制
RATE_LIMIT=60

# 空间服务
SPATIAL_BACKEND=auto
```

#### frontend/.env.local

```env
# 后端 API 地址
VITE_API_URL=https://your-domain.com

# 完整的访问地址
VITE_ORIGIN=https://your-domain.com

# 远程日志
VITE_REMOTE_LOG=true
```
