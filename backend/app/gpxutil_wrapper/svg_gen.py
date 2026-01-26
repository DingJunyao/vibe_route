"""
道路标志 SVG 生成模块

使用专业交通标志字体和 SVG 模板生成符合国标的道路标志
参照 gpxutil 实现
"""
import os
import re
from functools import reduce
from typing import Optional
from pathlib import Path

import svgwrite
from svgpathtools import parse_path

from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen

from app.core.config import settings
from loguru import logger


# 颜色定义 (国标 GB 5768.2-2009)
# CMYK 值转换为 RGB
RED = '#ED1724'      # CMYK 0/100/65/0 -- RGB 237,23,36
YELLOW = '#FFCD00'   # CMYK 0/0/100/0 -- RGB 255,205,0
WHITE = '#FFFFFF'
BLACK = '#000000'
GREEN = '#007367'    # CMYK 100/0/79/9 -- RGB 0,155,103


# 模板路径
TEMPLATE_DIR = Path(settings.ROAD_SIGN_DIR).parent / 'templates'

# 普通道路标志尺寸和位置
WAY_NUM_WIDTH = 400
WAY_NUM_HEIGHT = 200
WAY_NUM_WORD_START_X = 50
WAY_NUM_WORD_START_Y = 50
WAY_NUM_WORD_WIDTH = 300
WAY_NUM_WORD_HEIGHT = 100

# 高速公路标志尺寸和位置
EXPWY_CODE_START_X_DICT = {
    '1': 150,
    '2': 90,
    '4_big': 90,
    '4_small': 1220,
}
EXPWY_CODE_START_Y_DICT = {
    'big': 370,
    'big_name': 340,
    'small': 520,
    'small_name': 490,
}
EXPWY_CODE_WIDTH_DICT = {
    '1': 700,
    '2_4_big': 1070,
    '4_small': 390,
}
EXPWY_CODE_HEIGHT_DICT = {
    'big': 450,
    'small': 300,
}
EXPWY_NAME_START_X_DICT = {
    '1': 100,
    '2_4': 150,
}
EXPWY_NAME_START_Y = 860
EXPWY_NAME_WIDTH_DICT = {
    1: 800,
    2: 950,
    4: 1400,
}
EXPWY_NAME_HEIGHT = 200

EXPWY_BANNER_TEXT_START_X_DICT = {
    'national_1': 150,
    'national_2': 275,
    '4': 355,
    'province_1': 250,
    'province_2': 359.1,
}
EXPWY_BANNER_TEXT_START_Y_DICT = {
    'without_name': 80,
    'with_name': 110,
}
EXPWY_BANNER_TEXT_WIDTH_DICT = {
    'national_1_2': 700,
    '4': 990,
    'province_1_2': 500
}
EXPWY_BANNER_TEXT_HEIGHT = 100


def get_font_path(font_type: str, font_config: Optional[dict] = None) -> Optional[str]:
    """
    获取字体文件路径

    Args:
        font_type: 字体类型 ('A', 'B', 'C')
        font_config: 字体配置字典，包含 font_a, font_b, font_c

    Returns:
        字体文件完整路径，如果不存在则返回 None
    """
    # 如果提供了配置，使用配置中的字体文件名
    if font_config:
        font_filename = font_config.get(f'font_{font_type.lower()}')
        if font_filename:
            font_dir = Path(settings.ROAD_SIGN_DIR).parent / 'fonts'
            font_path = font_dir / font_filename
            if font_path.exists():
                logger.info(f"[get_font_path] 使用配置字体: {font_path}")
                return str(font_path)

    # 回退到默认字体文件名
    font_dir = Path(settings.ROAD_SIGN_DIR).parent / 'fonts'

    if font_type == 'A':
        # A 型字体 - 中文文字（思源黑体或交通标志 A 型）
        font_files = ['SourceHanSansSC-Bold.otf', 'SourceHanSansSC-Bold.ttf',
                      'jtbz_A.ttf', 'jtbz_A.otf']
    elif font_type == 'B':
        # B 型字体 - 主数字
        font_files = ['jtbz_B.ttf', 'jtbz_B.otf']
    elif font_type == 'C':
        # C 型字体 - 小数字
        font_files = ['jtbz_C.ttf', 'jtbz_C.otf']
    else:
        logger.warning(f"[get_font_path] 未知字体类型: {font_type}")
        return None

    for font_file in font_files:
        font_path = font_dir / font_file
        if font_path.exists():
            logger.info(f"[get_font_path] 使用默认字体: {font_path}")
            return str(font_path)

    logger.warning(f"[get_font_path] 未找到字体类型 {font_type} 的任何字体文件")
    return None


