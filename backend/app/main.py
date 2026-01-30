"""
FastAPI 主应用
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
import logging
import traceback
import uuid

from app.core.config import settings
from app.core.database import init_db
from app.core.rate_limit import limiter
from app.api import auth, admin, tracks, tasks, road_signs, logs, live_recordings, websocket

# 配置日志
LOG_LEVEL = logging.DEBUG if settings.DEBUG else logging.WARNING
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动缓存清理任务
    from app.utils.cache import config_cache
    await config_cache.start_cleanup_task()
    logger.info("Cache cleanup task started")

    # 启动时初始化数据库
    await init_db()

    # 初始化默认配置
    from app.core.database import async_session_maker, engine
    from app.services.config_service import config_service
    async with async_session_maker() as db:
        await config_service.init_default_configs(db)

    try:
        yield
    finally:
        # 关闭时的清理工作（无论是否发生异常都会执行）
        logger.info("Starting graceful shutdown...")

        # 1. 停止缓存清理任务
        try:
            await config_cache.stop_cleanup_task()
            logger.info("Cache cleanup task stopped")
        except Exception as e:
            logger.warning(f"Error stopping cache cleanup task: {e}")

        # 2. 取消所有后台任务
        from app.services.track_service import track_service
        try:
            await track_service.cancel_all_tasks()
            logger.info("Background tasks cancelled")
        except Exception as e:
            logger.warning(f"Error cancelling background tasks: {e}")

        # 3. 关闭所有 WebSocket 连接
        from app.api.websocket import live_track_manager
        try:
            # 关闭所有实时记录连接
            for recording_id in list(live_track_manager.recording_connections.keys()):
                await live_track_manager.close_recording_connections(
                    recording_id, code=1001, reason="Server shutdown"
                )
            # 关闭所有轨迹连接
            for track_id in list(live_track_manager.track_connections.keys()):
                connections = live_track_manager.track_connections[track_id].copy()
                for ws in connections:
                    try:
                        await ws.close(code=1001, reason="Server shutdown")
                    except Exception:
                        pass
                live_track_manager.track_connections[track_id].clear()
            logger.info("WebSocket connections closed")
        except Exception as e:
            logger.warning(f"Error closing WebSocket connections: {e}")

        # 4. 关闭数据库引擎和连接池
        try:
            await engine.dispose()
            logger.info("Database engine disposed")
        except Exception as e:
            logger.warning(f"Error disposing database engine: {e}")

        logger.info("Graceful shutdown completed")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="基于 Web 的轨迹管理系统",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加 GZip 压缩中间件
# 只对响应进行压缩，不处理请求
# 对于大于 500 字节的响应启用压缩，压缩级别 6（平衡速度和压缩率）
app.add_middleware(GZipMiddleware, minimum_size=500, compresslevel=6)


@app.middleware("http")
async def add_request_id_middleware(request: Request, call_next):
    """为每个请求添加唯一的请求ID"""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    # 记录请求开始
    logger.info(f"RequestID: {request_id} | {request.method} {request.url.path}")

    response = await call_next(request)

    # 添加请求ID到响应头
    response.headers["X-Request-ID"] = request_id

    # 记录请求完成
    logger.info(f"RequestID: {request_id} | Status: {response.status_code}")

    return response

# 注册路由
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(admin.router, prefix=settings.API_V1_PREFIX)
app.include_router(tracks.router, prefix=settings.API_V1_PREFIX)
app.include_router(tasks.router, prefix=settings.API_V1_PREFIX)
app.include_router(road_signs.router, prefix=settings.API_V1_PREFIX)
app.include_router(logs.router, prefix=settings.API_V1_PREFIX)
app.include_router(live_recordings.router, prefix=settings.API_V1_PREFIX)
app.include_router(websocket.router, prefix=settings.API_V1_PREFIX)


# 全局异常处理器 - 捕获所有未处理的异常并打印详细错误信息
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器"""
    # 获取请求ID（如果有）
    request_id = getattr(request.state, "request_id", "unknown")

    # 打印详细的错误信息到控制台
    logger.error(f"RequestID: {request_id} | Unhandled exception: {type(exc).__name__}: {exc}")
    logger.error(f"RequestID: {request_id} | Request: {request.method} {request.url}")
    logger.error(f"RequestID: {request_id} | Traceback:\n{traceback.format_exc()}")

    # 返回错误响应
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"Internal Server Error: {str(exc)}",
            "type": type(exc).__name__,
            "request_id": request_id,
        }
    )


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """健康检查"""
    # 检查数据库连接
    from app.core.database import async_session_maker
    try:
        async with async_session_maker() as db:
            await db.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"

    return {
        "status": "ok" if db_status == "healthy" else "degraded",
        "database": db_status,
        "version": settings.APP_VERSION,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
