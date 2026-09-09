# backend/app/utils/playwright_export.py

import asyncio
import json
import math
import shutil
import subprocess
import sys
import time
from typing import Callable, Optional
from pathlib import Path
from datetime import datetime
from urllib.parse import urlencode

from playwright.async_api import async_playwright

from ..core.config import settings
from ..schemas.animation import AnimationExportRequest

# 分辨率映射（视口尺寸）
RESOLUTION_DIMENSIONS = {
    '720p': (1280, 720),
    '1080p': (1920, 1080),
    '4k': (3840, 2160),
}


def _capture_in_proactor_loop(
    track_id: int,
    duration_ms: float,
    token: str,
    request: AnimationExportRequest,
    progress_callback: Optional[Callable[[float], None]],
) -> str:
    """
    在独立线程的 Proactor 事件循环中执行录制

    Windows 上 VSCode debugpy 调试时主事件循环为 SelectorEventLoop（不支持子进程），
    无法启动 Playwright 浏览器子进程；此处直接实例化 Proactor 循环规避。
    注意：不能通过 set_event_loop_policy 设置（debugpy 会拦截该调用），
    因此直接用构造器创建，绕过 policy 机制。
    """
    loop = asyncio.ProactorEventLoop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(
            _capture_impl(track_id, duration_ms, token, request, progress_callback)
        )
    finally:
        loop.close()
        asyncio.set_event_loop(None)


