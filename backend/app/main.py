# -*- coding: utf-8 -*-
"""
FastAPI 主应用
"""
import asyncio
import sys
import traceback
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.gzip import GZipMiddleware

# Windows 上需要使用 ProactorEventLoop 来支持子进程
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Windows 上需要使用 ProactorEventLoop 来支持子进程
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from app.core.config import settings
from app.core.database import init_db
from app.core.rate_limit import limiter
from app.api import auth, admin, tracks, tasks, road_signs, logs, live_recordings, websocket, geo_editor, poster, user_config, shared, interpolation, overlay_templates

# 配置 loguru 日志
from loguru import logger as loguru_logger

# 移除默认的 logger
loguru_logger.remove()

# 添加终端处理器（带颜色）
loguru_logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="DEBUG" if settings.DEBUG else "INFO",
    colorize=True,
)

# 添加文件处理器（所有日志）
log_dir = Path(settings.LOG_DIR)
log_dir.mkdir(parents=True, exist_ok=True)
loguru_logger.add(
    log_dir / "app_{time:YYYY-MM-DD}.log",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    level="DEBUG",
    rotation="00:00",  # 每天午夜轮转
    retention="30 days",  # 保留 30 天
    compression="zip",  # 压缩旧日志
    encoding="utf-8",
)

# 添加错误日志文件（仅错误级别）
loguru_logger.add(
    log_dir / "app_error_{time:YYYY-MM-DD}.log",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    level="ERROR",
    rotation="00:00",
    retention="90 days",
    compression="zip",
    encoding="utf-8",
)

