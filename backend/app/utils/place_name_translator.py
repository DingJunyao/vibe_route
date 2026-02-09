"""
地名英文翻译工具

支持行政区划和道路名称的自动翻译
"""
import re
from typing import Optional
from pypinyin import lazy_pinyin, Style


# 道路后缀映射（按长度降序排列，确保长后缀优先匹配）
ROAD_SUFFIXES = [
    # 大道 + 方位
    ("大道北", "Ave.", "(N)"),
    ("大道南", "Ave.", "(S)"),
    ("大道东", "Ave.", "(E)"),
    ("大道西", "Ave.", "(W)"),
    ("大道中", "Ave.", "(M)"),
    # 路 + 方位（XX 至少要两个字）
    ("北路", "Rd.", "(N)"),
    ("南路", "Rd.", "(S)"),
    ("东路", "Rd.", "(E)"),
    ("西路", "Rd.", "(W)"),
    ("中路", "Rd.", "(M)"),
    # 高架类
    ("大道高架", "Elevated Ave.", None),
    ("大街高架", "Elevated St.", None),
    ("街高架", "Elevated St.", None),
    ("路高架", "Elevated Rd.", None),
    ("高架", "Elevated Rd.", None),
    # 大道
    ("大道", "Ave.", None),
    # 街
    ("大街", "St.", None),
    ("街", "St.", None),
    # 高速/快速路
    ("高速", "Expwy.", None),
    ("快速路", "Expwy.", None),
    # 公路
    ("公路", "Hwy.", None),
    # 桥
    ("大桥", "Bridge", None),
    ("桥", "Bridge", None),
    # 巷
    ("巷", "Alley", None),
    # 线
    ("线", "Line", None),
    # 路（普通，放在最后）
    ("路", "Rd.", None),
]


def translate_road_name(name: str) -> str:
    """
    翻译道路名称为英文

    Args:
        name: 道路中文名称，如 "中山北路"、"京哈高速"

    Returns:
        str: 英文名称，如 "Zhongshan Rd. (N)"、"Jingha Expwy."

    Examples:
        >>> translate_road_name("中山北路")
        "Zhongshan Rd. (N)"
        >>> translate_road_name("京哈高速")
        "Jingha Expwy."
        >>> translate_road_name("G221")
        "G221"
        >>> translate_road_name("台北路")
        "Taibei Rd."  # 台北路只有一个字，不匹配方位规则
    """
    if not name:
        return ""

    # 特殊：全数字或字母开头的（如 G221、S1、京哈高速 G1）
    # 检查是否有字母/数字前缀
    prefix_match = re.match(r'^[A-Z0-9\u4e00-\u9fa5]+', name)
    if prefix_match:
        prefix = prefix_match.group()
        # 检查是否是纯字母/数字组合（如 G221、S1）
        if re.match(r'^[A-Z0-9]+$', prefix):
            remaining = name[len(prefix):]
            if not remaining:
                # 纯字母数字，直接返回
                return name
            # 检查剩余部分是否是后缀
            for suffix, en_suffix, _ in ROAD_SUFFIXES:
                if remaining.endswith(suffix):
                    return f"{prefix} {en_suffix}"
            # 没有匹配到已知后缀，直接返回
            return name

    # 按定义顺序匹配（已按长度降序排列）
    for suffix, en_suffix, direction in ROAD_SUFFIXES:
        if name.endswith(suffix):
            base_name = name[:-len(suffix)]

            # 检查方位后缀的基础名长度限制
            # 方位路名（北路、南路等）的 XX 至少要两个字
            if direction is not None and len(base_name) < 2:
                continue

            # 转换 base_name 为拼音
            if base_name:
                pinyin_list = lazy_pinyin(base_name, style=Style.NORMAL)
                base_en = "".join(pinyin_list).capitalize()
            else:
                base_en = ""

            # 组合结果
            if base_en:
                if direction:
                    return f"{base_en} {en_suffix} {direction}"
                else:
                    return f"{base_en} {en_suffix}"
            else:
                # 只有后缀没有基础名
                return en_suffix

    # 没有匹配到任何后缀，使用纯拼音
    pinyin_list = lazy_pinyin(name, style=Style.NORMAL)
    return "".join(pinyin_list).capitalize()


def translate_place_name(name: str, place_type: str) -> str:
    """
    根据类型翻译地名

    Args:
        name: 中文名称
        place_type: 类型 (province/city/district/road_name)

    Returns:
        str: 英文名称

    Examples:
        >>> translate_place_name("河北省", "province")
        "Hebei Province"
        >>> translate_place_name("中山北路", "road_name")
        "Zhongshan Rd. (N)"
    """
    if not name:
        return ""

    if place_type == "road_name":
        return translate_road_name(name)

    # 行政区划翻译使用 pinyin_generator
    from app.utils.pinyin_generator import name_to_pinyin

    level_map = {
        "province": "province",
        "city": "city",
        "district": "area",
    }

    return name_to_pinyin(name, level_map.get(place_type, "province"))