def char_to_svg_path(font_path: str, char: str):
    """将字符转换为 SVG Path"""
    font = TTFont(font_path)
    cmap = font.getBestCmap()

    if ord(char) not in cmap:
        raise ValueError(f"字符 '{char}' 不在字体中")

    glyph_name = cmap[ord(char)]
    glyph_set = font.getGlyphSet()
    glyph = glyph_set[glyph_name]

    pen = SVGPathPen(glyph_set)
    glyph.draw(pen)
    svg_path = pen.getCommands()

    # 翻转 Y 轴修复方向
    return parse_path(svg_path).scaled(1, -1)


def calculate_scaled_char_info(
    code: str,
    start_x: float,
    start_y: float,
    width: float,
    height: float,
    font_path: str
):
    """
    将文字字符串转换为 SVG Path 列表

    排版时假定所有字符都等高
    """
    scaled_char_path_list = []
    scaled_char_width_list = []

    # 遍历每个字符，转换为 SVG Path
    for char in code:
        paths_char = char_to_svg_path(font_path, char)
        char_minx, char_maxx, char_miny, char_maxy = paths_char.bbox()
        char_height = char_maxy - char_miny

        # 按目标高度缩放
        ratio = height / char_height
        scaled_path_char = paths_char.scaled(ratio)

        # 移动到原点
        scaled_char_minx, _, scaled_char_miny, _ = scaled_path_char.bbox()
        scaled_path_char = scaled_path_char.translated(complex(-scaled_char_minx, -scaled_char_miny))

        scaled_char_width = scaled_path_char.bbox()[1] - scaled_path_char.bbox()[0]
        scaled_char_width_list.append(scaled_char_width)
        scaled_char_path_list.append(scaled_path_char)

    # 计算字符间距
    if len(code) > 1:
        space = (width - reduce(lambda x, y: x + y, scaled_char_width_list)) / (len(code) - 1)
    else:
        space = 0

    # 计算每个字符的最终位置
    char_pos_list = []
    char_x = start_x
    char_y = start_y
    for i, char_width in enumerate(scaled_char_width_list):
        if i != 0:
            char_x += scaled_char_width_list[i - 1] + space
        char_pos_list.append((char_x, char_y))

    # 应用最终位置
    return [path.translated(complex(*pos))
            for path, pos in zip(scaled_char_path_list, char_pos_list)]


