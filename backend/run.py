"""
自定义启动脚本 - 设置 Windows 事件循环策略
"""
import asyncio
import sys

# 在任何异步操作之前设置事件循环策略
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uvicorn

from app.core.config import settings

if __name__ == '__main__':
    # 监听地址与端口由环境变量 / .env 配置（APP_HOST / APP_PORT）
    uvicorn.run('app.main:app', host=settings.APP_HOST, port=settings.APP_PORT, reload=True)
