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

# 逐帧导出参数
EXPORT_FPS = 30                 # 输出视频帧率
FRAME_JPEG_QUALITY = 92         # 单帧截图 JPEG 质量
MAX_EXPORT_FRAMES = 54000       # 帧数上限（30 分钟 @30fps），超出提示提高倍速
FFMPEG_CRF = '16'               # H.264 恒定质量（越小越清晰）


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
    使用 Playwright 逐帧截图并经 ffmpeg 合成动画视频

    打开前端轨迹详情页的导出模式，对每一帧调用页面暴露的
    `__seekExportFrame(t)`（定位动画 → 等待瓦片加载与渲染完成）后截图，
    最终合成为 H.264 MP4。相比浏览器实时录屏：
    - 画面不受录制压缩影响（源帧为高保真截图）
    - 瓦片必然加载完成，旋转视野外不会出现空白
    - 输出时长与帧严格对应（输出帧率 = EXPORT_FPS）

    Args:
        track_id: 轨迹 ID
        duration_ms: 轨迹总时长（毫秒）
        token: 用户 token（注入页面 localStorage 以复用登录会话）
        request: 导出请求（含分辨率、倍速与视图状态）
        progress_callback: 进度回调（0-100）

    Returns:
        下载路径（相对于 EXPORT_DIR，例如 animation/xxx.mp4）
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
    逐帧截图实现（必须在支持子进程的事件循环中运行）
    """
    if progress_callback is None:
        progress_callback = lambda p: None  # noqa: E731

    export_dir = Path(settings.EXPORT_DIR) / 'animation'
    export_dir.mkdir(parents=True, exist_ok=True)

    width, height = RESOLUTION_DIMENSIONS.get(request.resolution, (1920, 1080))

    # 输出帧序列：覆盖 [start_time, duration_ms]，按倍速压缩时长
    speed = max(request.speed, 0.25)
    start_ms = max(0.0, request.start_time)
    out_duration_s = max(0.0, (duration_ms - start_ms) / 1000.0 / speed)
    frame_count = int(math.ceil(out_duration_s * EXPORT_FPS))
    if frame_count < 1:
        raise ValueError("导出区间时长为 0（起点已到轨迹末尾）")
    if frame_count > MAX_EXPORT_FRAMES:
        raise ValueError(
            f"导出帧数 {frame_count} 超过上限 {MAX_EXPORT_FRAMES}（约 "
            f"{MAX_EXPORT_FRAMES // EXPORT_FPS} 分钟 @30fps），请提高导出倍速"
        )

    frames_dir = export_dir / 'frames' / f'{track_id}_{int(time.time() * 1000)}'
    frames_dir.mkdir(parents=True, exist_ok=True)

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
    if request.engine:
        # 地图引擎（SDK / Leaflet 瓦片），与用户点击导出时一致
        params['engine'] = request.engine
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

    # 整体超时：单帧最坏 ~2.5s + 编译余量
    timeout_s = frame_count * 2.5 + 180

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--enable-webgl', '--ignore-gpu-blocklist'],
        )
        context = await browser.new_context(
            viewport={'width': width, 'height': height},
        )
        # 注入登录会话（复用导出用户自己的 token）
        await context.add_init_script(
            f"localStorage.setItem('token', {json.dumps(token)});"
        )

        page = await context.new_page()
        try:
            # 页面存在持续轮询/WebSocket 连接，networkidle 永不满足，改用 domcontentloaded
            await page.goto(url, wait_until='domcontentloaded', timeout=60000)

            # 阶段一：等待页面就绪（数据加载 + 地图渲染完成，前端设置 exportState='ready'）
            ready_deadline = time.time() + 60
            state = None
            while time.time() < ready_deadline:
                current_path = await page.evaluate("window.location.pathname")
                if not current_path.startswith(f'/tracks/{track_id}'):
                    raise RuntimeError(f"导出页面跳转，当前路径: {current_path}")

                state = await page.evaluate(
                    "document.body?.dataset?.exportState || null"
                )
                if state in ('ready', 'completed', 'failed'):
                    break
                await asyncio.sleep(1)

            if state != 'ready':
                raise RuntimeError(
                    f"导出页面未就绪（state={state or 'unknown'}）"
                )

            if progress_callback:
                await progress_callback(5.0)

            # 阶段二：逐帧定位 + 截图（页面等待瓦片加载与渲染完成后返回）
            if not await page.evaluate("typeof window.__seekExportFrame === 'function'"):
                raise RuntimeError("导出页面未暴露 __seekExportFrame（回放播放器未挂载）")

            frame_deadline = time.time() + timeout_s
            for i in range(frame_count):
                if time.time() > frame_deadline:
                    raise RuntimeError(f"逐帧导出超时（{frame_count} 帧未在限时内完成）")
                t_ms = min(start_ms + i / EXPORT_FPS * speed * 1000, duration_ms)
                await page.evaluate("(t) => window.__seekExportFrame(t)", t_ms)
                frame_path = frames_dir / f"{i:06d}.jpg"
                await page.screenshot(
                    path=str(frame_path), type='jpeg', quality=FRAME_JPEG_QUALITY
                )
                if progress_callback:
                    await progress_callback(5.0 + 85.0 * (i + 1) / frame_count)
        finally:
            await context.close()
            await browser.close()

    if progress_callback:
        await progress_callback(92.0)

    # ffmpeg 合成 H.264 MP4（恒定质量，键控帧率与截图一致）
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'track_{track_id}_animation_{timestamp}.mp4'
    final_path = export_dir / filename
    result = subprocess.run(
        [
            'ffmpeg', '-y',
            '-framerate', str(EXPORT_FPS),
            '-i', str(frames_dir / '%06d.jpg'),
            '-c:v', 'libx264',
            '-crf', FFMPEG_CRF,
            '-preset', 'medium',
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            str(final_path),
        ],
        capture_output=True, timeout=1800,
    )
    if result.returncode != 0 or not final_path.exists():
        stderr_tail = result.stderr.decode(errors='ignore')[-400:]
        raise RuntimeError(f"ffmpeg 合成失败: {stderr_tail}")

    if progress_callback:
        await progress_callback(100.0)

    # 清理帧目录
    shutil.rmtree(frames_dir, ignore_errors=True)

    return f'animation/{filename}'
