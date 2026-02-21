# 快速命令

## ARM 架构（树莓派等）

> **注意**：piwheels 上某些包（如 uvicorn 旧版本）存在元数据损坏，会导致 pip 依赖解析卡住。建议直接从 PyPI 安装所有依赖。

```bash
# 1. 安装 Rust 工具链（编译 bcrypt、asyncmy 等）
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env

# 2. 安装系统编译依赖
sudo apt-get install -y build-essential libffi-dev python3-dev libpq-dev

# 3. 安装 Python 依赖
cd backend
python -m venv venv
source venv/bin/activate

# 4. 从 PyPI 安装所有依赖（避免 piwheels 元数据问题）
pip install fastapi uvicorn[standard] sqlalchemy alembic aiosqlite asyncmy aiomysql asyncpg pymysql psycopg2-binary bcrypt python-jose[cryptography] passlib[bcrypt] python-dotenv celery redis pydantic pydantic-settings email-validator httpx aiofiles requests gpxpy lxml pandas geopandas shapely svgwrite fonttools pillow cairosvg imageio numpy tqdm pyyaml pypinyin loguru openpyxl pytest pytest-asyncio rarfile playwright==1.58.0 --index-url https://pypi.org/simple

# 5. 安装 Playwright 浏览器
playwright install chromium

# 6. 配置环境
cp .env.example .env
mkdir -p data/uploads data/temp data/exports data/road_signs

# 7. 运行
uvicorn app.main:app --reload
alembic upgrade head
```

## x86/x64 架构

```bash
# 后端
cd backend && uvicorn app.main:app --reload

# 前端
cd frontend && npm run dev

# 数据库迁移
cd backend && alembic upgrade head
```
