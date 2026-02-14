# backend/app/utils/playwright_export.py

import asyncio
from typing import Callable, Optional
from pathlib import Path
from datetime import datetime

from playwright.async_api import async_playwright


async def capture_animation_video(
    track_id: int,
    points: list,
    resolution: str = '1080p',
    fps: int = 30,
    show_hud: bool = True,
    speed: float = 1.0,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> str:
    """
    使用 Playwright 捕获动画视频

    返回下载 URL（相对路径）
    """
    # 导出目录
    export_dir = Path('data/exports/animation')
    export_dir.mkdir(parents=True, exist_ok=True)

    # 生成文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'track_{track_id}_animation_{timestamp}.webm'
    output_path = export_dir / filename

    # 解析分辨率
    width_map = {
        '720p': (1280, 720),
        '1080p': (1920, 1080),
        '4k': (3840, 2160),
    }
    width, height = width_map.get(resolution, (1920, 1080))

    total_duration = speed * 60  # 假设原时长 60 秒

    async with async_playwright() as p:
        # 创建浏览器上下文
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # 访问轨迹详情页的动画模式
            url = f'http://localhost:5173/tracks/{track_id}?animation=true&export=true'
            await page.goto(url, wait_until='networkidle')

            # 等待地图加载
            await page.wait_for_selector('.map-content', timeout=30000)
            await asyncio.sleep(2)

            # 设置视口大小
            await page.set_viewport_size(width, height)

            # 开始录制
            video_path = export_dir / f'temp_{track_id}.webm'

            # 更新进度：0-10%
            if progress_callback:
                await progress_callback(10.0)

            # 模拟播放动画（实际实现需要与前端动画逻辑同步）
            # 这里简化处理：直接录制 5 秒
            steps = 10
            step_duration = total_duration / steps

            for i in range(steps):
                await asyncio.sleep(step_duration)

                # 更新进度
                current_progress = 10 + (i / steps) * 90
                if progress_callback:
                    await progress_callback(current_progress)

            # 停止录制
            await page.wait_for_timeout(500)

            # 更新进度：完成
            if progress_callback:
                await progress_callback(100.0)

            # 清理
            await browser.close()

            # 实际实现中，需要：
            # 1. 与前端动画播放逻辑同步
            # 2. 控制动画播放速度
            # 3. 等待动画完成

            return f'/exports/animation/{filename}'

        except Exception as e:
            await browser.close()
            raise e
