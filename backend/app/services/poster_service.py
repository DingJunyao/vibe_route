"""
海报生成服务 - 使用 Playwright 截取地图（同步版本，解决 Windows 子进程问题）
"""

import threading
from typing import Optional, Tuple
from loguru import logger

try:
    from playwright.sync_api import sync_playwright, Browser
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright 未安装，服务器端海报生成功能不可用")


class PosterService:
    """海报生成服务（同步版本）"""

    def __init__(self):
        self._browser: Optional[Browser] = None
        self._lock = threading.Lock()
        self._playwright = None

    def get_browser(self) -> Optional[Browser]:
        """获取浏览器实例（线程安全）"""
        if not PLAYWRIGHT_AVAILABLE:
            return None

        with self._lock:
            if self._browser is None:
                try:
                    self._playwright = sync_playwright().start()
                    self._browser = self._playwright.chromium.launch(
                        headless=True,
                        slow_mo=1000,
                        args=[
                            '--no-sandbox',
                            '--disable-setuid-sandbox',
                            '--disable-dev-shm-usage',
                            '--disable-web-security',
                            '--allow-file-access-from-files',
                            '--allow-running-insecure-content',
                            # 启用 WebGL 和硬件加速，支持百度地图 GL 版本
                            '--enable-gpu',
                            '--enable-zero-copy',
                            '--ignore-gpu-blocklist',
                            '--use-angle=default',
                        ],
                        ignore_default_args=['--enable-automation']
                    )
                    logger.info("Playwright 浏览器启动成功")
                except Exception as e:
                    logger.error(f"Playwright 浏览器启动失败: {e}")
                    return None

            return self._browser

    def close(self):
        """关闭浏览器"""
        with self._lock:
            if self._browser:
                self._browser.close()
                self._browser = None
            if self._playwright:
                self._playwright.stop()
                self._playwright = None

    def generate_map_image(
        self,
        provider: str,
        api_key: str,
        security_code: Optional[str],
        track_id: int,
        track_name: str = "",
        base_url: str = "http://localhost:5173",  # 开发环境前端地址
        poster_secret: str = "vibe-route-poster-secret",  # 海报生成密钥
        map_scale: int = 100,  # 地图缩放百分比
        center: Optional[Tuple[float, float]] = None,  # (lon, lat) - 保留兼容性
        zoom: int = 12,
        width: int = 1920,
        height: int = 1080,
        points: Optional[list] = None
    ) -> Optional[bytes]:
        """
        生成地图图片（同步方法）

        访问专用的地图截图页面 /tracks/{id}/map-only

        Args:
            provider: 地图提供商 (amap, baidu, tencent, osm, tianditu)
            track_id: 轨迹 ID
            base_url: 前端基础 URL
            poster_secret: 海报生成密钥，用于验证公开 API 访问
            map_scale: 地图缩放百分比（100-200）

        Note:
            百度地图 (baidu) 会自动转换为 Legacy 版本 (baidu_legacy) 以避免 WebGL 兼容性问题
        """
        # 百度地图统一使用 Legacy 版本（非 WebGL，避免截图问题）
        if provider == 'baidu':
            provider = 'baidu_legacy'
            logger.info("百度地图自动转换为 Legacy 版本用于海报生成")
        browser = self.get_browser()
        if not browser:
            raise Exception("浏览器未可用，请确保 Playwright 已正确安装")

        # 使用原始尺寸作为 viewport，让 CSS transform scale 作用在正确的基础上
        logger.info(f"原始尺寸: {width}x{height}, CSS scale: {map_scale}%")

        # 创建浏览器上下文（使用原始 viewport 大小）
        context = browser.new_context(
            viewport={'width': width, 'height': height, 'device_scale_factor': 3}
        )

        # 创建页面
        page = context.new_page()

        # 收集控制台日志
        console_messages = []
        def handle_console(msg):
            msg_text = f"[{msg.type}] {msg.text}"
            console_messages.append(msg_text)
            logger.debug(f"浏览器控制台: {msg_text}")

        page.on('console', handle_console)

        try:
            # 访问专用地图页面（带 provider、secret 和 map_scale 参数）
            url = f"{base_url}/tracks/{track_id}/map-only?provider={provider}&secret={poster_secret}&map_scale={map_scale}"
            logger.info(f"访问地图专用页面: {url}")

            page.goto(url, wait_until='domcontentloaded', timeout=30000)
            logger.info("页面 DOM 加载完成")

            # 对于百度地图，需要额外等待确保脚本加载
            if provider in ['baidu', 'baidu_legacy']:
                page.wait_for_timeout(5000)
                # 检查百度地图是否加载成功
                # baidu (GL 版本) 检查 BMapGL，baidu_legacy (非 WebGL) 检查 BMap
                if provider == 'baidu_legacy':
                    bmap_loaded = page.evaluate("!!(window.BMap && window.BMap.Map)")
                    logger.info(f"百度地图 Legacy API 加载状态: {bmap_loaded}")
                else:
                    bmap_loaded = page.evaluate("!!(window.BMapGL && window.BMapGL.Map)")
                    logger.info(f"百度地图 GL API 加载状态: {bmap_loaded}")
                if not bmap_loaded:
                    raise Exception(f"百度地图 API ({provider}) 加载失败")

            page.wait_for_load_state('networkidle', timeout=30000)
            logger.info("页面完全加载完成")

            # 等待地图准备就绪（前端设置 window.mapReady = true）
            try:
                page.wait_for_function("window.mapReady === true", timeout=15000)
                logger.info("地图准备就绪")
            except Exception as e:
                logger.warning(f"等待地图准备就绪超时: {e}")

            # 额外等待地图渲染完成
            # 百度地图 GL 版本和高德地图使用 WebGL，需要更长等待时间
            # baidu_legacy 是非 WebGL 版本，等待时间与其他地图相同
            is_webgl_map = provider in ['baidu', 'amap']
            base_wait = 5000 if is_webgl_map else 2000  # WebGL 地图需要更长等待
            scale_wait = (map_scale - 100) * (80 if is_webgl_map else 50)
            total_wait = base_wait + scale_wait
            logger.info(f"等待缩放完成: {total_wait}ms (scale: {map_scale}%, webgl: {is_webgl_map})")
            page.wait_for_timeout(total_wait)

            # 等待底图瓦片加载完成
            if provider == 'baidu':
                page.wait_for_timeout(5000)
                logger.info("等待百度地图底图瓦片加载完成")
            elif provider == 'baidu_legacy':
                page.wait_for_timeout(3000)
                logger.info("等待百度地图 Legacy 底图瓦片加载完成")
            elif provider == 'amap':
                page.wait_for_timeout(3000)
                logger.info("等待高德地图地名图层加载完成")

            # 打印控制台消息
            if console_messages:
                logger.info(f"浏览器控制台消息: {console_messages}")

            # 计算缩放后的截图尺寸
            scale_factor = map_scale / 100
            clip_width = int(width * scale_factor)
            clip_height = int(height * scale_factor)

            # 截取整个页面（CSS scale 会超出 viewport，使用 clip 指定区域）
            screenshot = page.screenshot(
                type='png',
                clip={'x': 0, 'y': 0, 'width': clip_width, 'height': clip_height}
            )
            logger.info(f"地图截图成功: {len(screenshot)} bytes, 尺寸: {clip_width}x{clip_height}")
            return screenshot

        except Exception as e:
            logger.error(f"地图截图生成失败: {e}")
            raise
        finally:
            page.close()


# 全局服务实例
poster_service = PosterService()