async def capture_animation_video(
    track_id: int,
    duration_ms: float,
    token: str,
    request: AnimationExportRequest,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> str:
    """
    使用 Playwright 录制动画视频

    打开前端轨迹详情页的导出模式，页面就绪后触发自动播放，
    完成后返回视频下载 URL（相对路径）。

    Args:
        track_id: 轨迹 ID
        duration_ms: 轨迹时长（毫秒），用于计算整体超时
        token: 用户 token（注入页面 localStorage 以复用登录会话）
        request: 导出请求（含分辨率、倍速与视图状态）
        progress_callback: 进度回调（0-100）

    Returns:
        下载 URL（相对路径，如 /exports/animation/xxx.webm）
    """
    if sys.platform == 'win32':
        return await asyncio.to_thread(
            _capture_in_proactor_loop,
            track_id,
            duration_ms,
            token,
            request,
            progress_callback,
        )
    return await _capture_impl(track_id, duration_ms, token, request, progress_callback)


async def _capture_impl(
    track_id: int,
    duration_ms: float,
    token: str,
    request: AnimationExportRequest,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> str:
    """
    Playwright 录制实现（必须在支持子进程的事件循环中运行）
    """
    if progress_callback is None:
        progress_callback = lambda p: None  # noqa: E731

    export_dir = Path(settings.EXPORT_DIR) / 'animation'
    export_dir.mkdir(parents=True, exist_ok=True)

    # 每任务独立录制目录（Playwright 要求目录存在且为空）
    record_dir = export_dir / 'recordings' / f'{track_id}_{int(time.time() * 1000)}'
    record_dir.mkdir(parents=True, exist_ok=True)

    width, height = RESOLUTION_DIMENSIONS.get(request.resolution, (1920, 1080))

    # 构造导出模式 URL
    params = {
        'export': 'true',
        'speed': request.speed,
        'startTime': request.start_time,
        'camera': request.camera_mode,
        'orientation': request.orientation_mode,
        'marker': request.marker_style,
        'infoPanel': '1' if request.show_info_panel else '0',
        'hud': '1' if request.show_hud else '0',
    }
    if request.layer_id:
        params['layer'] = request.layer_id
    if request.zoom is not None:
        # 画幅修正：用户在详情页的 zoom 是基于其地图画幅调整的，
        # 导出画幅（如 1920x1080）与详情页画幅不同，按最小维度比例修正 zoom，
        # 保证用户在详情页看到的内容完整包含在导出画面中。
        zoom = request.zoom
        if request.viewport_width and request.viewport_height:
            export_min = min(width, height)
            viewport_min = min(request.viewport_width, request.viewport_height)
            if viewport_min > 0 and export_min > 0:
                zoom += math.log2(export_min / viewport_min)
        params['zoom'] = zoom
    if request.center_lat is not None and request.center_lng is not None:
        params['centerLat'] = request.center_lat
        params['centerLng'] = request.center_lng

    url = f"{settings.FRONTEND_URL}/tracks/{track_id}?{urlencode(params)}"

    # 整体超时：预估播放时长 * 2 + 60s 兜底
    speed = max(request.speed, 0.25)
    timeout_sec = (duration_ms / 1000 / speed) * 2 + 60

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--enable-webgl', '--ignore-gpu-blocklist'],
        )
        context = await browser.new_context(
            viewport={'width': width, 'height': height},
            record_video_dir=str(record_dir),
            record_video_size={'width': width, 'height': height},
        )
        # 注入登录会话（复用导出用户自己的 token）
        await context.add_init_script(
            f"localStorage.setItem('token', {json.dumps(token)});"
        )

        page = await context.new_page()
        try:
            # 页面存在持续轮询/WebSocket 连接，networkidle 永不满足，改用 domcontentloaded
            await page.goto(url, wait_until='domcontentloaded', timeout=60000)
            goto_done_at = time.monotonic()

            # 阶段一：等待页面就绪（数据加载 + 地图渲染完成，前端设置 exportState='ready'）
            ready_deadline = time.time() + 60
            state = None
            ready_offset = 0.0  # 从 goto 完成到就绪的时长（用于裁剪录制开头的遮罩期）
            while time.time() < ready_deadline:
                current_path = await page.evaluate("window.location.pathname")
                if not current_path.startswith(f'/tracks/{track_id}'):
                    raise RuntimeError(f"导出页面跳转，当前路径: {current_path}")

                state = await page.evaluate(
                    "document.body?.dataset?.exportState || null"
                )
                if state in ('ready', 'completed', 'failed'):
                    ready_offset = time.monotonic() - goto_done_at
                    break
                await asyncio.sleep(1)

            if state != 'ready':
                raise RuntimeError(
                    f"导出页面未就绪（state={state or 'unknown'}）"
                )

            if progress_callback:
                await progress_callback(10.0)

            # 阶段二：缓冲后触发播放（视频从起点静止画面后开始动画）
            await asyncio.sleep(0.5)
            await page.evaluate(
                "window.__startExportPlayback && window.__startExportPlayback()"
            )

            # 阶段三：等待播放完成信号，期间轮询进度
            deadline = time.time() + timeout_sec
            state = None
            while time.time() < deadline:
                # 页面跳走（如登录失效跳转登录页）视为失败
                current_path = await page.evaluate("window.location.pathname")
                if not current_path.startswith(f'/tracks/{track_id}'):
                    raise RuntimeError(f"导出页面跳转，当前路径: {current_path}")

                state = await page.evaluate(
                    "document.body?.dataset?.exportState || null"
                )
                if state in ('completed', 'failed'):
                    break

                try:
                    pct = await page.evaluate(
                        "parseFloat(document.body?.dataset?.exportProgress || '0') || 0"
                    )
                    if progress_callback:
                        await progress_callback(10.0 + pct * 0.9)
                except Exception:
                    pass  # 页面暂不可读时忽略，下轮再试

                await asyncio.sleep(1)

            if state != 'completed':
                raise RuntimeError(
                    f"动画导出{'失败' if state == 'failed' else '超时'}"
                    f"（state={state or 'unknown'}）"
                )

            if progress_callback:
                await progress_callback(100.0)
        finally:
            # 关闭 context 使视频落盘
            await context.close()
            await browser.close()

    # 移动录制文件到最终位置
    video_files = list(record_dir.glob('*.webm'))
    if not video_files:
        raise RuntimeError("录制完成但未生成视频文件")

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'track_{track_id}_animation_{timestamp}.webm'
    final_path = export_dir / filename
    video_files[0].rename(final_path)

    # 清理录制目录
    record_dir.rmdir()

    # 裁剪录制开头的遮罩期（从地图起点画面开始），ffmpeg 不可用时跳过
    trim_offset = ready_offset + 0.5
    if trim_offset > 1.0 and shutil.which('ffmpeg'):
        trimmed_path = export_dir / f'trim_{filename}'
        result = subprocess.run(
            ['ffmpeg', '-y', '-i', str(final_path), '-ss', str(trim_offset),
             '-c', 'copy', str(trimmed_path)],
            capture_output=True, timeout=600,
        )
        if result.returncode == 0 and trimmed_path.exists() and trimmed_path.stat().st_size > 1000:
            trimmed_path.replace(final_path)

    return f'/exports/animation/{filename}'