def generate_way_num_sign(
    code: str,
    font_config: Optional[dict] = None,
    output_path: Optional[str] = None
) -> str:
    """
    生成普通道路标志 SVG

    Args:
        code: 道路编号 (如 G221, S221, X221, Y221)
        font_config: 字体配置字典，包含 font_a, font_b, font_c
        output_path: 输出文件路径，如果为 None 则返回 SVG 内容

    Returns:
        SVG 内容或文件路径
    """
    if not code:
        raise ValueError("道路编号不能为空")

    logger.info(f"[generate_way_num_sign] 生成普通道路标志: code={code}, font_config={font_config}")

    # 根据编号前缀确定颜色
    sign_type = code[0].upper()

    if sign_type == 'G':
        background_color = RED
        stroke_color = WHITE
    elif sign_type == 'S':
        background_color = YELLOW
        stroke_color = BLACK
    elif sign_type in ('X', 'Y', 'Z', 'C'):
        background_color = WHITE
        stroke_color = BLACK
    else:
        # 默认样式
        background_color = WHITE
        stroke_color = BLACK

    template_path = TEMPLATE_DIR / 'way_num.svg'

    if template_path.exists():
        from svgpathtools import svg2paths
        # 使用模板文件
        paths, attributes = svg2paths(str(template_path))

        # 生成文字 SVG Path
        font_path = get_font_path('B', font_config)
        if font_path:
            scaled_char_path_list = calculate_scaled_char_info(
                code, WAY_NUM_WORD_START_X, WAY_NUM_WORD_START_Y,
                WAY_NUM_WORD_WIDTH, WAY_NUM_WORD_HEIGHT, font_path
            )
        else:
            # 字体文件不存在，回退到普通文字
            logger.warning(f"[generate_way_num_sign] 未找到B型字体，使用普通文字")
            scaled_char_path_list = None

        # 创建 SVG
        dwg = svgwrite.Drawing(
            size=(f'{WAY_NUM_WIDTH}px', f'{WAY_NUM_HEIGHT}px'),
            viewBox=f'0 0 {WAY_NUM_WIDTH} {WAY_NUM_HEIGHT}',
            profile='full'
        )

        # 绘制模板路径（背景）
        for path, attr in zip(paths, attributes):
            insert_x = float(attr.get('x', 0))
            insert_y = float(attr.get('y', 0))
            width = float(attr['width'])
            height = float(attr['height'])
            rx = float(attr.get('rx', 0))
            ry = float(attr.get('ry', 0))

            fill = stroke_color
            if 'class' in attr:
                if attr['class'] == 'background':
                    fill = background_color
                elif attr['class'] == 'stroke':
                    fill = stroke_color

            dwg.add(dwg.rect(
                insert=(insert_x, insert_y),
                size=(width, height),
                rx=rx, ry=ry,
                fill=fill
            ))

        # 绘制文字
        if scaled_char_path_list:
            for path in scaled_char_path_list:
                dwg.add(dwg.path(d=path.d(), fill=stroke_color))
        else:
            # 回退到普通文字
            dwg.add(dwg.text(
                code,
                insert=(WAY_NUM_WIDTH / 2, WAY_NUM_HEIGHT / 2),
                font_size=WAY_NUM_WORD_HEIGHT,
                font_family='Arial, "Microsoft YaHei", sans-serif',
                font_weight='bold',
                fill=stroke_color,
                text_anchor='middle',
                dominant_baseline='central'
            ))

    else:
        # 模板文件不存在，使用简化版本
        dwg = svgwrite.Drawing(
            size=(f'{WAY_NUM_WIDTH}px', f'{WAY_NUM_HEIGHT}px'),
            viewBox=f'0 0 {WAY_NUM_WIDTH} {WAY_NUM_HEIGHT}',
            profile='full'
        )

        # 背景矩形
        dwg.add(dwg.rect(
            insert=(10, 10),
            size=(WAY_NUM_WIDTH - 20, WAY_NUM_HEIGHT - 20),
            rx=30, ry=30,
            fill=stroke_color,
            stroke=background_color,
            stroke_width=10
        ))

        dwg.add(dwg.rect(
            insert=(20, 20),
            size=(WAY_NUM_WIDTH - 40, WAY_NUM_HEIGHT - 40),
            rx=20, ry=20,
            fill=background_color
        ))

        # 文字
        dwg.add(dwg.text(
            code,
            insert=(WAY_NUM_WIDTH / 2, WAY_NUM_HEIGHT / 2),
            font_size=WAY_NUM_WORD_HEIGHT,
            font_family='Arial, "Microsoft YaHei", sans-serif',
            font_weight='bold',
            fill=stroke_color,
            text_anchor='middle',
            dominant_baseline='central'
        ))

    if output_path:
        dwg.saveas(output_path)
        return output_path
    else:
        svg_string = dwg.tostring()
        # 移除固定的 width 和 height 属性，保留 viewBox 让 SVG 可以自适应缩放
        svg_string = re.sub(r' width="\d+px"', '', svg_string)
        svg_string = re.sub(r' height="\d+px"', '', svg_string)
        return svg_string


