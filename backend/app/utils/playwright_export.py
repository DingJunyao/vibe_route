# backend/app/utils/playwright_export.py

import asyncio
import base64
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

# 导出参数
EXPORT_FPS = 30                 # 逐帧模式的输出帧率
FRAME_JPEG_QUALITY = 92         # 逐帧截图 JPEG 质量
SCREENCAST_JPEG_QUALITY = 90    # 流式录制 CDP screencast JPEG 质量
FRAME_MODE_MAX_FRAMES = 900     # 逐帧模式帧数上限（约 30s @30fps），更长输出走流式录制
FFMPEG_CRF = '16'               # H.264 恒定质量（越小越清晰）
WARM_LEAD_OUTPUT_S = 45.0       # 预热页领先主录制页的输出时间（秒）
WARM_FOLLOW_INTERVAL_S = 2.0    # 预热页跟随定位间隔（秒）

# 流式录制：CDP screencast 每帧事件回调 → ffmpeg stdin 的传输任务
def _start_frame_pump(
    cdp,
    ffmpeg_stdin,
) -> tuple:
    """
    启动帧搬运线程：从同步队列取 screencast 帧写入 ffmpeg stdin
    （挂钟时间戳由 -use_wallclock_as_timestamps 赋予），随后调度 screencastFrameAck。

    base64 解码与管道写放在独立线程（阻塞写天然形成对编码器的背压），
    事件循环每帧只剩入队与 ACK 调度——避免 HTTP 接口在录制期间被饿死。

    Returns:
        (on_frame, stop)：on_frame 为 CDP screencastFrame 事件回调；stop 用于收尾
    """
    import queue as pyqueue
    import threading

    sync_q: pyqueue.Queue = pyqueue.Queue(maxsize=400)
    loop = asyncio.get_running_loop()

    def ack(session_id: str) -> None:
        async def _ack() -> None:
            try:
                await cdp.send('Page.screencastFrameAck', {'sessionId': session_id})
            except Exception:
                pass
        loop.create_task(_ack())

    def worker() -> None:
        while True:
            params = sync_q.get()
            if params is None:
                break
            try:
                ffmpeg_stdin.write(base64.b64decode(params['data']))
            except (BrokenPipeError, OSError, ValueError):
                break
            ack(params['sessionId'])

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    def on_frame(params) -> None:
        # 队列满时立即回执丢弃该帧（挂钟时间轴下表现为一瞬停帧），防止内存堆积
        try:
            sync_q.put_nowait(params)
        except pyqueue.Full:
            ack(params['sessionId'])

    def stop() -> None:
        sync_q.put(None)

    return on_frame, stop


