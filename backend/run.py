"""
自定义启动脚本 - 设置 Windows 事件循环策略
"""
import asyncio
import sys

# 在任何异步操作之前设置事件循环策略
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uvicorn

if __name__ == '__main__':
    uvicorn.run('app.main:app', host='0.0.0.0', port=8000, reload=True)
