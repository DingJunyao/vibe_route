# syntax=docker/dockerfile:1
#
# Vibe Route - 轨迹管理系统 · 统一 Dockerfile（multi-stage 多 target）
#
#   --target frontend   : 前端运行时镜像（分开部署用）
#   --target backend    : 后端运行时镜像（分开部署用）
#   --target all-in-one : 统一部署镜像（nginx + uvicorn 同容器，默认 target）
#
# stage 顺序说明：all-in-one（统一部署，最常用）排在 frontend stage 之前，
# 这样经典 builder 构 all-in-one 时走到它即止，不必拉 nginx:alpine
# （all-in-one 的 nginx 由 apt 安装，不依赖 nginx:alpine 基础镜像）。

# ===========================================================================
# Stage 1: 前端构建（产出 dist）
# ===========================================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /build

# 先拷依赖描述、锁版本安装（利用 docker 层缓存）
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# 拷源码并构建（.dockerignore 已排除 node_modules，不会覆盖上面装的）
COPY frontend/ ./
RUN npm run build \
    # public/ 下的源文件（location.svg 等）从 Windows 构建上下文
    # COPY 进 Linux 后权限可能不可读，nginx try_files 命中后由 static 模块读取会 403。
    # 统一放开读权限（a+r 给文件可读、a+X 只给目录加可遍历位），vite 生成的 assets 本就 644 不受影响。
    && chmod -R a+rX dist
# 产物：/build/dist


# ===========================================================================
# Stage 2: 后端镜像（backend target；同时作为 all-in-one 的基础层）
# ===========================================================================
FROM python:3.11-slim AS backend

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=UTC \
    # playwright 浏览器安装位置（放 /app 下，appuser 可读）
    PLAYWRIGHT_BROWSERS_PATH=/app/.cache/ms-playwright

WORKDIR /app

# 装依赖：requirements 已含各数据库驱动（aiosqlite/asyncmy/asyncpg 等），换库只改环境变量
# libcairo2：cairosvg 运行时依赖；playwright 浏览器用 --with-deps 自行安装系统依赖
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && apt-get update \
    && apt-get install -y --no-install-recommends libcairo2 \
    && python -m playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

# 拷应用代码
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./
COPY backend/scripts ./scripts

# 持久化目录（开箱即用前提；compose 挂载点会覆盖这些路径）
RUN mkdir -p /app/data /app/logs

# 非 root 用户
RUN useradd -r -u 1000 -d /app -s /sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# 健康检查：探 /health，用 python urllib 免装 curl
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3).read()" || exit 1

# 生产启动（不带 --reload，区别于开发的 python run.py）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


# ===========================================================================
# Stage 3: 统一部署 all-in-one（backend 层 + 前端 dist + nginx + supervisor）
#   排在 frontend stage 之前，经典 builder 构此 target 时无需拉 nginx:alpine
# ===========================================================================
FROM backend AS all-in-one

# 装 nginx + supervisor + envsubst(gettext-base)，需 root
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx supervisor gettext-base \
    && rm -rf /var/lib/apt/lists/*

# 拷前端构建产物
COPY --from=frontend-builder /build/dist /usr/share/nginx/html

# nginx 配置模板（与 frontend target 复用同一份）
COPY deploy/nginx/default.conf.template /etc/nginx/templates/default.conf.template
# 清 Debian nginx 默认站点
RUN rm -f /etc/nginx/sites-enabled/default /etc/nginx/conf.d/default.conf

# supervisord 配置 + 启动脚本
COPY deploy/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY deploy/all-in-one-entrypoint.sh /all-in-one-entrypoint.sh
RUN sed -i 's/\r$//' /all-in-one-entrypoint.sh && chmod +x /all-in-one-entrypoint.sh

# all-in-one：后端默认指同容器 uvicorn
ENV BACKEND_URL=http://127.0.0.1:8000

EXPOSE 80

ENTRYPOINT ["/all-in-one-entrypoint.sh"]
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]


# ===========================================================================
# Stage 4: 前端运行时镜像（分开部署用；--target frontend 单独构时才需要）
# ===========================================================================
FROM nginx:alpine AS frontend

# 拷前端构建产物
COPY --from=frontend-builder /build/dist /usr/share/nginx/html

# nginx 配置模板 + 启动脚本
COPY deploy/nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY deploy/frontend-entrypoint.sh /frontend-entrypoint.sh
# 去掉 Windows 编写可能带入的 \r，再赋可执行权限
RUN sed -i 's/\r$//' /frontend-entrypoint.sh && chmod +x /frontend-entrypoint.sh
# 清掉 nginx 官方默认站点，由我们的模板渲染接管
RUN rm -f /etc/nginx/conf.d/default.conf

# 默认后端地址（分开部署 compose 服务名；可由 env / 挂载 .env 覆盖）
ENV BACKEND_URL=http://backend:8000

EXPOSE 80

ENTRYPOINT ["/frontend-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
