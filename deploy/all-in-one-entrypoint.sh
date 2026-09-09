#!/bin/sh
# all-in-one 容器启动入口：渲染 nginx 配置，再交给 supervisord 拉起 nginx + uvicorn。
set -e

# all-in-one：uvicorn 与 nginx 同容器，后端地址默认指向本地。
: "${BACKEND_URL:=http://127.0.0.1:8000}"

# 若挂载了 /app/.env（后端配置），允许覆盖 BACKEND_URL（一般保持 127.0.0.1）。
if [ -f /app/.env ]; then
    . /app/.env 2>/dev/null || true
fi

echo "[all-in-one-entrypoint] BACKEND_URL=${BACKEND_URL}"

envsubst '${BACKEND_URL}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf

exec "$@"
