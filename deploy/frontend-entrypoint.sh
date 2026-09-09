#!/bin/sh
# 前端容器启动入口：把 BACKEND_URL 渲染进 nginx 配置，再启动 nginx。
set -e

# 默认后端地址：分开部署的 compose 服务名。
# 统一/裸部署由环境变量或 /app/.env 覆盖。
: "${BACKEND_URL:=http://backend:8000}"

# 若挂载了配置文件（./frontend/.env:/app/.env），加载其中的 BACKEND_URL。
if [ -f /app/.env ]; then
    . /app/.env 2>/dev/null || true
fi

echo "[frontend-entrypoint] BACKEND_URL=${BACKEND_URL}"

# 渲染 nginx 配置：限定只替换 BACKEND_URL，保留 $host 等 nginx 内置变量。
envsubst '${BACKEND_URL}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf

exec "$@"
