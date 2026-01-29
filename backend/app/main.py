"""
FastAPI 主应用
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import logging
import traceback

from app.core.config import settings
from app.core.database import init_db
from app.api import auth, admin, tracks, tasks, road_signs, logs, live_recordings, websocket

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
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
        # 取消所有后台任务
        from app.services.track_service import track_service
        import logging
        logger = logging.getLogger(__name__)

        try:
            await track_service.cancel_all_tasks()
        except Exception as e:
            logger.warning(f"Error cancelling background tasks: {e}")

        # 关闭数据库引擎和连接池
        try:
            await engine.dispose()
        except Exception as e:
            logger.warning(f"Error disposing database engine: {e}")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="基于 Web 的轨迹管理系统",
    lifespan=lifespan,
)

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
    # 打印详细的错误信息到控制台
    logger.error(f"Unhandled exception: {type(exc).__name__}: {exc}")
    logger.error(f"Request: {request.method} {request.url}")
    logger.error(f"Traceback:\n{traceback.format_exc()}")

    # 返回错误响应
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"Internal Server Error: {str(exc)}",
            "type": type(exc).__name__,
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
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