def generate_expwy_sign(
    code: str,
    province: Optional[str] = None,
    name: Optional[str] = None,
    font_config: Optional[dict] = None,
    output_path: Optional[str] = None
) -> str:
    """
    生成高速道路标志 SVG

    Args:
        code: 高速编号 (如 G5, G45, S21)
        province: 省份简称 (如 '豫', '晋')，用于省级高速
        name: 道路名称
        font_config: 字体配置字典，包含 font_a, font_b, font_c
        output_path: 输出文件路径

    Returns:
        SVG 内容或文件路径
    """
    if not code:
        raise ValueError("高速编号不能为空")

    logger.info(f"[generate_expwy_sign] 生成高速标志: code={code}, province={province}, name={name}, font_config={font_config}")

    # 标准化编号
    if province and not code.startswith('S'):
        code = 'S' + code
    elif not province and not code.startswith('G'):
        code = 'G' + code

    code_num_len = len(code) - 1

    # 确定颜色
    if province:
        banner_text = f'{province}高速'
        banner_color = YELLOW
        banner_char_color = BLACK
    else:
        banner_text = '国家高速'
        banner_color = RED
        banner_char_color = WHITE

    background_color = GREEN
    stroke_color = WHITE

    # 确定模板索引
    template_index = str(code_num_len)
    if name:
        template_index += '_name'

    # 根据编号位数确定参数
    code_start_x_index = '2'
    code_start_y_index = 'big_name' if name else 'big'
    code_width_index = '2_4_big'
    code_height_index = 'big'

    small_code_start_x_index = '4_small'
    small_code_start_y_index = 'small_name' if name else 'small'
    small_code_width_index = '4_small'
    small_code_height_index = 'small'

    name_start_x_index = '2_4'
    name_width_index = 2

    banner_text_start_x_index = 'province_' if province else 'national_'
    banner_text_start_x_index += str(code_num_len)
    banner_text_start_y_index = 'with_name' if name else 'without_name'

    if code_num_len == 4:
        banner_text_width_index = '4'
        banner_text_start_x_index = '4'
    elif province:
        banner_text_width_index = 'province_1_2'
    else:
        banner_text_width_index = 'national_1_2'

    # 根据编号位数调整
    if code_num_len == 1:
        code_start_x_index = '1'
        code_width_index = '1'
        name_start_x_index = '1'
        name_width_index = 1
    elif code_num_len == 2:
        code_start_x_index = '2'
        code_width_index = '2_4_big'
        name_start_x_index = '2_4'
        name_width_index = 2
    elif code_num_len == 4:
        code_start_x_index = '4_big'
        code_width_index = '2_4_big'
        name_start_x_index = '2_4'
        name_width_index = 4

    # 处理 4 位编号（分成大号和小号）
    big_code = None
    small_code = None
    if code_num_len == 4:
        big_code = code[:3]
        small_code = code[3:]
    else:
        big_code = code

    # 获取模板文件
    template_name = f'expwy_{template_index}.svg'
    template_path = TEMPLATE_DIR / template_name

    if template_path.exists():
        from svgpathtools import svg2paths
        paths, attributes = svg2paths(str(template_path))

        # 获取 SVG 尺寸
        import xml.etree.ElementTree as ET
        tree = ET.parse(str(template_path))
        root = tree.getroot()
        viewbox = [float(i) for i in root.get('viewBox').split()]
        svg_width = int(viewbox[2] - viewbox[0])
        svg_height = int(viewbox[3] - viewbox[1])

        dwg = svgwrite.Drawing(
            size=(f'{svg_width}px', f'{svg_height}px'),
            viewBox=f'0 0 {svg_width} {svg_height}',
            profile='full'
        )

        # 绘制模板路径（背景）
        for path, attr in zip(paths, attributes):
            fill = stroke_color
            if 'class' in attr:
                if attr['class'] == 'background':
                    fill = background_color
                elif attr['class'] == 'stroke':
                    fill = stroke_color
                elif attr['class'] == 'banner':
                    fill = banner_color
            dwg.add(dwg.path(d=path.d(), fill=fill))

        # 生成横幅文字 SVG Path
        font_a_path = get_font_path('A', font_config)
        if font_a_path:
            scaled_banner_text_char_path_list = calculate_scaled_char_info(
                banner_text,
                EXPWY_BANNER_TEXT_START_X_DICT[banner_text_start_x_index],
                EXPWY_BANNER_TEXT_START_Y_DICT[banner_text_start_y_index],
                EXPWY_BANNER_TEXT_WIDTH_DICT[banner_text_width_index],
                EXPWY_BANNER_TEXT_HEIGHT,
                font_a_path
            )
            for path in scaled_banner_text_char_path_list:
                dwg.add(dwg.path(d=path.d(), fill=banner_char_color))
        else:
            # 回退到普通文字
            dwg.add(dwg.text(
                banner_text,
                insert=(svg_width / 2, EXPWY_BANNER_TEXT_START_Y_DICT[banner_text_start_y_index] + EXPWY_BANNER_TEXT_HEIGHT / 2),
                font_size=EXPWY_BANNER_TEXT_HEIGHT,
                font_family='Arial, "Microsoft YaHei", sans-serif',
                font_weight='bold',
                fill=banner_char_color,
                text_anchor='middle',
                dominant_baseline='central'
            ))

        # 生成道路编号 SVG Path
        font_b_path = get_font_path('B', font_config)
        if font_b_path:
            scaled_big_code_char_path_list = calculate_scaled_char_info(
                big_code,
                EXPWY_CODE_START_X_DICT[code_start_x_index],
                EXPWY_CODE_START_Y_DICT[code_start_y_index],
                EXPWY_CODE_WIDTH_DICT[code_width_index],
                EXPWY_CODE_HEIGHT_DICT[code_height_index],
                font_b_path
            )
            for path in scaled_big_code_char_path_list:
                dwg.add(dwg.path(d=path.d(), fill=stroke_color))

            # 4 位编号的小号部分
            if small_code:
                font_c_path = get_font_path('C', font_config)
                if font_c_path:
                    scaled_small_code_char_path_list = calculate_scaled_char_info(
                        small_code,
                        EXPWY_CODE_START_X_DICT[small_code_start_x_index],
                        EXPWY_CODE_START_Y_DICT[small_code_start_y_index],
                        EXPWY_CODE_WIDTH_DICT[small_code_width_index],
                        EXPWY_CODE_HEIGHT_DICT[small_code_height_index],
                        font_c_path
                    )
                    for path in scaled_small_code_char_path_list:
                        dwg.add(dwg.path(d=path.d(), fill=stroke_color))
        else:
            # 回退到普通文字
            dwg.add(dwg.text(
                big_code,
                insert=(svg_width / 2, EXPWY_CODE_START_Y_DICT[code_start_y_index] + EXPWY_CODE_HEIGHT_DICT[code_height_index] / 2),
                font_size=EXPWY_CODE_HEIGHT_DICT[code_height_index],
                font_family='Arial, "Microsoft YaHei", sans-serif',
                font_weight='bold',
                fill=stroke_color,
                text_anchor='middle',
                dominant_baseline='central'
            ))

        # 生成道路名称 SVG Path
        if name:
            if font_a_path:
                scaled_name_char_path_list = calculate_scaled_char_info(
                    name,
                    EXPWY_NAME_START_X_DICT[name_start_x_index],
                    EXPWY_NAME_START_Y,
                    EXPWY_NAME_WIDTH_DICT[name_width_index],
                    EXPWY_NAME_HEIGHT,
                    font_a_path
                )
                for path in scaled_name_char_path_list:
                    dwg.add(dwg.path(d=path.d(), fill=stroke_color))
            else:
                dwg.add(dwg.text(
                    name,
                    insert=(svg_width / 2, EXPWY_NAME_START_Y + EXPWY_NAME_HEIGHT / 2),
                    font_size=EXPWY_NAME_HEIGHT,
                    font_family='Arial, "Microsoft YaHei", sans-serif',
                    fill=stroke_color,
                    text_anchor='middle',
                    dominant_baseline='central'
                ))

    else:
        # 模板文件不存在，使用简化版本
        # 根据编号长度确定尺寸
        if code_num_len <= 2:
            svg_width = 1000
        elif code_num_len == 3:
            svg_width = 1250
        else:
            svg_width = 1650

        svg_height = 1200 if name else 1000
        banner_height = 150

        dwg = svgwrite.Drawing(
            size=(f'{svg_width}px', f'{svg_height}px'),
            viewBox=f'0 0 {svg_width} {svg_height}',
            profile='full'
        )

        # 主体背景（绿色圆角矩形）
        body_height = svg_height - banner_height
        dwg.add(dwg.rect(
            insert=(0, banner_height),
            size=(svg_width, body_height),
            fill=background_color,
            stroke=stroke_color,
            stroke_width=10,
            rx=30, ry=30
        ))

        # 顶部横幅
        dwg.add(dwg.rect(
            insert=(0, 0),
            size=(svg_width, banner_height),
            fill=banner_color
        ))

        # 横幅文字
        dwg.add(dwg.text(
            banner_text,
            insert=(svg_width / 2, banner_height / 2),
            font_size=80,
            font_family='Arial, "Microsoft YaHei", sans-serif',
            font_weight='bold',
            fill=banner_char_color,
            text_anchor='middle',
            dominant_baseline='central'
        ))

        # 道路编号
        code_font_size = 200
        code_y = banner_height + (body_height / 3) if name else banner_height + body_height / 2

        if small_code:
            dwg.add(dwg.text(
                big_code,
                insert=(svg_width / 2, code_y),
                font_size=int(code_font_size * 1.2),
                font_family='Arial, "Microsoft YaHei", sans-serif',
                font_weight='bold',
                fill=stroke_color,
                text_anchor='middle',
                dominant_baseline='central'
            ))
            dwg.add(dwg.text(
                small_code,
                insert=(svg_width / 2, code_y + code_font_size),
                font_size=int(code_font_size * 0.6),
                font_family='Arial, "Microsoft YaHei", sans-serif',
                font_weight='bold',
                fill=stroke_color,
                text_anchor='middle',
                dominant_baseline='central'
            ))
        else:
            dwg.add(dwg.text(
                big_code,
                insert=(svg_width / 2, code_y),
                font_size=code_font_size,
                font_family='Arial, "Microsoft YaHei", sans-serif',
                font_weight='bold',
                fill=stroke_color,
                text_anchor='middle',
                dominant_baseline='central'
            ))

        # 道路名称
        if name:
            name_y = banner_height + body_height * 0.75
            dwg.add(dwg.text(
                name,
                insert=(svg_width / 2, name_y),
                font_size=100,
                font_family='Arial, "Microsoft YaHei", sans-serif',
                fill=stroke_color,
                text_anchor='middle',
                dominant_baseline='central'
            ))

    if output_path:
        dwg.saveas(output_path)
        return output_path
    else:
        svg_string = dwg.tostring()
        # 移除固定的 width 和 height 属性，保留 viewBox 让 SVG 可以自适应缩放
        svg_string = re.sub(r' width="\d+px"', '', svg_string)
        svg_string = re.sub(r' height="\d+px"', '', svg_string)
        return svg_string


def generate_road_sign(
    sign_type: str,
    code: str,
    province: Optional[str] = None,
    name: Optional[str] = None,
    font_config: Optional[dict] = None,
    output_path: Optional[str] = None
) -> str:
    """
    统一的道路标志生成入口

    Args:
        sign_type: 标志类型 ('way' 或 'expwy')
        code: 道路编号
        province: 省份（仅高速用）
        name: 道路名称
        font_config: 字体配置字典，包含 font_a, font_b, font_c
        output_path: 输出路径

    Returns:
        SVG 内容或文件路径
    """
    if sign_type == 'way':
        return generate_way_num_sign(code, font_config, output_path)
    elif sign_type == 'expwy':
        return generate_expwy_sign(code, province, name, font_config, output_path)
    else:
        raise ValueError(f"未知的标志类型: {sign_type}")
