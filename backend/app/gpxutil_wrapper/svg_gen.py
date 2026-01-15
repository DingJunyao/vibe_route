"""
道路标志 SVG 生成模块

简化的 Web 版本，不依赖外部字体文件
"""
import os
from typing import Optional
from dataclasses import dataclass
import svgwrite


@dataclass
class RoadSignColors:
    """道路标志颜色定义"""
    # 国道红色
    RED = '#ED1724'
    # 省道黄色
    YELLOW = '#FFCD00'
    # 白色
    WHITE = '#FFFFFF'
    # 黑色
    BLACK = '#000000'
    # 高速绿色
    GREEN = '#007367'


@dataclass
class RoadSignConfig:
    """道路标志配置"""
    # 普通道路标志尺寸
    WAY_NUM_WIDTH = 400
    WAY_NUM_HEIGHT = 200
    WAY_NUM_BORDER_RADIUS = 20
    WAY_NUM_BORDER_WIDTH = 10
    WAY_NUM_FONT_SIZE = 120
    WAY_NUM_FONT_WEIGHT = 'bold'
    WAY_NUM_FONT_FAMILY = 'Arial, "Microsoft YaHei", sans-serif'

    # 高速标志尺寸
    EXPWY_HEIGHT = 1000
    EXPWY_BANNER_HEIGHT = 150
    EXPWY_BORDER_RADIUS = 30
    EXPWY_FONT_SIZE_CODE = 200
    EXPWY_FONT_SIZE_NAME = 100
    EXPWY_FONT_SIZE_BANNER = 80
    EXPWY_FONT_FAMILY = 'Arial, "Microsoft YaHei", sans-serif'


def calculate_way_num_width(code: str) -> int:
    """根据道路编号计算宽度"""
    base_width = RoadSignConfig.WAY_NUM_WIDTH
    # 每个字符大约 100px 宽
    char_width = 100
    return max(base_width, len(code) * char_width + 100)


def generate_way_num_sign(
    code: str,
    output_path: Optional[str] = None
) -> str:
    """
    生成普通道路标志 SVG

    Args:
        code: 道路编号 (如 G221, S221, X221, Y221)
        output_path: 输出文件路径，如果为 None 则返回 SVG 内容

    Returns:
        SVG 内容或文件路径
    """
    if not code:
        raise ValueError("道路编号不能为空")

    # 根据编号前缀确定颜色
    sign_type = code[0].upper()

    if sign_type == 'G':
        background_color = RoadSignColors.RED
        text_color = RoadSignColors.WHITE
    elif sign_type == 'S':
        background_color = RoadSignColors.YELLOW
        text_color = RoadSignColors.BLACK
    elif sign_type in ('X', 'Y', 'Z', 'C'):
        background_color = RoadSignColors.WHITE
        text_color = RoadSignColors.BLACK
    else:
        # 默认样式
        background_color = RoadSignColors.WHITE
        text_color = RoadSignColors.BLACK

    # 计算尺寸
    width = calculate_way_num_width(code)
    height = RoadSignConfig.WAY_NUM_HEIGHT
    border_radius = RoadSignConfig.WAY_NUM_BORDER_RADIUS
    border_width = RoadSignConfig.WAY_NUM_BORDER_WIDTH

    # 创建 SVG
    dwg = svgwrite.Drawing(
        size=(f'{width}px', f'{height}px'),
        profile='full'
    )

    # 背景矩形
    dwg.add(dwg.rect(
        insert=(border_width, border_width),
        size=(width - border_width * 2, height - border_width * 2),
        rx=border_radius - border_width // 2,
        ry=border_radius - border_width // 2,
        fill=text_color,
        stroke=background_color,
        stroke_width=border_width
    ))

    # 文字
    text = dwg.text(
        code,
        insert=(width / 2, height / 2),
        font_size=RoadSignConfig.WAY_NUM_FONT_SIZE,
        font_family=RoadSignConfig.WAY_NUM_FONT_FAMILY,
        font_weight=RoadSignConfig.WAY_NUM_FONT_WEIGHT,
        fill=background_color,
        text_anchor='middle',
        dominant_baseline='central'
    )
    dwg.add(text)

    if output_path:
        dwg.saveas(output_path)
        return output_path
    else:
        return dwg.tostring()


def calculate_expwy_dimensions(code: str, has_name: bool) -> tuple:
    """计算高速标志尺寸"""
    code_num_len = len(code)

    # 基础尺寸
    if code_num_len <= 2:
        width = 800
    elif code_num_len == 3:
        width = 1000
    else:
        # 4 位编号，需要分成两部分
        width = 1400

    if has_name:
        height = 1200
    else:
        height = 1000

    return width, height


