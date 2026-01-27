"""
Alembic 环境配置

用于配置数据库迁移的运行环境
"""
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# 导入配置和 Base
from app.core.config import settings
from app.core.database import Base
from app.models import *  # 导入所有模型，确保 Base.metadata 包含所有表

# Alembic 配置对象
config = context.config

# 解释日志配置文件
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 设置 MetaData 对象
# 'target_metadata' 用于自动生成迁移脚本
target_metadata = Base.metadata

# 从 settings.DATABASE_URL 获取数据库 URL
# 注意：Alembic 需要同步驱动，所以将 aiosqlite 替换为 sqlite
database_url = settings.DATABASE_URL
if database_url.startswith("sqlite+aiosqlite"):
    database_url = database_url.replace("sqlite+aiosqlite", "sqlite")
elif database_url.startswith("mysql+asyncmy"):
    database_url = database_url.replace("mysql+asyncmy", "mysql+pymysql")
elif database_url.startswith("postgresql+asyncpg"):
    database_url = database_url.replace("postgresql+asyncpg", "postgresql+psycopg2")

config.set_main_option("sqlalchemy.url", database_url)


def run_migrations_offline() -> None:
    """
    离线模式运行迁移

    在不需要实际数据库连接的情况下生成 SQL 脚本
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """执行迁移的辅助函数"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """异步模式运行迁移"""
    configuration = config.get_section(config.config_ini_section)
    # 使用原始的异步 URL（用于 async_engine_from_config）
    configuration["sqlalchemy.url"] = settings.DATABASE_URL

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    在线模式运行迁移

    这种模式下，需要连接到实际数据库来执行迁移
    """
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
