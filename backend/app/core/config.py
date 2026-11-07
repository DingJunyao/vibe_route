"""
应用配置模块
支持多数据库类型：SQLite、MySQL、PostgreSQL
"""
from pathlib import Path
from typing import Literal, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    # 应用基础配置
    APP_NAME: str = "Vibe Route"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # API 配置
    API_V1_PREFIX: str = "/api"

    # 服务监听配置（`python run.py` 开发启动时生效；前端 vite proxy 的 VITE_DEV_BACKEND_URL 需同步）
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # 安全配置
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 天

    # 数据库配置
    DATABASE_TYPE: Literal["sqlite", "mysql", "postgresql"] = "sqlite"

    # SQLite 配置
    SQLITE_DB_PATH: str = "data/vibe_route.db"

    # MySQL 配置
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "vibe_route"
    MYSQL_PASSWORD: str = ""
    MYSQL_DB: str = "vibe_route"

    # PostgreSQL 配置
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "vibe_route"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = "vibe_route"

    @property
    def DATABASE_URL(self) -> str:
        """根据数据库类型生成连接 URL"""
        if self.DATABASE_TYPE == "sqlite":
            return f"sqlite+aiosqlite:///{self.SQLITE_DB_PATH}"
        elif self.DATABASE_TYPE == "mysql":
            return (
                f"mysql+asyncmy://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
                f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}"
            )
        elif self.DATABASE_TYPE == "postgresql":
            return (
                f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )
        raise ValueError(f"Unsupported database type: {self.DATABASE_TYPE}")

    # 文件存储配置
    DATA_DIR: str = "data"
    UPLOAD_DIR: str = "data/uploads"
    TEMP_DIR: str = "data/temp"
    EXPORT_DIR: str = "data/exports"

    # 前端地址（动画导出等场景由后端打开页面）
    FRONTEND_URL: str = "http://localhost:5173"
    # Playwright 有头模式调试：true 时动画导出录制以有头浏览器打开，
    # 可实时观看轨迹回放录制是否符合预期（仅本地开发调试用）
    PLAYWRIGHT_HEADED: bool = False
    ROAD_SIGN_DIR: str = "data/road_signs"

    # 日志目录
    LOG_DIR: str = "logs"

    # 文件大小限制（字节）
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100 MB

    # CORS 配置
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # 首位用户自动为管理员
    FIRST_USER_IS_ADMIN: bool = True

    # 覆盖层配置
    OVERLAY_ALLOW_USER_FONTS: bool = False  # 是否允许用户上传自定义字体
    OVERLAY_MAX_USER_FONTS: int = 10  # 每个用户最多上传字体数量
    OVERLAY_MAX_USER_FONTS_SIZE_MB: int = 100  # 每个用户字体总大小限制(MB)

    @property
    def overlay_allow_user_fonts(self) -> bool:
        """是否允许用户上传自定义字体"""
        return self.OVERLAY_ALLOW_USER_FONTS

    @property
    def overlay_max_user_fonts(self) -> int:
        """每个用户最多上传字体数量"""
        return self.OVERLAY_MAX_USER_FONTS

    @property
    def overlay_max_user_fonts_size_mb(self) -> int:
        """每个用户字体总大小限制(MB)"""
        return self.OVERLAY_MAX_USER_FONTS_SIZE_MB


settings = Settings()


# 随应用打包的路牌模板目录（app/assets/road_sign_templates/）。
# 不放 data/ 下：.dockerignore 排除 backend/data，且 Docker 里 data/ 会被挂载卷覆盖，
# 打包进 app/ 才能保证镜像内开箱即用。
BUNDLED_ROAD_SIGN_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / 'assets' / 'road_sign_templates'


def resolve_road_sign_template(name: str) -> Path:
    """解析路牌模板文件路径。

    优先 data/templates/（兼容旧部署手工放置/定制过的模板），
    不存在时回落到随应用打包的 app/assets/road_sign_templates/。
    两者都缺失时返回 data 路径，保持原有「文件不存在」的报错行为。
    """
    legacy = Path(settings.ROAD_SIGN_DIR).parent / 'templates' / name
    if legacy.exists():
        return legacy
    bundled = BUNDLED_ROAD_SIGN_TEMPLATES_DIR / name
    return bundled if bundled.exists() else legacy
