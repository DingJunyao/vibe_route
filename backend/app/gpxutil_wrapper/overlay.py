"""
信息覆盖层生成服务
根据轨迹点数据生成带有道路编号等信息的 PNG 图片序列
"""
import os
import zipfile
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track, TrackPoint
from app.core.config import settings


@dataclass
class OverlayConfig:
    """覆盖层生成配置"""
    image_width: int = 1920
    image_height: int = 1080
    font_size: int = 48
    show_coords: bool = True
    show_elevation: bool = True
    show_road_info: bool = True
    bg_color: str = "#000000"
    text_color: str = "#FFFFFF"
    accent_color: str = "#409EFF"


class OverlayGenerator:
    """信息覆盖层生成器"""

    def __init__(self, config: Optional[OverlayConfig] = None):
        self.config = config or OverlayConfig()
        self.output_dir = settings.UPLOAD_DIR / "overlays"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _get_font(self, size: int) -> ImageFont.ImageFont:
        """获取字体，支持中文字符"""
        # 尝试使用系统字体
        font_paths = [
            # Windows 中文字体
            "C:/Windows/Fonts/msyh.ttc",  # 微软雅黑
            "C:/Windows/Fonts/simhei.ttf",  # 黑体
            "C:/Windows/Fonts/simsun.ttc",  # 宋体
            # Linux 中文字体
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            # macOS 中文字体
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Medium.ttc",
        ]

        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    return ImageFont.truetype(font_path, size)
                except Exception:
                    continue

        # 如果都找不到，使用默认字体
        return ImageFont.load_default()

    def _generate_overlay_image(self, point: TrackPoint, index: int, total: int) -> Image.Image:
        """为单个轨迹点生成覆盖层图片"""
        # 创建图片
        img = Image.new('RGB', (self.config.image_width, self.config.image_height),
                        color=self.config.bg_color)
        draw = ImageDraw.Draw(img)

        # 字体
        title_font = self._get_font(int(self.config.font_size * 1.5))
        font = self._get_font(self.config.font_size)
        small_font = self._get_font(int(self.config.font_size * 0.7))

        # 进度标识
        progress_text = f"{index + 1} / {total}"
        draw.text((self.config.image_width - 200, 30), progress_text,
                 fill=self.config.text_color, font=small_font, anchor="ra")

        # 标题区域 - 道路信息
        y_offset = 80

        if point.road_number:
            # 道路编号大标题
            draw.text((100, y_offset), point.road_number,
                     fill=self.config.accent_color, font=title_font, anchor="la")
            y_offset += 80

        if point.road_name:
            # 道路名称
            draw.text((100, y_offset), point.road_name,
                     fill=self.config.text_color, font=font, anchor="la")
            y_offset += 70

        # 行政区划
        location_parts = []
        if point.province:
            location_parts.append(point.province)
        if point.city and point.city != point.province:
            location_parts.append(point.city)
        if point.district:
            location_parts.append(point.district)

        if location_parts:
            location_text = " · ".join(location_parts)
            draw.text((100, y_offset), location_text,
                     fill="#AAAAAA", font=small_font, anchor="la")
            y_offset += 60

        # 坐标信息
        if self.config.show_coords:
            coord_text = f"WGS84: {point.latitude_wgs84:.6f}, {point.longitude_wgs84:.6f}"
            draw.text((100, self.config.image_height - 150), coord_text,
                     fill=self.config.text_color, font=small_font, anchor="la")

        # 海拔信息
        if self.config.show_elevation and point.elevation is not None:
            elev_text = f"海拔: {point.elevation:.1f} m"
            draw.text((100, self.config.image_height - 100), elev_text,
                     fill=self.config.text_color, font=small_font, anchor="la")

        # 时间信息
        if point.time:
            time_text = f"时间: {point.time.strftime('%Y-%m-%d %H:%M:%S')}"
            draw.text((100, self.config.image_height - 50), time_text,
                     fill="#AAAAAA", font=small_font, anchor="la")

        # 装饰线
        draw.line([(50, y_offset + 20), (self.config.image_width - 50, y_offset + 20)],
                 fill="#333333", width=2)

        return img

    async def generate(
        self,
        db: AsyncSession,
        track_id: int,
        user_id: int
    ) -> tuple[str, int]:
        """
        生成覆盖层图片序列并打包为 ZIP

        Returns:
            (zip_file_path, image_count)
        """
        # 查询轨迹点
        result = await db.execute(
            TrackPoint.__table__.select()
            .where(TrackPoint.track_id == track_id)
            .order_by(TrackPoint.point_index)
        )
        points = result.scalars().all()

        if not points:
            raise ValueError("轨迹点数据不存在")

        # 创建 ZIP 文件
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        zip_filename = f"track_{track_id}_overlay_{timestamp}.zip"
        zip_path = self.output_dir / zip_filename

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for i, point in enumerate(points):
                # 生成图片
                img = self._generate_overlay_image(point, i, len(points))

                # 保存到内存
                img_filename = f"frame_{i:05d}.png"
                img_bytes = BytesIO()
                img.save(img_bytes, format='PNG')
                img_bytes.seek(0)

                # 添加到 ZIP
                zipf.writestr(img_filename, img_bytes.getvalue())

        return str(zip_path), len(points)


# 导入 BytesIO
from io import BytesIO