def generate_expwy_sign(
    code: str,
    province: Optional[str] = None,
    name: Optional[str] = None,
    output_path: Optional[str] = None
) -> str:
    """
    生成高速道路标志 SVG

    Args:
        code: 高速编号 (如 G5, G45, S21)
        province: 省份简称 (如 '豫', '晋')，用于省级高速
        name: 道路名称
        output_path: 输出文件路径

    Returns:
        SVG 内容或文件路径
    """
    if not code:
        raise ValueError("高速编号不能为空")

    # 标准化编号
    if province and not code.startswith('S'):
        code = 'S' + code
    elif not province and not code.startswith('G'):
        code = 'G' + code

    # 确定颜色和文字
    if province:
        banner_text = f'{province}高速'
        banner_color = RoadSignColors.YELLOW
        banner_text_color = RoadSignColors.BLACK
    else:
        banner_text = '国家高速'
        banner_color = RoadSignColors.RED
        banner_text_color = RoadSignColors.WHITE

    background_color = RoadSignColors.GREEN
    stroke_color = RoadSignColors.WHITE

    # 计算尺寸
    width, height = calculate_expwy_dimensions(code, bool(name))
    banner_height = RoadSignConfig.EXPWY_BANNER_HEIGHT

    # 创建 SVG
    dwg = svgwrite.Drawing(
        size=(f'{width}px', f'{height}px'),
        profile='full'
    )

    # 主体背景（绿色圆角矩形）
    body_height = height - banner_height
    dwg.add(dwg.rect(
        insert=(0, banner_height),
        size=(width, body_height),
        fill=background_color,
        stroke=stroke_color,
        stroke_width=10,
        rx=RoadSignConfig.EXPWY_BORDER_RADIUS,
        ry=RoadSignConfig.EXPWY_BORDER_RADIUS
    ))

    # 顶部横幅
    dwg.add(dwg.rect(
        insert=(0, 0),
        size=(width, banner_height),
        fill=banner_color
    ))

    # 横幅文字
    banner_font_size = min(RoadSignConfig.EXPWY_FONT_SIZE_BANNER, width / len(banner_text) * 1.5)
    dwg.add(dwg.text(
        banner_text,
        insert=(width / 2, banner_height / 2),
        font_size=banner_font_size,
        font_family=RoadSignConfig.EXPWY_FONT_FAMILY,
        font_weight='bold',
        fill=banner_text_color,
        text_anchor='middle',
        dominant_baseline='central'
    ))

    # 道路编号
    code_font_size = RoadSignConfig.EXPWY_FONT_SIZE_CODE
    code_y = banner_height + (body_height / 3) if name else banner_height + body_height / 2

    # 处理 4 位编号（分成大号和小号）
    if len(code) == 5:  # G + 4 位数字
        big_code = code[:3]  # 如 G45
        small_code = code[3:]  # 如 11

        # 大号编号
        dwg.add(dwg.text(
            big_code,
            insert=(width / 2, code_y),
            font_size=int(code_font_size * 1.2),
            font_family=RoadSignConfig.EXPWY_FONT_FAMILY,
            font_weight='bold',
            fill=stroke_color,
            text_anchor='middle',
            dominant_baseline='central'
        ))

        # 小号编号
        dwg.add(dwg.text(
            small_code,
            insert=(width / 2, code_y + code_font_size),
            font_size=int(code_font_size * 0.6),
            font_family=RoadSignConfig.EXPWY_FONT_FAMILY,
            font_weight='bold',
            fill=stroke_color,
            text_anchor='middle',
            dominant_baseline='central'
        ))
    else:
        dwg.add(dwg.text(
            code,
            insert=(width / 2, code_y),
            font_size=code_font_size,
            font_family=RoadSignConfig.EXPWY_FONT_FAMILY,
            font_weight='bold',
            fill=stroke_color,
            text_anchor='middle',
            dominant_baseline='central'
        ))

    # 道路名称
    if name:
        name_y = banner_height + body_height * 0.75
        name_font_size = RoadSignConfig.EXPWY_FONT_SIZE_NAME
        dwg.add(dwg.text(
            name,
            insert=(width / 2, name_y),
            font_size=name_font_size,
            font_family=RoadSignConfig.EXPWY_FONT_FAMILY,
            font_weight='normal',
            fill=stroke_color,
            text_anchor='middle',
            dominant_baseline='central'
        ))

    if output_path:
        dwg.saveas(output_path)
        return output_path
    else:
        return dwg.tostring()


def generate_road_sign(
    sign_type: str,
    code: str,
    province: Optional[str] = None,
    name: Optional[str] = None,
    output_path: Optional[str] = None
) -> str:
    """
    统一的道路标志生成入口

    Args:
        sign_type: 标志类型 ('way' 或 'expwy')
        code: 道路编号
        province: 省份（仅高速用）
        name: 道路名称
        output_path: 输出路径

    Returns:
        SVG 内容或文件路径
    """
    if sign_type == 'way':
        return generate_way_num_sign(code, output_path)
    elif sign_type == 'expwy':
        return generate_expwy_sign(code, province, name, output_path)
    else:
        raise ValueError(f"未知的标志类型: {sign_type}")
