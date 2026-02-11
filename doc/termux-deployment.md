# Termux + proot-distro 部署指南

本指南专门针对在 Android 设备上使用 Termux + proot-distro 部署 Ubuntu 环境的场景。

## 目录

- [环境特点](#环境特点)
- [系统要求](#系统要求)
- [安装步骤](#安装步骤)
- [常见问题](#常见问题)
- [性能优化](#性能优化)

---

## 环境特点

### Termux + proot-distro 的特殊性

1. **用户空间 Linux**：通过 proot 实现的 Linux 用户空间环境
2. **ARM 架构**：通常是 aarch64 架构
3. **资源受限**：相比原生 Linux，性能和内存受限
4. **包管理差异**：使用 proot-distro 的 apt，而非原生 apt

### 与原生 Linux 的差异

| 方面 | Termux + proot-distro | 原生 Linux |
|------|----------------------|-----------|
| 内核访问 | 受限（proot 转换） | 直接访问 |
| 文件系统 | 绑定挂载 | 原生文件系统 |
| 网络 | 可能需要额外配置 | 原生支持 |
| 包管理 | proot-distro apt | 系统 apt/dnf |

---

## 系统要求

### Android 设备

- **Android 版本**：7.0+（推荐 10.0+）
- **存储**：至少 5GB 可用空间
- **内存**：推荐 4GB+ RAM
- **架构**：ARM64（aarch64）

### Termux 要求

```bash
# 更新 Termux 包管理器
pkg update && pkg upgrade

# 安装 proot-distro
pkg install proot-distro

# 安装 Ubuntu
proot-distro install ubuntu
```

---

## 安装步骤

### 1. 进入 proot-distro 环境

```bash
# 启动 Ubuntu 环境
~/ubuntu/var/usr/bin/proot-distro-login

# 或使用 alias
startubuntu
```

### 2. 安装 Rust 工具链

**重要**：bcrypt、asyncmy 等包需要 Rust 编译。

```bash
# 安装 Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env

# 验证安装
cargo --version
rustc --version
```

### 3. 安装系统编译依赖

```bash
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    libffi-dev \
    python3-dev \
    libpq-dev \
    python3.13-venv
```

### 4. 克隆项目

```bash
# 假设项目在 ~/code 目录
cd ~/code/vibe_route
cd backend
```

### 5. 创建 Python 虚拟环境

```bash
# 创建 venv
python3 -m venv venv

# 激活 venv
source venv/bin/activate
```

### 6. 安装 Python 依赖

**重要提示**：

1. **从 PyPI 安装**：避免 piwheels 元数据损坏问题
2. **固定 bcrypt 版本**：bcrypt 4.x/5.x 与 passlib 不兼容
3. **svgpathtools 来源**：需要从 GitHub 安装

```bash
# 从 PyPI 安装所有依赖（避免 piwheels 问题）
pip install fastapi uvicorn[standard] sqlalchemy alembic \
    aiosqlite aiomysql asyncpg pymysql psycopg2-binary \
    bcrypt>=3.2.0,<4.0.0 \
    python-jose[cryptography] passlib[bcrypt] \
    python-dotenv celery redis pydantic pydantic-settings \
    email-validator httpx aiofiles requests \
    gpxpy lxml pandas geopandas shapely \
    svgwrite cairosvg fonttools pillow imageio \
    numpy tqdm pyyaml pypinyin loguru \
    openpyxl pytest pytest-asyncio rarfile \
    slowapi python-multipart \
    --index-url https://pypi.org/simple

# svgpathtools 从 GitHub 安装（PyPI 版本不兼容）
pip install "svgpathtools @ https://github.com/bcwhite-code/svgpathtools/archive/refs/heads/master.zip"

# 安装 Playwright
pip install playwright==1.58.0

# 安装 Playwright 浏览器
playwright install chromium
```

### 7. 安装 Playwright 系统依赖

```bash
sudo apt-get install -y \
    libnspr4 \
    libnss3 \
    libatk1.0-0t64 \
    libatk-bridge2.0-0t64 \
    libcups2t64 \
    libxcb1 \
    libxkbcommon0 \
    libatspi2.0-0t64 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libcairo2 \
    libpango-1.0-0 \
    libasound2t64
```

### 8. 配置环境

```bash
# 复制配置文件
cp .env.example .env

# 编辑配置（可选）
vim .env
```

### 9. 创建数据目录

```bash
mkdir -p data/uploads data/temp data/exports data/road_signs
```

### 10. 初始化数据库

```bash
# 方法 1：使用 SQLAlchemy 初始化（推荐）
python -c "
import asyncio
from app.core.database import engine
from app.models import Base

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

asyncio.run(init_db())
print('数据库初始化成功!')
"

# 方法 2：设置 alembic 版本标记
python -c "
import sqlite3
conn = sqlite3.connect('data/vibe_route.db')
cursor = conn.cursor()

# 创建 alembic_version 表
cursor.execute('CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)')

# 设置版本
cursor.execute('INSERT INTO alembic_version (version_num) VALUES (\"014_add_interpolations\")')

conn.commit()
print('Alembic 版本已设置: 014_add_interpolations')
"
```

### 11. 启动开发服务器

```bash
# 基础启动
uvicorn app.main:app --reload

# 指定主机和端口
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

服务将运行在 `http://localhost:8000`

---

## 常见问题

### 问题 1：bcrypt 版本兼容性

**错误信息**：
```
AttributeError: module 'bcrypt' has no attribute '__about__'
```

**原因**：bcrypt 4.0.1+ 移除了 `__about__` 属性，导致 passlib 1.7.4 无法读取版本。

**解决方案**：
```bash
# 卸载不兼容版本
pip uninstall -y bcrypt

# 安装兼容版本
pip install 'bcrypt>=3.2.0,<4.0.0'
```

### 问题 2：pip 依赖解析卡住

**症状**：`pip install -r requirements.txt` 卡住不动。

**原因**：piwheels 上某些包（如 uvicorn 旧版本）存在元数据损坏。

**解决方案**：直接从 PyPI 安装，不使用 requirements.txt：
```bash
pip install <package-name> --index-url https://pypi.org/simple
```

### 问题 3：svgpathtools 导入错误

**错误信息**：
```
ModuleNotFoundError: No module named 'svgpathtools'
```

**原因**：PyPI 上的 svgpathtools 版本与项目不兼容。

**解决方案**：从 GitHub 安装：
```bash
pip install "svgpathtools @ https://github.com/bcwhite-code/svgpathtools/archive/refs/heads/master.zip"
```

### 问题 4：Playwright 浏览器下载失败

**错误信息**：
```
Client network socket disconnected before secure TLS connection was established
```

**原因**：网络问题或 CDN 访问受限。

**解决方案**：
```bash
# 重试安装
playwright install chromium

# 或手动下载（从镜像）
export PLAYWRIGHT_DOWNLOAD_HOST=https://playwright.akamai.net
playwright install chromium
```

### 问题 5：端口被占用

**错误信息**：
```
[Errno 98] error while attempting to bind on address ('0.0.0.0', 8000): address already in use
```

**解决方案**：
```bash
# 查看端口占用
sudo lsof -i :8000

# 或使用其他端口
uvicorn app.main:app --reload --port 8001
```

### 问题 6：密码哈希失败

**错误信息**：
```
ValueError: password cannot be longer than 72 bytes
```

**原因**：bcrypt 版本不兼容，参考问题 1。

---

## 性能优化

### 1. 减少日志输出

编辑 `.env`：
```env
LOG_LEVEL=WARNING
```

### 2. 调整 worker 数量

```bash
# 单 worker（适合资源受限环境）
uvicorn app.main:app --workers 1
```

### 3. 使用 SQLite

Termux 环境推荐使用 SQLite，无需额外服务：
```env
DATABASE_TYPE=sqlite
SQLITE_DB_PATH=data/vibe_route.db
```

### 4. 禁用不必要的功能

如果不需要海报生成等功能，可以不安装 Playwright 相关依赖：
```bash
# 从安装命令中移除：
# - playwright
# - cairosvg
# - pillow
```

---

## 进阶配置

### 使用 Supervisor 守护进程

```bash
# 安装 Supervisor
pip install supervisor

# 创建配置文件 ~/supervisor.conf
[program:vibe-route]
command=/home/user/code/vibe_route/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
directory=/home/user/code/vibe_route/backend
user=
autostart=true
autorestart=true
stderr_logfile=/home/user/code/vibe_route/backend/logs/supervisor.err.log
stdout_logfile=/home/user/code/vibe_route/backend/logs/supervisor.out.log

# 启动
supervisord -c ~/supervisor.conf
supervisorctl -c ~/supervisor.conf start vibe-route
```

### 访问服务

在同一 Android 设备上通过浏览器访问：

- **后端 API**：`http://localhost:8000`
- **API 文档**：`http://localhost:8000/docs`

从局域网其他设备访问：

1. 查看设备 IP：`ip addr show`
2. 访问：`http://<设备-ip>:8000`

---

## 参考

- [deployment.md](./deployment.md) - 通用部署指南
- [configuration.md](./configuration.md) - 配置选项说明
- [README.md](../README.md) - 项目总览
