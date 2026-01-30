"""
应用配置模块
支持多数据库类型：SQLite、MySQL、PostgreSQL
"""
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

    # Redis 配置 (用于 Celery)
    REDIS_URL: str = "redis://localhost:6379/0"

    # 文件存储配置
    UPLOAD_DIR: str = "data/uploads"
    TEMP_DIR: str = "data/temp"
    EXPORT_DIR: str = "data/exports"
    ROAD_SIGN_DIR: str = "data/road_signs"

    # 文件大小限制（字节）
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100 MB

    # CORS 配置
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # 首位用户自动为管理员
    FIRST_USER_IS_ADMIN: bool = True


settings = Settings()
