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
                        headless=False,
                        slow_mo=1000,
                        args=[
                            '--no-sandbox',
                            '--disable-setuid-sandbox',
                            '--disable-dev-shm-usage',
                            '--disable-web-security',
                            '--allow-file-access-from-files',
                            '--allow-running-insecure-content',
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
        """
        browser = self.get_browser()
        if not browser:
            raise Exception("浏览器未可用，请确保 Playwright 已正确安装")

        # 计算 CSS 缩放后的 viewport 大小
        # TrackMapOnly.vue 使用 transform: scale(mapScale/100) 缩放
        # 需要相应增大 viewport，否则截图会只捕获缩放后的一小部分
        scale_factor = map_scale / 100
        adjusted_width = int(width * scale_factor)
        adjusted_height = int(height * scale_factor)
        logger.info(f"原始尺寸: {width}x{height}, CSS scale: {map_scale}%, 调整后 viewport: {adjusted_width}x{adjusted_height}")

        # 创建浏览器上下文（设置视口大小和设备像素比，确保截图清晰）
        # 使用 device_scale_factor=2 保证截图清晰度，同时避免内存占用过大
        context = browser.new_context(
            viewport={'width': adjusted_width, 'height': adjusted_height, 'device_scale_factor': 2}
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

            page.goto(url, wait_until='networkidle', timeout=30000)
            logger.info("页面加载完成")

            # 等待地图准备就绪（前端设置 window.mapReady = true）
            try:
                page.wait_for_function("window.mapReady === true", timeout=15000)
                logger.info("地图准备就绪")
            except Exception as e:
                logger.warning(f"等待地图准备就绪超时: {e}")

            # 额外等待地图渲染完成
            page.wait_for_timeout(2000)

            # 打印控制台消息
            if console_messages:
                logger.info(f"浏览器控制台消息: {console_messages}")

            # 查找地图容器（专用页面使用 .map-only-page）
            map_element = page.query_selector('.map-only-page')
            if map_element:
                # 截取整个地图容器（已经是全屏）
                screenshot = map_element.screenshot(type='png')
                logger.info(f"地图容器截图成功: {len(screenshot)} bytes")
                return screenshot
            else:
                # 降级：截取整个页面
                screenshot = page.screenshot(full_page=False, type='png')
                logger.info(f"整页截图: {len(screenshot)} bytes")
                return screenshot

        except Exception as e:
            logger.error(f"地图截图生成失败: {e}")
            raise
        finally:
            page.close()


# 全局服务实例
poster_service = PosterService()
