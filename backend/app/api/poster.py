"""
海报生成 API - 使用 Playwright 截取地图
"""

import asyncio
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from PIL import Image, ImageDraw, ImageFont
import io
from typing import Optional, List
from datetime import datetime

from app.core.deps import get_current_user
from app.core.database import get_db
from app.core.config import settings
from app.models.user import User
from app.services.config_service import config_service
from app.services.poster_service import poster_service
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

router = APIRouter()


class PosterConfig(BaseModel):
    """海报配置"""
    template: str = Field(default="minimal", description="模板类型: minimal, simple, rich, geo")
    width: int = Field(default=1920, description="海报宽度")
    height: int = Field(default=1080, description="海报高度")
    show_watermark: bool = Field(default=True, description="是否显示水印")
    map_scale: int = Field(default=100, description="地图缩放百分比，100-200")


class TrackData(BaseModel):
    """轨迹数据"""
    track_id: int = Field(..., description="轨迹 ID，用于访问地图专用页面")
    name: str = Field(..., description="轨迹名称")
    points: List[dict] = Field(..., description="轨迹点列表")
    distance: float = Field(default=0, description="距离（米）")
    duration: int = Field(default=0, description="时长（秒）")
    elevation_gain: float = Field(default=0, description="爬升（米）")
    elevation_loss: float = Field(default=0, description="下降（米）")
    start_time: Optional[str] = Field(default=None, description="开始时间")
    end_time: Optional[str] = Field(default=None, description="结束时间")


class MapBounds(BaseModel):
    """地图边界"""
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float


def format_distance(meters: float) -> str:
    """格式化距离"""
    if meters >= 1000:
        return f"{meters / 1000:.2f} km"
    return f"{int(meters)} m"