def _capture_in_proactor_loop(
    track_id: int,
    duration_ms: float,
    token: str,
    request: AnimationExportRequest,
    progress_callback: Optional[Callable[[float], None]],
    task_id: str = '',
    cancel_check: Optional[Callable[[], bool]] = None,
) -> str:
    """
    在独立线程的 Proactor 事件循环中执行录制

    Windows 上 VSCode debugpy 调试时主事件循环为 SelectorEventLoop（不支持子进程），
    无法启动 Playwright 浏览器子进程；此处直接实例化 Proactor 循环规避。
    注意：不能通过 set_event_loop_policy 设置（debugpy 会拦截该调用），
    因此直接用构造器创建，绕过 policy 机制。
    线程无法被 asyncio 取消，取消依赖 cancel_check 的协作式检查。
    """
    loop = asyncio.ProactorEventLoop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(
            _capture_impl(track_id, duration_ms, token, request, progress_callback, task_id, cancel_check)
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
    task_id: str = '',
    cancel_check: Optional[Callable[[], bool]] = None,
) -> str:
    """
    使用 Playwright 录制动画视频，合成为 H.264 MP4

    打开前端轨迹详情页的导出模式，按输出时长自动选择两种采集方式：
    - 短输出（≤ FRAME_MODE_MAX_FRAMES/EXPORT_FPS 秒）：逐帧截图——对每帧调用页面
      `__seekExportFrame(t)`（定位动画 → 等待瓦片加载与渲染完成）后截图，
      质量最优、瓦片必然加载完成；
    - 长输出（数小时）：CDP screencast 流式录制——页面实时播放，JPEG 帧经
      ffmpeg stdin（挂钟时间戳）流式编码，耗时 ≈ 输出时长，不落盘中间帧。

    Args:
        track_id: 轨迹 ID
        duration_ms: 轨迹总时长（毫秒）
        token: 用户 token（注入页面 localStorage 以复用登录会话）
        request: 导出请求（含分辨率、倍速与视图状态）
        progress_callback: 进度回调（0-100）
        task_id: 任务 ID（用于文件命名与逐帧目录隔离）
        cancel_check: 取消检查（返回 True 时尽快抛出中止录制），线程路径必须提供

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
            task_id,
            cancel_check,
        )
    return await _capture_impl(track_id, duration_ms, token, request, progress_callback, task_id, cancel_check)


def _build_export_url(track_id: int, request: AnimationExportRequest, width: int, height: int) -> str:
    """构造导出模式页面 URL（含视图状态参数）"""
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

    return f"{settings.FRONTEND_URL}/tracks/{track_id}?{urlencode(params)}"


async def _open_export_page(
    p,
    track_id: int,
    width: int,
    height: int,
    token: str,
    request: AnimationExportRequest,
):
    """
    启动浏览器并打开导出模式页面，等待就绪（数据加载 + 地图渲染完成）

    Returns:
        (browser, context, page)
    """
    url = _build_export_url(track_id, request, width, height)

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
    # 页面存在持续轮询/WebSocket 连接，networkidle 永不满足，改用 domcontentloaded
    await page.goto(url, wait_until='domcontentloaded', timeout=60000)

    await _wait_export_ready(page, track_id)
    return browser, context, page


async def _wait_export_ready(page, track_id: int) -> None:
    """等待页面就绪（前端设置 exportState='ready'）"""
    ready_deadline = time.time() + 60
    state = None
    while time.time() < ready_deadline:
        current_path = await page.evaluate("window.location.pathname")
        if not current_path.startswith(f'/tracks/{track_id}'):
            raise RuntimeError(f"导出页面跳转，当前路径: {current_path}")

        state = await page.evaluate("document.body?.dataset?.exportState || null")
        if state in ('ready', 'completed', 'failed'):
            break
        await asyncio.sleep(1)

    if state != 'ready':
        raise RuntimeError(f"导出页面未就绪（state={state or 'unknown'}）")


async def _capture_frame_mode(
    context,
    page,
    track_id: int,
    duration_ms: float,
    request: AnimationExportRequest,
    frames_dir: Path,
    progress_callback: Callable[[float], None],
    cancel_check: Optional[Callable[[], bool]] = None,
) -> None:
    """逐帧截图：每帧 seek → 等待瓦片/渲染就绪 → 截图"""
    speed = max(request.speed, 0.25)
    start_ms = max(0.0, request.start_time)
    frame_count = int(math.ceil((duration_ms - start_ms) / 1000.0 / speed * EXPORT_FPS))

    if not await page.evaluate("typeof window.__seekExportFrame === 'function'"):
        raise RuntimeError("导出页面未暴露 __seekExportFrame（回放播放器未挂载）")

    frame_deadline = time.time() + frame_count * 2.5 + 120
    for i in range(frame_count):
        if cancel_check is not None and cancel_check():
            raise RuntimeError("任务已取消")
        if time.time() > frame_deadline:
            raise RuntimeError(f"逐帧导出超时（{frame_count} 帧未在限时内完成）")
        t_ms = min(start_ms + i / EXPORT_FPS * speed * 1000, duration_ms)
        await page.evaluate("(t) => window.__seekExportFrame(t)", t_ms)
        frame_path = frames_dir / f"{i:06d}.jpg"
        await page.screenshot(path=str(frame_path), type='jpeg', quality=FRAME_JPEG_QUALITY)
        if progress_callback:
            await progress_callback(10.0 + 80.0 * (i + 1) / frame_count)

    if progress_callback:
        await progress_callback(92.0)


async def _compose_frames_with_ffmpeg(frames_dir: Path, final_path: Path) -> None:
    """逐帧目录合成 MP4（异步子进程：阻塞式调用会冻结整个事件循环，
    并发录制时其他任务与 API 请求都会被卡住）"""
    proc = await asyncio.create_subprocess_exec(
        'ffmpeg', '-y',
        '-framerate', str(EXPORT_FPS),
        '-i', str(frames_dir / '%06d.jpg'),
        '-c:v', 'libx264',
        '-crf', FFMPEG_CRF,
        '-preset', 'medium',
        '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart',
        str(final_path),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=1800)
    except asyncio.TimeoutError:
        proc.kill()
        try:
            await proc.wait()
        except Exception:
            pass
        raise RuntimeError("ffmpeg 合成超时")
    if proc.returncode != 0 or not final_path.exists():
        stderr_tail = (stderr or b'').decode(errors='ignore')[-400:]
        raise RuntimeError(f"ffmpeg 合成失败: {stderr_tail}")


async def _capture_screencast_mode(
    context,
    page,
    track_id: int,
    duration_ms: float,
    request: AnimationExportRequest,
    final_path: Path,
    width: int,
    height: int,
    progress_callback: Callable[[float], None],
    cancel_check: Optional[Callable[[], bool]] = None,
) -> None:
    """
    流式录制：页面实时播放，CDP screencast JPEG 帧直通 ffmpeg stdin
    （挂钟时间戳，不落盘中间帧），耗时 ≈ 输出时长，支持数小时输出

    瓦片预热：录制全程开启「预热页」——同一上下文中的另一份同轨迹页面，
    由后端驱动它始终定位于主录制页前方 WARM_LEAD_OUTPUT_S（输出时间）的位置：
    小步寻址不触发 Leaflet 的瓦片请求中止，沿途瓦片（含旋转扩展范围与缩放
    档位变化）提前载入浏览器缓存（瓦片 max-age 3600），主录制页请求时命中
    缓存瞬时完成。预热页异常不阻断导出（瓦片门控兜底）。
    """
    speed = max(request.speed, 0.25)
    start_ms = max(0.0, request.start_time)
    out_duration_s = max(0.0, (duration_ms - start_ms) / 1000.0 / speed)

    # 阶段二：开启预热页（进度 2-8），初始定位于主录制页前方
    warm_page = None
    try:
        warm_url = _build_export_url(track_id, request, width, height)
        warm_page = await context.new_page()
        await warm_page.goto(warm_url, wait_until='domcontentloaded', timeout=60000)
        await _wait_export_ready(warm_page, track_id)
        warm_target_ms = min(start_ms + WARM_LEAD_OUTPUT_S * speed * 1000, duration_ms)
        await warm_page.evaluate("(t) => window.__seekExportPosition(t)", warm_target_ms)
        if progress_callback:
            await progress_callback(8.0)
    except Exception as e:
        # 预热页失败不阻断导出（瓦片门控兜底）
        print(f"[playwright_export] 预热页开启失败（门控兜底）: {e}")
        warm_page = None

    ffmpeg_proc = None
    stop_frame_pump = None
    try:
        ffmpeg_proc = subprocess.Popen(
            [
                'ffmpeg', '-y',
                '-loglevel', 'error', '-nostats',  # stderr 进度输出会塞满管道缓冲导致死锁，仅保留错误
                '-f', 'mjpeg', '-use_wallclock_as_timestamps', '1',
                '-i', 'pipe:0',
                '-c:v', 'libx264', '-crf', FFMPEG_CRF, '-preset', 'superfast',
                '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
                str(final_path),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        cdp = await context.new_cdp_session(page)
        on_screencast_frame, stop_frame_pump = _start_frame_pump(cdp, ffmpeg_proc.stdin)

        cdp.on('Page.screencastFrame', on_screencast_frame)
        await cdp.send('Page.startScreencast', {
            'format': 'jpeg',
            'quality': SCREENCAST_JPEG_QUALITY,
            'maxWidth': width,
            'maxHeight': height,
            'everyNthFrame': 3,  # 头less rAF 约 60fps，降至 ~20fps 降低事件循环与编码压力
        })

        if progress_callback:
            await progress_callback(10.0)

        # 触发播放（页面 rAF 驱动；导出模式下推进会被瓦片就绪门控短暂暂停）
        await page.evaluate("window.__startExportPlayback && window.__startExportPlayback()")

        out_duration_s = (duration_ms - start_ms) / 1000.0 / speed
        timeout_s = out_duration_s * 3 + 300
        deadline = time.time() + timeout_s
        state = None
        poll_i = 0
        while time.time() < deadline:
            if cancel_check is not None and cancel_check():
                raise RuntimeError("任务已取消")

            current_path = await page.evaluate("window.location.pathname")
            if not current_path.startswith(f'/tracks/{track_id}'):
                raise RuntimeError(f"导出页面跳转，当前路径: {current_path}")

            state = await page.evaluate("document.body?.dataset?.exportState || null")
            if state in ('completed', 'failed'):
                break

            pct = 0.0
            try:
                pct = float(await page.evaluate(
                    "parseFloat(document.body?.dataset?.exportProgress || '0') || 0"
                ))
                if progress_callback:
                    await progress_callback(10.0 + pct * 0.8)
            except Exception:
                pass  # 页面暂不可读时忽略，下轮再试

            # 预热页跟随：定位到主录制页前方 WARM_LEAD_OUTPUT_S（输出时间）的位置，
            # 该处瓦片提前入缓存；小步寻址避免 Leaflet 中止在途请求。
            # 接近末端时缩小领先量紧贴主录制页（对末段做第二次覆盖，重试失败的瓦片）
            if warm_page is not None and pct > 0 and poll_i % max(1, int(WARM_FOLLOW_INTERVAL_S)) == 0:
                try:
                    out_t = out_duration_s * pct / 100.0
                    remaining_output = out_duration_s - out_t
                    lead_s = WARM_LEAD_OUTPUT_S if remaining_output > 90.0 else max(10.0, remaining_output * 0.4)
                    warm_target_ms = min(
                        start_ms + (out_t + lead_s) * speed * 1000,
                        duration_ms,
                    )
                    await warm_page.evaluate(
                        "(t) => window.__seekExportPosition && window.__seekExportPosition(t)",
                        warm_target_ms,
                    )
                except Exception:
                    pass  # 预热页异常不影响录制（门控兜底）

            poll_i += 1
            await asyncio.sleep(1)

        if state != 'completed':
            raise RuntimeError(
                f"动画导出{'失败' if state == 'failed' else '超时'}（state={state or 'unknown'}）"
            )

        # 收尾录制：关闭预热页（释放 CPU 供编码；异常时 context.close 统一兜底）
        if warm_page is not None:
            try:
                await warm_page.close()
            except Exception:
                pass
            warm_page = None

        # 停止采集，收尾编码
        await cdp.send('Page.stopScreencast')
        stop_frame_pump()
        ffmpeg_proc.stdin.close()
        # 阻塞 wait 会冻结事件循环（最长 300s），放到线程里等
        ffmpeg_returncode = await asyncio.to_thread(ffmpeg_proc.wait, timeout=300)
        if ffmpeg_returncode != 0 or not final_path.exists():
            stderr_tail = ffmpeg_proc.stderr.read().decode(errors='ignore')[-400:]
            raise RuntimeError(f"ffmpeg 流式合成失败: {stderr_tail}")

        if progress_callback:
            await progress_callback(100.0)
    except BaseException:
        # 取消/异常/超时：终止 ffmpeg 并清理管道，防止残留进程
        try:
            if stop_frame_pump is not None:
                stop_frame_pump()
        except Exception:
            pass
        if ffmpeg_proc is not None:
            try:
                if ffmpeg_proc.stdin and not ffmpeg_proc.stdin.closed:
                    ffmpeg_proc.stdin.close()
            except Exception:
                pass
            try:
                ffmpeg_proc.kill()
            except Exception:
                pass
        raise


async def _capture_impl(
    track_id: int,
    duration_ms: float,
    token: str,
    request: AnimationExportRequest,
    progress_callback: Optional[Callable[[float], None]] = None,
    task_id: str = '',
    cancel_check: Optional[Callable[[], bool]] = None,
) -> str:
    """
    导出实现（必须在支持子进程的事件循环中运行）：
    按输出时长选择逐帧截图（短）或 CDP screencast 流式录制（长）
    """
    if progress_callback is None:
        progress_callback = lambda p: None  # noqa: E731

    export_dir = Path(settings.EXPORT_DIR) / 'animation'
    export_dir.mkdir(parents=True, exist_ok=True)

    width, height = RESOLUTION_DIMENSIONS.get(request.resolution, (1920, 1080))

    speed = max(request.speed, 0.25)
    start_ms = max(0.0, request.start_time)
    out_duration_s = max(0.0, (duration_ms - start_ms) / 1000.0 / speed)
    frame_count = int(math.ceil(out_duration_s * EXPORT_FPS))
    if frame_count < 1:
        raise ValueError("导出区间时长为 0（起点已到轨迹末尾）")

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    # 文件名含 task_id 片段：同轨迹并发导出同秒启动时也不会互相覆盖
    filename = f'track_{track_id}_animation_{timestamp}_{task_id[:8]}.mp4'
    final_path = export_dir / filename
    frames_dir = export_dir / 'frames' / f'{track_id}_{task_id[:8]}'

    async with async_playwright() as p:
        browser, context, page = await _open_export_page(
            p, track_id, width, height, token, request
        )
        try:
            if progress_callback:
                await progress_callback(5.0)

            try:
                if frame_count <= FRAME_MODE_MAX_FRAMES:
                    # 短输出：逐帧截图（质量最优、瓦片确定性加载）
                    frames_dir.mkdir(parents=True, exist_ok=True)
                    await _capture_frame_mode(
                        context, page, track_id, duration_ms, request,
                        frames_dir, progress_callback, cancel_check,
                    )
                    await _compose_frames_with_ffmpeg(frames_dir, final_path)

                    if progress_callback:
                        await progress_callback(100.0)
                    # 帧目录在合成成功后清理
                    shutil.rmtree(frames_dir, ignore_errors=True)
                else:
                    # 长输出（数小时）：CDP screencast 流式录制，耗时 ≈ 输出时长
                    await _capture_screencast_mode(
                        context, page, track_id, duration_ms, request,
                        final_path, width, height, progress_callback, cancel_check,
                    )
            except BaseException as e:
                # 失败/取消不留下残缺的输出文件；取消时的逐帧目录是纯垃圾直接清掉，
                # 其他失败保留以便排查（遗留目录由保留期清理任务兜底回收）
                final_path.unlink(missing_ok=True)
                if isinstance(e, asyncio.CancelledError) or (cancel_check is not None and cancel_check()):
                    shutil.rmtree(frames_dir, ignore_errors=True)
                raise
        finally:
            # 关闭动作不能被打断（取消/关闭风暴下保证浏览器退出）
            try:
                await asyncio.shield(_close_browser_quietly(context, browser))
            except asyncio.CancelledError:
                pass

    return f'animation/{filename}'


async def _close_browser_quietly(context, browser) -> None:
    try:
        await context.close()
    except Exception:
        pass
    try:
        await browser.close()
    except Exception:
        pass