# 将 loguru 导出为标准 logging 接口兼容
class LoggerAdapter:
    """适配器类，使 loguru 兼容标准 logging 接口"""

    def __init__(self, logger_instance):
        self._logger = logger_instance

    def debug(self, msg, *args, **kwargs):
        self._logger.opt(depth=1).debug(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self._logger.opt(depth=1).info(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self._logger.opt(depth=1).warning(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self._logger.opt(depth=1).error(msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self._logger.opt(depth=1).critical(msg, *args, **kwargs)

    def exception(self, msg, *args, **kwargs):
        self._logger.opt(depth=1).exception(msg, *args, **kwargs)

logger = LoggerAdapter(loguru_logger)


def _convert_gb5765_fonts_to_woff2():
    """Pre-convert GB 5765 fonts to WOFF2 format at startup"""
    import time
    
    print("=" * 60)
    print("GB5765 FONT CONVERSION: Starting...")
    print("=" * 60)
    
    # Small delay to ensure output is visible
    time.sleep(0.1)
    
    try:
        from pathlib import Path
        from app.core.config import settings
    except ImportError as e:
        print(f"ERROR: Cannot import: {e}")
        return
    
    try:
        fonts_dir = Path(settings.ROAD_SIGN_DIR).parent / 'fonts'
        print(f"Fonts directory: {fonts_dir}")
        print(f"Directory exists: {fonts_dir.exists()}")
    except Exception as e:
        print(f"ERROR: Cannot determine fonts_dir: {e}")
        return
    
    if not fonts_dir.exists():
        print("ERROR: Fonts directory does not exist, skipping conversion")
        return
    
    # GB 5765 font files - using underscores as they appear in filesystem
    gb_fonts = ['jtbz_A.ttf', 'jtbz_B.ttf', 'jtbz_C.ttf']
    woff2_dir = fonts_dir / 'woff2_cache'
    woff2_dir.mkdir(exist_ok=True)
    
    print(f"Processing {len(gb_fonts)} GB 5765 fonts")
    
    for font_name in gb_fonts:
        source_path = fonts_dir / font_name
        woff2_path = woff2_dir / font_name.replace('.ttf', '.woff2')
        
        # Check if WOFF2 already exists and is up to date
        need_conversion = True
        if woff2_path.exists():
            source_mtime = source_path.stat().st_mtime
            woff2_mtime = woff2_path.stat().st_mtime
            if woff2_mtime >= source_mtime:
                need_conversion = False
                print(f"  {font_name}: Cache is up to date, skipping")
        
        if not need_conversion:
            continue
        
        try:
            from fontTools.ttLib import TTFont
            from io import BytesIO
            
            # Read original font
            with open(source_path, 'rb') as f:
                content = f.read()
            
            # Load and sanitize
            font = TTFont(BytesIO(content))
            original_tables = list(font.keys())
            print(f"  {font_name}: Original tables: {original_tables}")

            # Remove problematic tables
            # vmtx requires vhea, so remove both or neither
            # post table may be corrupted, remove and rebuild a minimal one
            has_vhea = 'vhea' in font
            has_vmtx = 'vmtx' in font

            problematic_tables = []
            for table_tag in font.keys():
                if table_tag in ('VDMX', 'GASP', 'GDEF', 'GPOS', 'GSUB', 'gasp', 'gvar', 'fvar', 'STAT', 'trak', 'kern'):
                    problematic_tables.append(table_tag)
                # Remove vhea and vmtx together (vmtx depends on vhea)
                elif table_tag in ('vhea', 'vmtx'):
                    problematic_tables.append(table_tag)
                # Remove post table (will rebuild a minimal one)
                elif table_tag == 'post':
                    problematic_tables.append(table_tag)

            if problematic_tables:
                print(f"  {font_name}: Removing {len(problematic_tables)} problematic tables: {problematic_tables}")

                for table_tag in problematic_tables:
                    try:
                        del font[table_tag]
                    except Exception as e:
                        print(f"  {font_name}: Failed to remove {table_tag}: {e}")

            # Rebuild post table (minimal version)
            try:
                from fontTools.ttLib import newTable
                font['post'] = newTable('post')
                # Set required attributes for the post table header
                font['post'].formatType = 3.0
                font['post'].italicAngle = 0.0
                font['post'].underlinePosition = -100
                font['post'].underlineThickness = 50
                font['post'].isFixedPitch = 0
                font['post'].minMemType42 = 0
                font['post'].maxMemType42 = 0
                font['post'].minMemType1 = 0
                font['post'].maxMemType1 = 0
                print(f"  {font_name}: Rebuilt post table")
            except Exception as e:
                print(f"  {font_name}: Failed to rebuild post table: {e}")
                raise  # 让错误传播，停止处理
            
            # Save as WOFF2
            woff2_output = BytesIO()
            font.save(woff2_output, 'WOFF2')
            
            woff2_content = woff2_output.getvalue()
            
            # Write to cache directory
            with open(woff2_path, 'wb') as f:
                f.write(woff2_content)
            
            print(f"  {font_name}: Converted to WOFF2 ({len(woff2_content)} bytes, removed {len(problematic_tables)} tables)")
        except Exception as e:
            print(f"  {font_name}: FAILED - {e}")
            import traceback
            traceback.print_exc()
    
    print("=" * 60)
    print("GB5765 FONT CONVERSION: Completed!")
    print("=" * 60)
    time.sleep(0.1)  # Ensure final message is visible


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时预转换 GB 5765 字体为 WOFF2 格式
    # 这些字体有非标准的表结构，浏览器 OTS 会拒绝
    # 预转换避免每次请求时都处理
    _convert_gb5765_fonts_to_woff2()

    # 启动缓存清理任务
    from app.utils.cache import config_cache
    await config_cache.start_cleanup_task()
    logger.info("Cache cleanup task started")

    # 启动时初始化数据库
    await init_db()

    # 初始化默认配置和空间服务
    from app.core.database import async_session_maker, engine
    from app.services.config_service import config_service
    from app.services.spatial import create_spatial_service, SpatialBackend

    async with async_session_maker() as db:
        await config_service.init_default_configs(db)

        # 初始化空间服务
        configs = await config_service.get_all_configs(db, use_cache=False)
        spatial_backend_config = configs.get("spatial_backend", "auto")
        try:
            spatial_backend = SpatialBackend(spatial_backend_config)
        except ValueError:
            spatial_backend = SpatialBackend.AUTO

        spatial_service = await create_spatial_service(db, spatial_backend)
        capability_info = spatial_service.get_capability_info()
        logger.info(f"Spatial service initialized: {capability_info['backend']} - {capability_info['description']}")

        # 将空间服务注入到服务实例中
        from app.services.track_service import track_service
        from app.services.live_recording_service import live_recording_service

        track_service.spatial_service = spatial_service
        live_recording_service.spatial_service = spatial_service

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
app.include_router(geo_editor.router, prefix=settings.API_V1_PREFIX)
app.include_router(poster.router, prefix="/api/poster", tags=["poster"])
app.include_router(user_config.router, prefix=settings.API_V1_PREFIX)
app.include_router(shared.router, prefix=settings.API_V1_PREFIX)  # 公开分享接口
app.include_router(interpolation.router, prefix=settings.API_V1_PREFIX)
app.include_router(overlay_templates.router, prefix=settings.API_V1_PREFIX)  # 覆盖层模板


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