def format_duration(seconds: int) -> str:
    """格式化时长"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def format_elevation(meters: float) -> str:
    """格式化海拔"""
    if meters >= 1000:
        return f"{meters / 1000:.1f} km"
    return f"{int(meters)} m"


def get_bounds_center(bounds: MapBounds) -> tuple[float, float]:
    """获取边界中心点"""
    center_lat = (bounds.min_lat + bounds.max_lat) / 2
    center_lon = (bounds.min_lon + bounds.max_lon) / 2
    return center_lat, center_lon


def calculate_zoom(bounds: MapBounds, width: int, height: int) -> int:
    """计算缩放级别"""
    lat_diff = bounds.max_lat - bounds.min_lat
    lon_diff = bounds.max_lon - bounds.min_lon

    for zoom in range(3, 19):
        lat_coverage = 180 / (2 ** zoom)
        lon_coverage = 360 / (2 ** zoom)

        if lat_diff < lat_coverage * 0.8 and lon_diff < lon_coverage * 0.8:
            return zoom

    return 12


async def get_map_config(db: AsyncSession, provider: str) -> tuple[str, str | None]:
    """获取地图配置 (api_key, security_code)"""
    # OSM 不需要 API Key
    if provider == 'osm':
        return '', None

    config = await config_service.get_all_configs(db)
    map_layers = config.get("map_layers", {})

    layer = map_layers.get(provider)
    if not layer:
        raise HTTPException(status_code=400, detail=f"未配置 {provider} 地图")

    # 天地图使用 tk
    if provider == 'tianditu':
        tk = layer.get("tk")
        if not tk:
            raise HTTPException(status_code=400, detail="天地图 tk 未配置")
        return tk, None

    api_key = layer.get("api_key") or layer.get("ak")
    if not api_key:
        raise HTTPException(status_code=400, detail=f"{provider} API Key 未配置")

    security_code = layer.get("security_js_code") or layer.get("js_code") or layer.get("tk")

    return api_key, security_code


@router.get("/providers")
async def get_providers(db: AsyncSession = Depends(get_db)):
    """获取可用的海报生成地图提供商"""
    config = await config_service.get_all_configs(db)
    map_layers = config.get("map_layers", {})

    providers = []
    for layer_id, layer in map_layers.items():
        if layer_id in ['amap', 'baidu', 'tencent', 'osm', 'tianditu']:
            # 检查必需的密钥
            if layer_id == 'osm':
                # OSM 不需要密钥
                pass
            elif layer_id == 'tianditu':
                # 天地图需要 tk
                if not layer.get("tk"):
                    continue
            else:
                # 其他地图需要 api_key 或 ak
                if not layer.get("api_key") and not layer.get("ak"):
                    continue

            providers.append({
                "id": layer_id,
                "name": layer.get("name", layer_id),
                "enabled": layer.get("enabled", True)
            })

    return {"providers": providers}


@router.post("/generate")
async def generate_poster(
    config: PosterConfig,
    track: TrackData,
    bounds: MapBounds,
    provider: str = "amap",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    服务器端生成海报

    使用 Playwright 截取 JS API 渲染的地图
    """

    try:
        logger.info(f"开始生成海报: provider={provider}, template={config.template}, size={config.width}x{config.height}")

        # 获取地图配置
        api_key, security_code = await get_map_config(db, provider)
        logger.info(f"地图 API Key: {api_key[:10]}...")

        # 计算中心和缩放级别
        center_lat, center_lon = get_bounds_center(bounds)
        zoom = calculate_zoom(bounds, config.width, config.height)
        logger.info(f"中心点: ({center_lat}, {center_lon}), 缩放级别: {zoom}")

        # 使用 Playwright 访问专用地图页面并截图（在线程池中运行同步函数）
        logger.info("正在使用 Playwright 访问地图专用页面并截图...")

        # 获取 poster secret（从环境变量或使用默认值）
        poster_secret = getattr(settings, 'POSTER_SECRET', 'vibe-route-poster-secret')

        # 从请求数据中获取 track_id（前端已传递）
        track_id = track.track_id if hasattr(track, 'track_id') else (
            track.points[0].get('id', 1) if track.points else 1
        )

        map_image_bytes = await asyncio.to_thread(
            poster_service.generate_map_image,
            provider=provider,
            api_key=api_key,
            security_code=security_code,
            track_id=track_id,
            track_name=track.name,
            base_url="http://localhost:5173",
            poster_secret=poster_secret,
            map_scale=config.map_scale,
            width=config.width,
            height=config.height
        )

        # 加载地图图片
        map_image = Image.open(io.BytesIO(map_image_bytes))
        logger.info(f"地图图片加载成功: {map_image.size}")

        # 创建输出画布
        canvas = Image.new('RGB', (config.width, config.height), (245, 245, 245))

        # 绘制地图（居中）
        map_x = (config.width - map_image.width) // 2
        map_y = (config.height - map_image.height) // 2
        canvas.paste(map_image, (map_x, map_y))

        # 根据模板添加信息
        if config.template != "minimal":
            draw = ImageDraw.Draw(canvas)

            # 尝试加载字体
            try:
                font_large = ImageFont.truetype("msyh.ttc", 48)
                font_medium = ImageFont.truetype("msyh.ttc", 32)
                font_small = ImageFont.truetype("msyh.ttc", 24)
            except:
                font_large = ImageFont.load_default()
                font_medium = ImageFont.load_default()
                font_small = ImageFont.load_default()

            # 绘制半透明背景框
            if config.template in ("simple", "rich"):
                overlay_y = config.height - 200
                overlay = Image.new('RGBA', (config.width, 200), (30, 30, 30, 200))
                canvas.paste(overlay, (0, overlay_y), overlay)

                # 绘制轨迹名称
                draw.text((30, overlay_y + 20), track.name, fill=(255, 255, 255), font=font_large)

                # 绘制统计信息
                info_y = overlay_y + 80
                info_x = 30
                line_height = 40

                if track.distance > 0:
                    draw.text((info_x, info_y), f"距离: {format_distance(track.distance)}", fill=(255, 255, 255), font=font_medium)
                    info_y += line_height

                if track.duration > 0:
                    draw.text((info_x, info_y), f"时长: {format_duration(track.duration)}", fill=(255, 255, 255), font=font_medium)
                    info_y += line_height

                if track.elevation_gain > 0:
                    draw.text((info_x, info_y), f"爬升: {format_elevation(track.elevation_gain)}", fill=(255, 255, 255), font=font_small)

            elif config.template == "geo":
                # 地理模板 - 右下角信息
                overlay_width = 400
                overlay_height = 180
                overlay = Image.new('RGBA', (overlay_width, overlay_height), (30, 30, 30, 220))
                canvas.paste(overlay, (config.width - overlay_width, config.height - overlay_height), overlay)

                info_x = config.width - overlay_width + 20
                info_y = config.height - overlay_height + 20

                draw.text((info_x, info_y), track.name, fill=(255, 255, 255), font=font_medium)
                info_y += 50

                draw.text((info_x, info_y), f"{format_distance(track.distance)} · {format_duration(track.duration)}", fill=(200, 200, 200), font=font_small)

        # 水印
        if config.show_watermark:
            draw = ImageDraw.Draw(canvas)
            try:
                font_watermark = ImageFont.truetype("msyh.ttc", 20)
            except:
                font_watermark = ImageFont.load_default()

            watermark_text = "Vibe Route"
            bbox = draw.textbbox((0, 0), watermark_text, font=font_watermark)
            text_width = bbox[2] - bbox[0]

            draw.text((config.width - text_width - 20, config.height - 40), watermark_text, fill=(150, 150, 150), font=font_watermark)

        # 输出图片
        output = io.BytesIO()
        canvas.save(output, format='PNG')
        output.seek(0)

        logger.info("海报生成完成")
        return StreamingResponse(output, media_type="image/png")

    except Exception as e:
        logger.error(f"海报生成失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"海报生成失败: {str(e)}")
