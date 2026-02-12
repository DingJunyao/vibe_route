"""
覆盖层渲染引擎
基于模板配置生成覆盖层图片
"""
import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import TrackPoint
from app.models.overlay_template import Font
from app.core.config import settings
from app.schemas.overlay_template import (
    OverlayTemplateConfig,
    OverlayElement,
    PositionConfig,
    SizeConfig,
    ContentConfig,
    TextLayoutConfig,
    StyleConfig,
    SafeAreaConfig,
    BackgroundConfig,
)


class OverlayRenderer:
    """
    覆盖层渲染引擎

    支持基于百分比配置的任意分辨率渲染
    """

    # 系统字体路径映射
    SYSTEM_FONTS = {
        'system_msyh': {
            'name': '微软雅黑',
            'paths': [
                "C:/Windows/Fonts/msyh.ttc",
                "C:/Windows/Fonts/msyhbd.ttc",
                "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
                "/System/Library/Fonts/PingFang.ttc",
            ]
        },
        'system_simhei': {
            'name': '黑体',
            'paths': [
                "C:/Windows/Fonts/simhei.ttf",
                "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
                "/System/Library/Fonts/STHeiti Medium.ttc",
            ]
        },
        'system_simsun': {
            'name': '宋体',
            'paths': [
                "C:/Windows/Fonts/simsun.ttc",
                "/System/Library/Fonts/STSong Light.ttc",
            ]
        },
        'system_arial': {
            'name': 'Arial',
            'paths': [
                "C:/Windows/Fonts/arial.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
            ]
        },
        'system_times': {
            'name': 'Times New Roman',
            'paths': [
                "C:/Windows/Fonts/times.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
                "/System/Library/Fonts/Times.ttc",
            ]
        },
        'system_courier': {
            'name': 'Courier New',
            'paths': [
                "C:/Windows/Fonts/cour.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
                "/System/Library/Fonts/Courier.dfont",
            ]
        },
    }

    # 锚点位置映射（相对于容器/元素）
    ANCHOR_POSITIONS = {
        'top-left': (0.0, 0.0),
        'top': (0.5, 0.0),
        'top-right': (1.0, 0.0),
        'left': (0.0, 0.5),
        'center': (0.5, 0.5),
        'right': (1.0, 0.5),
        'bottom-left': (0.0, 1.0),
        'bottom': (0.5, 1.0),
        'bottom-right': (1.0, 1.0),
    }

    # PIL 锚点映射
    PIL_ANCHORS = {
        ('left', 'top'): 'la',
        ('center', 'top'): 'ma',
        ('right', 'top'): 'ra',
        ('left', 'middle'): 'lm',
        ('center', 'middle'): 'mm',
        ('right', 'middle'): 'rm',
        ('left', 'bottom'): 'ld',
        ('center', 'bottom'): 'md',
        ('right', 'bottom'): 'rd',
    }

    def __init__(
        self,
        template_config: OverlayTemplateConfig,
        output_resolution: tuple = (1920, 1080),
        fonts: Optional[Dict[str, Font]] = None
    ):
        """
        初始化渲染器

        Args:
            template_config: 模板配置
            output_resolution: 输出分辨率 (width, height)
            fonts: 字体字典 {font_id: Font}
        """
        self.config = template_config
        self.output_width, self.output_height = output_resolution
        self.fonts = fonts or {}
        self._font_cache = {}

        # 获取安全区配置
        safe_area = self.config.safe_area or SafeAreaConfig()
        self.safe_area = safe_area

    def render(self, point_data: TrackPoint) -> Image.Image:
        """
        渲染单个覆盖层帧

        Args:
            point_data: 轨迹点数据

        Returns:
            PIL Image 对象
        """
        # 创建画布（RGBA 支持透明）
        img = Image.new('RGBA', (self.output_width, self.output_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # 绘制背景（如果配置了）
        if self.config.background:
            self._draw_background(img, draw)

        # 按顺序渲染元素
        for element in (self.config.elements or []):
            if self._is_visible(element, point_data):
                self._render_element(img, draw, element, point_data)

        return img

    def _draw_background(self, img: Image, draw: ImageDraw):
        """绘制背景"""
        bg_config = self.config.background
        if not bg_config or bg_config.opacity <= 0:
            return

        # 解析颜色
        color = self._parse_color(bg_config.color)

        # 应用不透明度
        if bg_config.opacity < 1:
            # RGBA 格式
            if len(color) == 3:
                color = (*color, int(255 * bg_config.opacity))
            else:
                color = (*color[:3], int(color[3] * bg_config.opacity))

        # 绘制矩形
        draw.rectangle(
            [(0, 0), (self.output_width, self.output_height)],
            fill=color
        )

    def _is_visible(self, element: OverlayElement, point_data: TrackPoint) -> bool:
        """判断元素是否可见"""
        visible = element.visible

        # 如果 visible 是字符串，检查数据源字段
        if isinstance(visible, str):
            value = self._get_value(point_data, visible)
            return bool(value)

        # 如果是 boolean，直接返回
        if isinstance(visible, bool):
            return visible

        return True

    def _render_element(
        self,
        img: Image,
        draw: ImageDraw,
        element: OverlayElement,
        point_data: TrackPoint
    ):
        """渲染单个元素"""
        element_type = element.type

        if element_type == 'text':
            self._render_text_element(img, draw, element, point_data)
        elif element_type == 'group':
            self._render_group_element(img, draw, element, point_data)
        # TODO: 支持 road_sign, icon 类型

    def _render_text_element(
        self,
        img: Image,
        draw: ImageDraw,
        element: OverlayElement,
        point_data: TrackPoint
    ):
        """渲染文本元素"""
        style = element.style or StyleConfig()
        layout = element.layout or TextLayoutConfig()
        content = element.content or ContentConfig()

        # 获取文本内容
        text = self._format_text(point_data, content)
        if not text:
            return

        # 获取字体
        font_id = style.font_family or 'system_msyh'
        font_size = int(self.output_height * style.font_size)
        font = self._get_font(font_id, font_size)

        # 计算文本尺寸
        text_width, text_height = self._calculate_text_size(
            text, font, layout, style
        )

        # 计算位置
        x, y = self._calculate_position(element, (text_width, text_height))

        # 处理背景色
        if style.background_color:
            bg_color = self._parse_color(style.background_color)
            padding = style.padding or 0
            draw.rectangle(
                [
                    (x - padding, y - padding),
                    (x + text_width + padding, y + text_height + padding)
                ],
                fill=bg_color
            )

        # 绘制文本
        if layout.wrap and layout.max_lines:
            lines = self._wrap_text(text, text_width, font, layout.max_lines)
            self._draw_text_lines(draw, lines, x, y, text_width, font, layout, style.color)
        else:
            # 单行文本
            anchor = self._get_pil_anchor(layout.horizontal_align, layout.vertical_align)
            draw.text((x, y), text, font=font, fill=style.color, anchor=anchor)

    def _render_group_element(
        self,
        img: Image,
        draw: ImageDraw,
        element: OverlayElement,
        point_data: TrackPoint
    ):
        """渲染组元素（递归渲染子元素）"""
        for child in (element.children or []):
            if self._is_visible(child, point_data):
                self._render_element(img, draw, child, point_data)

    def _calculate_position(
        self,
        element: OverlayElement,
        element_size: tuple
    ) -> tuple:
        """
        计算元素的实际位置（左上角坐标）

        Args:
            element: 元素配置
            element_size: 元素尺寸 (width, height)

        Returns:
            (x, y) 元素左上角坐标
        """
        elem_width, elem_height = element_size
        pos_config = element.position or PositionConfig()

        # 获取容器锚点坐标
        container_x, container_y = self._get_container_anchor(
            pos_config.container_anchor,
            pos_config.use_safe_area
        )

        # 获取元素锚点偏移
        elem_anchor_x, elem_anchor_y = self._get_element_anchor(
            pos_config.element_anchor,
            elem_width,
            elem_height
        )

        # 计算偏移（百分比转像素）
        offset_x = self.output_width * pos_config.x
        offset_y = self.output_height * pos_config.y

        # 最终位置（元素左上角）
        final_x = container_x + offset_x - elem_anchor_x
        final_y = container_y + offset_y - elem_anchor_y

        return final_x, final_y

    def _get_container_anchor(
        self,
        anchor: str,
        use_safe_area: bool
    ) -> tuple:
        """
        获取容器锚点的像素坐标

        Args:
            anchor: 锚点类型
            use_safe_area: 是否使用安全区

        Returns:
            (x, y) 锚点坐标
        """
        w, h = self.output_width, self.output_height

        if use_safe_area:
            left = w * self.safe_area.left
            right = w * (1 - self.safe_area.right)
            top = h * self.safe_area.top
            bottom = h * (1 - self.safe_area.bottom)
        else:
            left, right = 0, w
            top, bottom = 0, h

        # 根据锚点类型计算位置
        anchor_ratio = self.ANCHOR_POSITIONS.get(anchor, (0, 0))

        x = left + (right - left) * anchor_ratio[0]
        y = top + (bottom - top) * anchor_ratio[1]

        return x, y

    def _get_element_anchor(
        self,
        anchor: str,
        width: float,
        height: float
    ) -> tuple:
        """
        获取元素锚点相对于元素左上角的偏移

        Args:
            anchor: 锚点类型
            width: 元素宽度
            height: 元素高度

        Returns:
            (offset_x, offset_y) 锚点偏移
        """
        anchor_ratio = self.ANCHOR_POSITIONS.get(anchor, (0, 0))
        return width * anchor_ratio[0], height * anchor_ratio[1]

    def _calculate_text_size(
        self,
        text: str,
        font: ImageFont,
        layout: TextLayoutConfig,
        style: StyleConfig
    ) -> tuple:
        """
        计算文本尺寸

        Args:
            text: 文本内容
            font: 字体对象
            layout: 布局配置
            style: 样式配置

        Returns:
            (width, height) 文本尺寸
        """
        # 获取自然尺寸
        bbox = font.getbbox(text)
        natural_width = bbox[2] - bbox[0]
        natural_height = -bbox[1]  # 字体高度

        # 计算宽度
        if layout.width:
            text_width = int(self.output_width * layout.width)
        elif layout.max_width:
            text_width = min(
                natural_width,
                int(self.output_width * layout.max_width)
            )
        else:
            text_width = natural_width

        # 计算高度
        if layout.height:
            text_height = int(self.output_height * layout.height)
        else:
            text_height = int(natural_height * layout.line_height)

        # 如果折行，计算多行高度
        if layout.wrap and text_width < natural_width:
            lines = self._wrap_text(text, text_width, font, layout.max_lines)
            text_height = len(lines) * int(natural_height * layout.line_height)

        return text_width, text_height

    def _wrap_text(
        self,
        text: str,
        max_width: float,
        font: ImageFont,
        max_lines: Optional[int]
    ) -> List[str]:
        """
        文本折行

        Args:
            text: 文本内容
            max_width: 最大宽度（像素）
            font: 字体对象
            max_lines: 最大行数

        Returns:
            折行后的文本列表
        """
        if not text:
            return []

        lines = []
        current_line = []

        for char in text:
            test_line = ''.join(current_line + [char])
            bbox = font.getbbox(test_line)
            if bbox[2] - bbox[0] <= max_width:
                current_line.append(char)
            else:
                if current_line:
                    lines.append(''.join(current_line))
                current_line = [char]

        if current_line:
            lines.append(''.join(current_line))

        # 处理最大行数限制
        if max_lines and len(lines) > max_lines:
            lines = lines[:max_lines]
            if max_lines > 0:
                # 添加省略号
                last_line = lines[-1]
                if len(last_line) > 3:
                    lines[-1] = last_line[:-3] + '...'

        return lines

    def _draw_text_lines(
        self,
        draw: ImageDraw,
        lines: List[str],
        x: float,
        y: float,
        width: float,
        font: ImageFont,
        layout: TextLayoutConfig,
        color: str
    ):
        """绘制多行文本"""
        line_height = int(font.size * layout.line_height)

        for i, line in enumerate(lines):
            line_y = y + i * line_height

            # 水平对齐
            anchor = self._get_pil_anchor(layout.horizontal_align, 'top')

            # 两端对齐处理
            if layout.horizontal_align == 'justify' and i < len(lines) - 1:
                self._draw_justified_text(draw, line, x, line_y, width, font, color)
            else:
                draw.text((x, line_y), line, font=font, fill=color, anchor=anchor)

    def _draw_justified_text(
        self,
        draw: ImageDraw,
        text: str,
        x: float,
        y: float,
        width: float,
        font: ImageFont,
        color: str
    ):
        """绘制两端对齐文本（简单实现，通过调整字符间距）"""
        # 简单实现：使用左对齐
        # TODO: 实现真正的两端对齐（需要计算字符宽度并分布间距）
        draw.text((x, y), text, font=font, fill=color, anchor='la')

    def _format_text(self, point_data: TrackPoint, content: ContentConfig) -> str:
        """根据数据源格式化文本"""
        # 如果有自定义示例文本，直接使用
        if content.sample_text:
            # 使用 format 字段格式化示例文本
            format_str = content.format or '{}'
            try:
                return format_str.format(content.sample_text)
            except:
                return content.sample_text

        source = content.source
        if not source:
            return ''

        # 获取原始值
        value = self._get_value(point_data, source)
        if value is None:
            return ''

        # 应用小数位数格式化（数字类型）
        if content.decimal_places is not None and isinstance(value, (int, float)):
            value = round(value, content.decimal_places)

        # 应用格式化字符串
        format_str = content.format or '{}'
        try:
            formatted = format_str.format(value)
        except:
            formatted = str(value)

        return formatted

    def _get_value(self, point_data: TrackPoint, source: str):
        """从数据源获取值"""
        # 直辖市列表（这些城市的 province 和 city 相同）
        DIRECT_CITIES = {'北京市', '上海市', '天津市', '重庆市'}

        # 中文区域组合（例：河南省 三门峡市 湖滨区）
        def get_region() -> str:
            """获取组合的中文区域信息"""
            parts = []
            province = point_data.province or ''
            city = point_data.city or ''
            district = point_data.district or ''

            if province:
                parts.append(province)
            # 直辖市时，city 与 province 相同，不重复添加
            if city and city not in DIRECT_CITIES:
                parts.append(city)
            if district:
                parts.append(district)

            return ' '.join(parts)

        # 英文区域组合（例：Hubin District, Sanmenxia City, Henan Province）
        def get_region_en() -> str:
            """获取组合的英文区域信息"""
            parts = []
            province = point_data.province or ''
            city = point_data.city or ''
            district = point_data.district or ''
            province_en = point_data.province_en or ''
            city_en = point_data.city_en or ''
            district_en = point_data.district_en or ''

            # 省辖县级行政单位（如济源市、仙桃市等）
            is_province_administered = (
                city and province and city != province and
                not district_en and not district_en.endswith(' District')
            )

            if district:
                district_text = district_en
                # 如果已经有后缀则不添加
                if district_text and not any(
                    district_text.endswith(suffix)
                    for suffix in [' District', ' City', ' County', ' Prefecture']
                ):
                    district_text += ' District'
                parts.append(district_text)

            if city and city != province:
                city_text = city_en
                if city_text and not any(
                    city_text.endswith(suffix)
                    for suffix in [' City', ' Prefecture', ' County']
                ):
                    # 省辖县级行政单位不加 City 后缀
                    if not is_province_administered:
                        city_text += ' City'
                parts.append(city_text)
            elif is_province_administered:
                # 省辖县级行政单位（如济源市）
                city_text = city_en
                if city_text and not city_text.endswith(' City'):
                    city_text += ' City'
                parts.append(city_text)

            if province:
                province_text = province_en
                if province_text and not any(
                    province_text.endswith(suffix)
                    for suffix in [' Province', ' City', ' Municipality']
                ):
                    # 直辖市使用 City，省份使用 Province
                    if province in DIRECT_CITIES:
                        province_text += ' City'
                    else:
                        province_text += ' Province'
                parts.append(province_text)

            return ', '.join(parts) if parts else ''

        mapping = {
            'province': point_data.province,
            'city': point_data.city,
            'district': point_data.district,
            'province_en': point_data.province_en,
            'city_en': point_data.city_en,
            'district_en': point_data.district_en,
            'region': get_region(),
            'region_en': get_region_en(),
            'road_number': point_data.road_number,
            'road_name': point_data.road_name,
            'road_name_en': point_data.road_name_en,
            'speed': (point_data.speed * 3.6) if point_data.speed else None,  # m/s -> km/h
            'elevation': point_data.elevation,
            'compass_angle': point_data.bearing,
            'latitude': point_data.latitude_wgs84,
            'longitude': point_data.longitude_wgs84,
        }
        return mapping.get(source)

    def _get_font(self, font_id: str, size: int) -> ImageFont.ImageFont:
        """获取字体对象"""
        cache_key = f"{font_id}_{size}"

        if cache_key in self._font_cache:
            return self._font_cache[cache_key]

        # 尝试从加载的字体获取
        if font_id in self.fonts:
            font = self.fonts[font_id]
            try:
                img_font = ImageFont.truetype(font.file_path, size)
                self._font_cache[cache_key] = img_font
                return img_font
            except Exception:
                pass

        # 尝试系统字体
        if font_id in self.SYSTEM_FONTS:
            font_info = self.SYSTEM_FONTS[font_id]
            for path in font_info['paths']:
                if os.path.exists(path):
                    try:
                        img_font = ImageFont.truetype(path, size)
                        self._font_cache[cache_key] = img_font
                        return img_font
                    except Exception:
                        continue

        # 使用默认字体
        return ImageFont.load_default(size)

    def _get_pil_anchor(self, horizontal: str, vertical: str) -> str:
        """获取 PIL 锚点"""
        key = (horizontal, vertical)
        return self.PIL_ANCHORS.get(key, 'la')

    def _parse_color(self, color: str) -> tuple:
        """解析颜色字符串"""
        color = color.lstrip('#')

        if len(color) == 6:
            # RGB
            return tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        elif len(color) == 8:
            # RGBA
            return tuple(int(color[i:i+2], 16) for i in (0, 2, 4, 6))

        # 尝试解析颜色名称
        color_names = {
            'white': (255, 255, 255),
            'black': (0, 0, 0),
            'red': (255, 0, 0),
            'green': (0, 255, 0),
            'blue': (0, 0, 255),
        }
        return color_names.get(color.lower(), (255, 255, 255))


def create_sample_point() -> TrackPoint:
    """创建示例轨迹点用于预览"""
    point = TrackPoint(
        latitude_wgs84=34.7732,
        longitude_wgs84=111.2167,
        elevation=500.0,
        speed=13.89,  # m/s -> 50 km/h
        bearing=225.0,
        province='河南省',
        city='三门峡市',
        district='渑池县',
        province_en='Henan',
        city_en='Sanmenxia',
        district_en='Mianchi',
        road_number='G310',
        road_name='黄河路',
        road_name_en='Huanghe Rd.',
    )
    return point
